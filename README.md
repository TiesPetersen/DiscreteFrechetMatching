# DiscreteFrechetMatching
An analysis of different discrete locally correct (retractable) Fréchet matching algorithms.

This repository contains C++ implementations of two algorithm families for computing the discrete locally correct Fréchet distance and matching between two curves, and an experiment comparing them on runtime, memory usage, and machine-independent operation counts.

The discrite Fréchet distance is a measure of the similarity between two curves. It is defined as the minimum length of a leash required to connect a dog and its owner as they walk along their respective curves, without backtracking. The discrete Fréchet distance is a variant of the Fréchet distance that is computed using a discrete set of points along the curves, rather than continuous curves. When calculating the "locally correct" (also referred to as "retractable") variant of this distance, the matching is restricted so that the leash is kept as short as possible at any point in time.

## Algorithms
In this project we are interested in 2 different algorithms for computing the discrete locally correct Fréchet matching between two curves: the **BBMS** algorithm and the **DijkstraPrim's** algorithm:

### 1. BBMS
Based on the paper "Locally correct Fréchet matchings" by Buchin, K., Buchin, M., Meulemans, W., & Speckmann, B. (2012). "

#### Optimizations

BBMS includes two main optimizations to improve the runtime of the algorithm: _shortcuts_ and _dead path pruning_.

_Shortcuts_ are additional edges added to the tree structure used in the algorithm, which allow for faster queries of the nearest common ancestor (NCA) of two nodes. This can significantly reduce the time spent on NCA queries.

_Dead path pruning_ is a technique for removing nodes from the tree that are no longer relevant for future computations. Removing dead paths will reduce the number of steps needed to query the NCA of two nodes, which can further improve the runtime of the algorithm.

#### Versions

The current experiment (`algorithms/`) uses two versions of this algorithm:
- `BBMS_Core`: BBMS without any optimizations (so no shortcuts or dead path pruning). Serves as a baseline.
- `BBMS_Inter`: BBMS with the shortcut optimization, but without dead path pruning.
- `BBMS_Dpp_Stepwise`: BBMS with both the shortcut and dead path pruning optimizations. The dead path pruning is implemented such that shortcuts are removed step by step.
- `BBMS_Dpp_Instant`: BBMS with both the shortcut and dead path pruning optimizations. The dead path pruning is implemented such that only a few shortcuts are removed instantly.

### 2. DijkstraPrims
Based on the paper "The Fréchet Distance Unleashed: Approximating a Dog with a Frog" by Sariel Har-Peled, Benjamin Raichel and Eliot W. Robson (2026). 

This algorithm is simple to implement and thus only has one version.

## Why C++, not Python

The algorithms were first prototyped in Python (see the `outdated-experiments` branch) to work out their correctness, but Python isn't suitable for the actual experiment: at the curve sizes we care about (up to N=50,000, meaning grids of up to 2.5 billion cells), Python's per-object memory overhead and interpreter overhead would dominate the runtime and memory measurements instead of reflecting the algorithms themselves, and would make the largest sizes impractically slow to even reach. The C++ implementations in `algorithms/` compile with `-O2` and use flat, contiguous data structures sized directly to the input, so the numbers the experiment reports measure the algorithms, not the language.

## File Structure

- `algorithms/` -> the C++ implementations, used by both the experiment and `tests/`:
    - `BBMS/`: `bbms_core`, `bbms_inter`, `bbms_dpp_instant`, `bbms_dpp_stepwise` (`.cpp`/`.h` each), plus `bbms_dpp_common.h` for the tree/shortcut logic shared by the two dpp variants.
    - `DP/`: `dijkstra_prims.cpp`/`.h`.
    - `common.h`: shared types (`Point`, `Curve`, `MatchingAndFrechetDistance`) and the NCA-tree matching-extraction helper.
    - `counters.h`/`counters.cpp`: operation-count instrumentation, compiled in via a `-DCOUNT_OPS` build (see below).
    - `parent_trace.h`/`parent_trace.cpp`: records each algorithm's per-cell parent choice, compiled in via a `-DTRACE_TEST` build (see below).
- `tests/` -> correctness verification for the algorithms, independent of the experiment's timing/memory measurements. `run_tests.sh` builds and runs all of the below:
    - `dynamic_programming_check`: checks every algorithm's distance and matching against an independent, deliberately naive O(mn) dynamic programming reference (`reference/`), on random curves.
    - `matching_check`: checks that all BBMS variants return byte-identical matchings on the same input.
    - `parent_trace_check`: checks that all BBMS variants make the identical parent choice at every grid cell, pinpointing the exact cell if one diverges.
