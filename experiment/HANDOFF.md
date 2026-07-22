# Handoff: where this project stands right now

Read this first if you're picking this up in a new chat/machine. It's a status
summary, not the design doc — see the pointers at the bottom for the real detail.

## What this is

A research project comparing two algorithm families for computing the discrete
locally-correct Fréchet distance/matching: **BBMS** (`BBMSCore`, `BBMSInter`; two
more variants exist but are currently out of scope, see below) and **DijkstraPrims**.
Goal is a paper comparing them on runtime, memory, and machine-independent operation
counts, across three synthetic datasets (worst-case adversarial, best-case identical
curves, random) — see `paper_draft.md` (repo root) for the paper's own structure.

**Branch: `main-experiment`** — not `main`. Everything described here lives there.

## Layout

- `algorithms/` — the three algorithms, plus `common.h` and `counters.h`/`.cpp`. This
  is the **canonical, will-be-published-with-the-paper** source. Not `src_cpp/` —
  that's old dev scratch space, ignore it (slated for deletion).
- `datasets/` — generated curve files, already committed (~177MB). One file per
  `(dataset, N)`, format documented in `experiment/PSEUDOCODE.md`.
- `experiment/` — the runner (`runner.cpp`, builds to `runner.exe` +
  `runner_counted.exe`) and the orchestrator (`main.py`). This is the current,
  canonical experiment. Not `experiments/` (plural) — that's the old ad hoc
  per-question experiments from earlier in the project (`cpp_adversarial`,
  `memory_usage`, `loglog_scaling`), also dev scratch space, not part of the paper.
- `results/` — where the orchestrator writes CSVs. Empty until a real run happens.

## Status: implementation done, smoke-tested on macOS + WSL, not yet run for real

Everything in `PLAN.md` and `PSEUDOCODE.md` has been implemented — not just
pseudocode anymore, the actual code exists and builds. Verified so far (on a Mac):

- All algorithm objects compile in both the plain and `-DCOUNT_OPS` builds.
- All three algorithms agree on `frechet_distance` on the same input.
- Op-counts look sane: `BBMSInter`'s shortcuts cut total NCA-walk steps ~5.5x vs
  `BBMSCore` on one worst-case sample; `DijkstraPrims` explores ~99.9% of the grid
  under the adversarial dataset, as expected.
- Resumability, timeout handling, wall-skipping (stop testing larger N after a
  failure), and wall-*reconstruction* after a resume — all confirmed working via
  smoke tests with tiny/overridden grids and an artificially short timeout.
- The cross-algorithm agreement check (§5.6 in `PLAN.md`) correctly flags an
  injected disagreement and stays silent on real, correct data.
- One real bug was caught and fixed during smoke testing: failed rows were losing
  `algorithm`/`N`/`sample` identity (all `-1`), which would have also silently broken
  wall-reconstruction on resume.

## WSL smoke test (Stage 2 in `PLAN.md`): done, 2026-07-22

All three things that couldn't be verified on macOS were checked on WSL (Ubuntu
24.04, kernel 5.15, native `~/dfm-smoke` filesystem, not `/mnt/c/...`), using a
throwaway copy of `algorithms/` + `experiment/{runner.cpp,Makefile,main.py}` +
two small dataset files (`worst-case` N=500 and N=4000) — not the full sweep.
That copy has been deleted; nothing under `experiment/` or `algorithms/` changed.

1. **Memory-pressure counters respond on Linux — confirmed.** Running `BBMSCore`
   N=500 under a `systemd-run --scope -p MemoryMax=5M -p MemorySwapMax=0` cgroup cap
   moved `major_faults` from 0 → 360, `block_input_ops` from 0 → 362, and
   `involuntary_ctx_switches` from ~0 → 71, versus an uncapped baseline run. These
   fields are genuinely live on Linux, not just schema placeholders.
2. **`maxrss_to_mb` Linux branch — confirmed correct.** Runner reported
   `maxrss_after_mb=9.08594`; `/usr/bin/time -v` on the same invocation reported
   `Maximum resident set size: 9304` KB → 9304/1024 = 9.086 MB. Exact match.
