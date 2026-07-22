# Main Experiment: Design & Workflow

Status snapshot, not a paper section — this describes how the main comparison
experiment (BBMSCore, BBMSInter, DijkstraPrims, over worst-case/best-case/random
datasets) is built, run, and validated. `paper_draft.md` (repo root) describes the
paper itself; this describes the machinery that produces its data.

Numbers marked **(calibrate)** are starting proposals, not final — see Stage 3.

---

## 1. Scope

- **Algorithms**: `BBMSCore`, `BBMSInter`, `DijkstraPrims` (from `algorithms/`).
  `BBMSDppInstant`/`BBMSDppStepwise` excluded — still blocked on the `int → long long`
  conversion, out of scope for this pass.
- **Datasets**: worst-case (adversarial outlier), best-case (identical curves), random
  (independent uniform points). Real-world data deferred to later.
- **Curve shape**: `m = n = N` for all three datasets (aspect ratio is a separate,
  smaller robustness check, not part of this sweep — see `paper_draft.md` §6/§9/§10).
- **Metrics**: runtime, memory (RSS + getrusage fields), operation counts (NCA-walk
  steps split plain/shortcut, shortcuts written, heap pushes/pops). See §4 for the
  exact per-algorithm list — already agreed, not re-derived here.

---

## 2. Datasets

### 2.1 Size grid

`N ∈ {500, 1000, 2000, 4000, 7000, 11000, 18000, 28000, 40000, 50000}` — 10 points,
log-spaced (not linear), rounded to clean numbers (nearest thousand once past the low
end), shared across all three datasets and all three algorithms.

- **Log spacing, not linear**: an evenly-log-spaced grid weights a log-log regression
  fit evenly across the range; a linear grid wastes points at the expensive end and
  under-samples the cheap end where the baseline exponent is easiest to pin down.
- **Max N=50000 will very likely OOM `BBMSInter` and possibly `DijkstraPrims` before
  the top of the grid**: `50000² × 56 bytes ≈ 140 GB`, over the 128 GB target
  machine's budget. This is expected, not a problem — it's exactly what
  `status=oom` (§5.5) and the "stop testing larger N once a wall is hit" logic exist
  for. `BBMSCore`'s lighter `Node` (~24 bytes/cell, ~60 GB at N=50000) should make it
  to the top of the grid; the other two are expected to stop early, which is itself a
  real, useful finding, not noise to clean up.
- **This grid is a pre-AWS estimate, not measured on the real hardware** — subject
  to revision after the calibration run (Stage 3).

### 2.2 Samples per (dataset, N) — K

`K = 5` for all three datasets, uniformly. Originally proposed as a differentiated
3/3/5 then 5/5/10 (smaller for worst-case/best-case, where instance-to-instance
variance is expected to be small by construction, larger for random, where it's the
actual thing being characterized) — simplified to a single value across the board.
This trades some statistical power on the random dataset specifically (a real,
acknowledged cost, not a free simplification) for a simpler implementation and
orchestration. Revisit if the random dataset's across-sample spread (§5.1) turns out
too noisy to draw a confident conclusion from at K=5.

### 2.3 Repeats per sample — R

`R = 3` timing repeats per sample instance. Denoises OS/measurement jitter (same
instance, same curves, repeated wall-clock measurement) — this is the axis where
**min** is the correct aggregation (noise is one-directional; see §5.1). This is
independent from K (§2.2), which is the different-instances axis and gets
**mean/median**, not min — these two axes must not be aggregated the same way; see
the runtime methodology discussion this plan is based on.

R matters more at small N (measurement noise is a bigger fraction of a small
signal) than at large N (minutes-long runs dwarf any jitter) — cheap to keep uniform
at R=3 throughout rather than varying it by N.

### 2.4 Generation

- Single parameterized `datasets/generate_datasets.py`, not three separate scripts —
  produces into whichever of `worst-case/`, `best-case/`, `random/` it's asked for.
- One file per `(dataset, N)`, containing all `K` sample curve-pairs for that
  combination — matches the plan's own description.
- Real-world dataset: deferred. When picked up later, check what datasets the two
  cited papers (Buchin et al. 2012, Har-Peled/Raichel/Robson 2026) used, for
  comparability — noted in `paper_draft.md` already, repeated here so it isn't lost.