- `datasets/` -> generated curve-pair files consumed by the experiment, split into `synthetic/` and `real-world/` (mirroring `experiment/`'s split below):
    - `synthetic/`: one file per `(dataset, N)`, generated by `generate_datasets.py`. Dataset kinds: `identical` (p == q), `random` (independent points), `outlier` (same distribution as `random`, but one point moved far away -- adversarial specifically for `DijkstraPrims`'s early termination), and `alternating` (adversarial for `DijkstraPrims`'s priority-queue size specifically, engineered to drive it toward its theoretical N²/2 maximum).
    - `real-world/`: curve pairs sampled from public trajectory datasets (Geolife, Pigeons, Drifter) and the SETH-hardness benchmark used in the Fréchet distance literature (OV), generated by `generate_real_world_datasets.py` from raw downloads expected under `external_datasets/` (gitignored). Unlike the synthetic sets, curves here have independent, unequal lengths and no shared N grid, and each dataset's pairs are split across multiple `part_NNN.txt` files to stay under GitHub's 100MB per-file limit.
- `experiment/` -> the experiment itself, split into two orchestrators that share the same C++ runner:
    - `runner.cpp`: runs one algorithm on one sample and prints one CSV line of results. Compiled twice — once plain (timing/memory), once with `-DCOUNT_OPS` (operation counts) — see `experiment/Makefile`. Shared by both orchestrators below; it already supports unequal-length curve pairs, though it only ever reports a single `N` (= the first curve's length) for its own logging purposes.
    - `synthetic/main.py`: sweeps every `(dataset, N, sample, algorithm)` combination against `datasets/synthetic/`, handles resumability, timeouts, and per-algorithm failure walls (skipping larger N once an algorithm fails at a smaller one, since cost is monotonic in N there), and writes results to `results/` (or wherever `RESULTS_DIR` is pointed for a given run, e.g. `results_calibration_300/`).
    - `real-world/main.py`: sweeps every `(dataset, pair, algorithm)` combination against `datasets/real-world/` and writes results to `results_real_world/`. No cross-pair walling (pairs aren't ordered by size the way N values are, so a later pair failing wouldn't imply anything about an earlier one), and both passes are timeout-bounded (real curves have shown far worse per-cell behavior than synthetic ones for `BBMSCore`/`BBMSInter`, so the op-count pass isn't left uncapped here the way it is for the synthetic run).
- `analysis/` -> reads a results folder and writes a single self-contained interactive HTML report:
    - `app_synthetic.py`: for `synthetic/main.py`'s output -- one line per algorithm/dataset across the shared N grid.
    - `app_real_world.py`: for `real-world/main.py`'s output -- a log-scale scatter of `cells` (m×n) vs. each attribute, one point per pair, since there's no shared N grid to plot a line across; failed pairs (timeout/oom) still show up as marker-only points along the bottom of the plot.
- `results/` -> where `synthetic/main.py` writes its output CSVs (`timing_memory.csv`, `opcounts.csv` per dataset). Empty until a run happens.
- `results_real_world/` -> where `real-world/main.py` writes its output CSVs. Empty until a run happens.

Earlier Python prototypes and the ad hoc, per-question experiments used during development have been moved to the `outdated-experiments` branch to keep this structure focused on the final experiment.

## The main experiment

The experiment compares `BBMSCore`, `BBMSInter`, `BBMSDppInstant`, `BBMSDppStepwise`, and `DijkstraPrims` against each other across the synthetic datasets above, at curve sizes ranging from N=500 to N=50,000, collecting three kinds of measurement.

- **Runtime and memory** (`timing_memory.csv`): wall-clock time and `getrusage`-based memory/fault/context-switch statistics, repeated a few times per sample for statistical stability.
- **Operation counts** (`opcounts.csv`): machine-independent counts — NCA-walk steps, shortcut hops, heap pushes/pops, cells processed — collected in a single deterministic run per sample, since these don't vary run to run.
- **Cross-algorithm agreement**: after each dataset's operation-count pass, every algorithm's reported Fréchet distance on the same instance is checked for agreement, flagging any disagreement as a warning.

That agreement check only compares final answers on the datasets actually used in the experiment. Independent, algorithm-internal correctness verification lives separately in `tests/` (see above) and is not part of the timed run.

The sweep is resumable (a restart skips already-completed rows) and self-limiting: once an algorithm hits a timeout or out-of-memory failure at some N, larger N values are skipped for that algorithm rather than retried, since cost only grows with N.

**Building and running:**
```bash
cd experiment
make                                   # builds runner.exe and runner_counted.exe, shared by both orchestrators
cd ..
python3 experiment/synthetic/main.py   # runs the synthetic sweep, writes results/<dataset>/*.csv
python3 experiment/real-world/main.py  # runs the real-world sweep, writes results_real_world/<dataset>/*.csv
```

The real-world sweep additionally requires `datasets/real-world/*/part_*.txt` to already exist -- generate them with `python3 datasets/real-world/generate_real_world_datasets.py`, which itself expects the raw downloads under `external_datasets/` (gitignored; not included in this repo).

## Running the tests

```bash
cd tests
./run_tests.sh
```

This builds and runs `dynamic_programming_check`, `matching_check`, and `parent_trace_check` in sequence, each on hundreds of random curves, printing a pass/fail summary with timing for each. A non-zero exit code means at least one check failed.
