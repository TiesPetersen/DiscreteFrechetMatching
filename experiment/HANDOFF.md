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

## Status: implementation done, smoke-tested on macOS, not yet run for real

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

## What's next: the WSL smoke test (Stage 2 in `PLAN.md`)

Three things could **not** be verified on macOS and need checking on WSL before
trusting them on the real AWS run:

1. Whether `major_faults`/`block_input_ops`/`block_output_ops`/context-switch
   counters actually respond to real memory pressure. Expected to read flat zero on
   macOS regardless (its memory compressor intercepts pressure before classic page
   faults) — this is the whole reason Linux is needed to check it at all.
2. The Linux branch of the `ru_maxrss` unit conversion in `runner.cpp`
   (`maxrss_to_mb`) — only the macOS branch has actually executed so far.
3. Whether a real OOM gets classified as `status=oom` by `main.py`'s
   `run_and_classify`. Tried forcing this on macOS via `ulimit -v` — doesn't work
   there (`setrlimit failed`) — needs WSL's/Linux's actual memory-limiting tools.

After WSL: a calibration run on the real AWS machine (top few N values, no repeats,
to sanity-check the N grid/timeout value against real hardware — both are currently
estimates extrapolated from an M1 Mac mini), then the full run, then analysis.

## Where to look for more detail

- `experiment/PLAN.md` — the actual experimental design and reasoning (dataset
  sizing, sample counts, aggregation methodology, interleaving order, resumability,
  timeout/failure handling).
- `experiment/PSEUDOCODE.md` — file-by-file pseudocode for everything (now
  implemented for real, but this is still the clearest single-document overview).
- `paper_draft.md` (repo root) — the paper's own section-by-section skeleton and
  status.