---

## 3. Workflow stages

1. **Implement.** Dataset generation, the experiment driver, the `#ifdef COUNT_OPS`
   instrumentation, the Makefile split (`algorithms/Makefile` builds algorithm
   objects; `experiment/Makefile` builds the driver, links against them).
2. **Smoke test on WSL (Windows laptop).** Not for real numbers — WSL2's
   virtualization layer and the laptop's own specs aren't the testbed that goes in
   the paper. This step exists solely to validate anything that's fundamentally
   Linux-kernel-dependent and *cannot* be checked on macOS at all: the `getrusage`
   unit handling (`ru_maxrss` is bytes on macOS, kilobytes on Linux — already a known
   trap), and whether `major_faults`/context-switch counters actually move under
   memory pressure the way they're supposed to on a real Linux kernel. Run one
   dataset, check the metrics look sane and are the right ones. Keep the repo on the
   native WSL filesystem, not a `/mnt/c/...` path.
3. **Calibration run on the real AWS machine.** Before committing to the full sweep:
   run the top 2-3 N values once each (no repeats) across all three algorithms, on
   the actual rented hardware. Use real numbers to sanity-check or revise the N grid,
   K, and R from §2 before spending a day of compute on a plan built from an
   extrapolation off different hardware (M1 Mac mini numbers, not AWS x86_64 vCPUs).
4. **Full run on AWS.** The real data collection. Expected to take on the order of a
   day; timeout + resumability (§5) mean an imperfect calibration doesn't turn into a
   week-long overrun — it just means some cells get flagged `timeout` instead of a
   completed value.
5. **Analysis.** Separate from this document — min/median aggregation per §5.1, the
   log-log fits, the memory-wall characterization, the op-count-driven §8 hypothesis
   check from `paper_draft.md`.

---

## 4. Metrics (recap — designed earlier, not re-derived here)

- **Both algorithm families**: cells processed. For BBMS, this is always exactly
  `m·n` — never instrumented, reported analytically, always 100%. For DijkstraPrims,
  it's the number of priority-queue pops before the target is reached — genuinely
  data-dependent, and the single most directly comparable "how much of the grid did
  this actually need" number across datasets.
- **BBMSCore**: NCA-walk steps (all "regular hops" — shortcut hops and shortcuts
  written are structurally always 0, never instrumented).
- **BBMSInter**: NCA-walk steps split into regular hops vs. shortcut hops, plus
  `shortcuts_written` (number of `.low`/`.high` field writes across the run) — the
  cost side of the shortcut mechanism, complementing walk-step savings.
- **DijkstraPrims**: heap pushes and heap pops, tracked separately (pops = cells
  settled before early termination; pushes = cells discovered, which can exceed pops).
- **Memory**: empirical RSS/getrusage behavior only, for now — reuses
  `memory_usage.cpp`'s design, extended to all three algorithms, run against whatever
  memory the machine actually has (no artificial capped budget). Measured from
  outside the algorithm call, so it doesn't need the `#ifdef COUNT_OPS` separation
  from §5.2 — that's only relevant to the op-count layer above.
  (The exact analytic footprint — `sizeof(Node) × m × n` for BBMS, entry count ×
  allocator overhead for DijkstraPrims — was considered as a second, machine-independent
  layer, but is left out for now. Revisit if the empirical RSS data alone turns out
  to be insufficient for the space-complexity claim.)

---

## 5. Execution design

### 5.1 Runtime aggregation — two axes, two different reducers

This is easy to get backwards, so it's spelled out explicitly:

- **Same instance, repeated trials (R, §2.3)** → **min**. Pure measurement noise,
  one-directional (only ever adds delay), so the minimum observed time is the best
  estimate of the true, noise-free cost for that specific instance.
- **Different instances, same N (K, §2.2)** → **mean or median**, never min. Taking
  the min across genuinely different random curve pairs doesn't denoise anything —
  it cherry-picks the easiest draw. Median is more robust to one outlier instance;
  mean aligns with the formal definition of average-case complexity as an expectation
  over the input distribution. Report both if they diverge noticeably — that's itself
  informative.