3. **Real OOM → `status=oom` — confirmed, two ways.**
   - `ulimit -v 100000` (100MB address-space cap) on a `BBMSCore` N=4000 run (needs
     ~384MB for its `m*n` node vector) triggered a real `std::bad_alloc`, caught by
     the runner itself, printed as `status=oom`. This is the path that flatly didn't
     work on macOS (`setrlimit failed`) — now confirmed on real Linux.
   - Separately, fed a subprocess that gets SIGKILLed with no stdout directly into
     `main.py`'s actual `run_and_classify` — confirmed its returncode/empty-output
     inference branch also classifies this as `status=oom`.
   - Note: tried to also trigger a *genuine* kernel/cgroup OOM-kill (rather than the
     `ulimit -v`/simulated-kill paths above) via `systemd-run --scope -p MemoryMax=...`.
     This turned out to be unreliable to signal/kill cleanly from outside in this WSL
     session (two runs became unresponsive under a tight cap with swap enabled —
     thrashing rather than getting OOM-killed — and had to be `pkill -9`'d) rather
     than actually validating anything new, so it was abandoned in favor of the two
     more targeted checks above, which cover the same code paths deterministically.

`PLAN.md` §6 checklist updated accordingly. Still open there: exact timeout value
and N-grid ceiling, both deferred to the AWS calibration run since they need real
hardware numbers.

## Local calibration rehearsal (Windows/WSL laptop, not the real testbed): done, 2026-07-22

Before AWS access, ran a small end-to-end rehearsal of `main.py` itself (not just
`runner.exe` in isolation, as the smoke test above did) on this WSL machine, to
validate the orchestrator's actual multi-N sweep behavior, and got calibration
signal worth carrying forward even though this hardware isn't the real testbed:

- `main.py` ran correctly end-to-end across a real multi-N sweep: resumability,
  wall-skipping, and cross-algorithm agreement all fired correctly on organically
  (not artificially) triggered timeouts, not just the artificial ones from the
  earlier smoke test.
- `BBMSCore`'s runtime scaling on `worst-case` looks much worse than cell-count-
  linear (~6-8x per N-doubling vs. ~4x expected) and it hit a 20s timeout already
  at N=4000 — only the 4th of 10 grid points, which goes up to N=50000.
- Memory scaled close to the expected ~4x/doubling, but extrapolated out to
  N=50000 implies multi-hundred-GB requirements for at least `BBMSInter` — likely
  unreachable on typical AWS instances.

Full numbers are in this session's transcript, not reproduced here since they're
laptop/WSL numbers, not AWS ones — not worth the confusion of looking canonical
in a doc. What *is* now in the repo, ready for the real machine: a tested
calibration script, so the AWS session doesn't require Claude to write ad hoc
commands live.

## What's next: AWS calibration, then the full run

See **`experiment/calibration/AWS_HANDOFF.md`** — a self-contained, step-by-step
plan for the AWS machine (no Claude Code access assumed there). It covers:
building, running `experiment/calibration/calibrate.py` (already written and
tested — reuses `main.py`'s own logic against a separate `results_calibration/`
output dir, so it can't clobber real data), reading the results to set
`TIMEOUT_S`/`GRID` in `main.py`, then launching the real full run safely
(tmux + a memory `ulimit` safety net) and pulling back the final `results/`.

## Where to look for more detail

- `experiment/PLAN.md` — the actual experimental design and reasoning (dataset
  sizing, sample counts, aggregation methodology, interleaving order, resumability,
  timeout/failure handling).
- `experiment/PSEUDOCODE.md` — file-by-file pseudocode for everything (now
  implemented for real, but this is still the clearest single-document overview).
- `experiment/calibration/AWS_HANDOFF.md` — the concrete next-step plan, written
  for the AWS machine specifically.
- `paper_draft.md` (repo root) — the paper's own section-by-section skeleton and
  status.