- The across-instance **spread** (not just the point estimate) is worth keeping, not
  discarding — e.g. if `BBMSCore`'s runtime varies more across worst-case samples
  than `BBMSInter`'s does, that's independent supporting evidence for the §8
  NCA-walk-amortization hypothesis in `paper_draft.md`, for free.

### 5.2 Op-counts: separate build, not merged into the timing/memory run

Two binaries from one source file, via `#ifdef COUNT_OPS` (see the actual sketch
worked out for `bbms_core.cpp` — same pattern applies to `bbms_inter.cpp` and
`dijkstra_prims.cpp`):

- **Uninstrumented build**: used for timing (§5.1) and RSS/getrusage measurement.
  Zero counting code compiled in at all — not just branched-around, actually absent
  from the binary — so it cannot contaminate either measurement.
- **`-DCOUNT_OPS` build**: used only for operation counts. Counts are deterministic
  given the input, so this build needs **1 run per sample, not R repeats** — cost is
  `R+1` runs total per sample instead of `2R`, i.e. ~33% overhead at R=3, not the ~2x
  originally assumed.
- Counters live in a global (`g_counters` in a small shared `counters.h`), reset once
  per algorithm call — chosen specifically to avoid threading a conditional parameter
  through every internal call site (rejected earlier for being too noisy at the call
  site). Single-threaded-only assumption, which holds for everything in this project.

### 5.3 Interleaving order

Nested loop order, outermost to innermost:

```
for dataset in [worst-case, best-case, random]:
    for N in size_grid:
        for sample in range(K):
            for repeat in range(R):
                for algorithm in [BBMSCore, BBMSInter, DijkstraPrims]:
                    run(...)
```

Two interleaving decisions here, at two different granularities:

- **Algorithm inside sample** (not sample inside algorithm): for a given N and
  sample, all three algorithms get measured close together in time rather than one
  algorithm finishing its entire sweep before the next starts. This is the direct
  fix for the cross-session ambient-load drift found empirically earlier in this
  project (DijkstraPrims measured ~2x slower across two different sessions,
  unrelated to any code change) — applied within a session, not just across them.
- **Algorithm innermost, inside repeat** (not repeat innermost, inside algorithm):
  each run is a fresh subprocess, but CPU L2/L3 cache and TLB state are hardware
  resources, not process-scoped — they can carry real "warmth" across process
  boundaries when two runs with a similar memory-access pattern happen back-to-back.
  Running the same algorithm's `R` repeats consecutively risks later repeats
  benefiting from cache state left behind by that same algorithm's own prior repeat,
  which has nothing to do with its true cost. Placing a *different* algorithm's run
  between each repeat breaks that up — a given algorithm's repeats are never
  adjacent to each other in execution order, only ever separated by the other two
  algorithms' runs.

### 5.4 Resumability

Append-and-skip, at the finest granularity, one CSV per dataset — the same pattern
already used by `cpp_adversarial`, `memory_usage`, and `loglog_scaling`, not a new
scheme:

- Each completed `(algorithm, N, sample, repeat)` row is appended to its dataset's
  CSV immediately after that run finishes.
- On startup, load the CSV, build a set of already-completed
  `(algorithm, N, sample, repeat)` tuples, and skip anything already present.
- No timestamped filenames, no "redo the whole dataset if it was interrupted" logic —
  a crash mid-dataset loses nothing; the next run resumes at the exact row it left
  off on. This achieves the crash-resilience the plan was originally asking for
  without discarding valid completed work just because the dataset wasn't 100% done.
- **The wall-detection state (§5.5) must be reconstructed from the CSV on resume, not
  just the completed-row set.** These two mechanisms don't compose automatically: if
  the in-memory `walls` dict is empty on every fresh start (as it would be if built
  from nothing), resuming after a crash that happened past an already-discovered wall
  would re-attempt those larger-N runs and burn a full timeout duration re-discovering
  a wall the previous run had already found. On startup, scan the existing CSV for any
  row with `status` in `{timeout, oom}` and seed `walls[algorithm]` from those directly,
  before processing any new runs — not just load the completed-row set and start
  `walls` empty.

### 5.5 Timeout & failure classification

- Each run is wrapped in `subprocess.run(..., timeout=...)` (**(calibrate)** the
  exact value — start high, e.g. 30-45 minutes, tightened after the calibration run).
- On `TimeoutExpired`: record the row with `status=timeout`.
- **OOM detection cannot rely on catching `bad_alloc` alone — on Linux, it typically
  won't fire.** Under default overcommit, a huge allocation like `BBMSInter`'s
  `std::vector<Node>` at N=50000 is usually satisfied *virtually* and the process is
  killed later by the kernel's OOM killer (`SIGKILL`) the moment it actually touches
  enough of that memory — no C++ exception is ever thrown, so the runner's own
  `catch (bad_alloc)` may simply never execute for the scenario this experiment most
  wants to observe. `bad_alloc` is still worth catching as a secondary path (it can
  fire on macOS/WSL during development, or for smaller over-limit allocations), but
  the orchestrator must independently detect a killed child process: after a
  `subprocess.run` call that did *not* raise `TimeoutExpired`, check whether
  `returncode` indicates termination by signal (negative on Unix) or whether stdout
  failed to parse as a valid CSV line, and classify that as `status=oom`. This is an
  *inference*, not a certainty — an unexplained kill during a high-memory run at the
  top of the N grid is the most parsimonious explanation in this context, but it
  isn't literally observing the OOM killer act. Worth confirming empirically during
  the WSL/calibration stages (§3) rather than assumed correct on paper alone.
- **Wall-skipping (stop testing larger N once a failure is seen) must trigger on any
  failure status, not just `timeout`.** Cost is monotonic in N regardless of *why* a
  run failed — an algorithm that cleanly reports `status=oom` at N=28000 is just as
  certain to fail again at N=40000 as one that timed out there. The original design
  only set the wall on `TimeoutExpired`; it needs to check `status in {timeout, oom}`
  uniformly, covering both the exception path and the returncode-based OOM inference
  above.
- Results carry an explicit `status` column (`ok` / `timeout` / `oom` / `error`), not
  a bare boolean — a timeout and an out-of-memory crash are scientifically different
  findings (one's about wall-clock cost, the other's central to the memory-wall
  story), and collapsing them into one `ok=False` would throw that distinction away
  at collection time, before analysis ever gets a chance to use it.

### 5.6 Cross-algorithm correctness check

All three algorithms record `frechet_distance` per run, but nothing was checking that
they actually agree with each other on the same instance — a real gap for a paper
whose whole point is comparing these algorithms, especially since the data to check
it is already being collected regardless. After each dataset's op-count pass
completes (one row per `(algorithm, N, sample)`, exactly what's needed — no repeats
to reconcile), group by `(N, sample)` and verify every algorithm that reports
`status=ok` on that instance reports the same `frechet_distance`, within the same
tolerance already used elsewhere in this project (`1e-9`). Log a warning (not a hard
failure — an actual disagreement is itself a finding worth investigating, not
something to crash the run over) for any mismatch. This piggybacks entirely on
already-collected data; it doesn't require any additional runs.

---

## 6. Open items / to calibrate

- [ ] Exact per-run timeout value (§5.5) — pick after seeing calibration-run numbers.
- [ ] Confirm N-grid ceiling (§2.1) against real AWS timing/memory behavior — may need
      to trim if the machine is slower than the M1 extrapolation assumed, or could
      safely extend if it's faster and memory allows.
- [x] Confirm the returncode-based OOM inference (§5.5) actually fires as expected —
      during the WSL smoke test and again during the AWS calibration run, deliberately
      trigger an OOM (e.g. a small `ulimit -v` cap) and check it's classified as
      `status=oom`, not left unhandled or misclassified. **WSL: confirmed 2026-07-22.**
      `ulimit -v` on a large-N allocation reliably triggers the runner's own
      `bad_alloc` catch → `status=oom` (this path never fired on macOS — see
      `HANDOFF.md`). Separately, feeding a killed/no-output subprocess directly into
      `main.py`'s `run_and_classify` confirmed the orchestrator's own inference
      branch (non-zero/empty-output → `oom`) also works. Still needs the AWS
      calibration-run recheck.
