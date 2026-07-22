# DiscreteFrechetMatching
An analysis of different discrete locally correct (retractable) Fréchet matching algorithms.

The discrite Fréchet distance is a measure of the similarity between two curves. It is defined as the minimum length of a leash required to connect a dog and its owner as they walk along their respective curves, without backtracking. The discrete Fréchet distance is a variant of the Fréchet distance that is computed using a discrete set of points along the curves, rather than continuous curves. When calculating the "locally correct" (also referred to as "retractable") variant of this distance, the matching is restricted so that the leash is kept as short as possible at any point in time.

This repository contains C++ implementations of two algorithm families for computing the discrete locally correct Fréchet distance and matching between two curves, and an experiment comparing them on runtime, memory usage, and machine-independent operation counts.

## Algorithms
In this project we are interested in 2 different algorithms for computing the discrete locally correct Fréchet matching between two curves: the **BBMS** algorithm and the **DijkstraPrims** algorithm:

### 1. BBMS
Based on the paper "Locally correct Fréchet matchings" by Buchin, K., Buchin, M., Meulemans, W., & Speckmann, B. (2012). "

#### Optimizations

BBMS includes two main optimizations to improve the runtime of the algorithm: _shortcuts_ and _dead path pruning_.

_Shortcuts_ are additional edges added to the tree structure used in the algorithm, which allow for faster queries of the nearest common ancestor (NCA) of two nodes. This can significantly reduce the time spent on NCA queries.

_Dead path pruning_ is a technique for removing nodes from the tree that are no longer relevant for future computations. Removing dead paths will reduce the number of steps needed to query the NCA of two nodes, which can further improve the runtime of the algorithm.

#### Versions

The current experiment (`algorithms/`) uses two versions of this algorithm:
- `BBMSCore`: BBMS without any optimizations (so no shortcuts or dead path pruning). Serves as a baseline.
- `BBMSInter`: BBMS with the shortcut optimization, but without dead path pruning.

Two further variants explored earlier in the project — `BBMS_dpp_instant` and `BBMS_dpp_stepwise`, which add dead path pruning on top of shortcuts, differing in how the pruning walk is performed — are out of scope for the current experiment. Their history is preserved on the `outdated-experiments` branch.

### 2. DijkstraPrims
Based on the paper "The Fréchet Distance Unleashed: Approximating a Dog with a Frog" by Sariel Har-Peled, Benjamin Raichel and Eliot W. Robson (2026). 

This algorithm is simple to implement and thus only has one version.

## Why C++, not Python

The algorithms were originally prototyped in Python (see the `outdated-experiments` branch), which is where their correctness was first established — easier to write and check against a reference dynamic-programming solution. The current experiment, however, needs to measure runtime, memory, and operation counts at curve sizes up to N=50,000 (i.e. grids of up to 2.5 billion cells), and to have those measurements reflect the algorithms' own behavior rather than interpreter overhead.

Python wasn't viable for that: its per-object memory overhead would dominate the memory measurements rather than reflecting the algorithms' actual data structures, and its interpreter overhead would both distort runtime comparisons and make the largest grid sizes impractically slow to even reach. The experiment's C++ implementations (`algorithms/`) compile with `-O2` and use flat, contiguous data structures sized directly to the input, so both runtime and memory numbers measure the algorithms, not the language runtime.

## File Structure

- `algorithms/` — the canonical C++ implementations used by the experiment:
    - `BBMS/`: `bbms_core.cpp`/`.h` and `bbms_inter.cpp`/`.h`.
    - `DP/`: `dijkstra_prims.cpp`/`.h`.
    - `common.h`: shared types (`Point`, `Curve`, `MatchingAndFrechetDistance`) and the NCA-tree matching-extraction helper.
    - `counters.h`/`counters.cpp`: operation-count instrumentation, compiled in via a `-DCOUNT_OPS` build (see below).
- `datasets/` — generated curve-pair files consumed by the experiment, one file per `(dataset, N)`. Three dataset kinds: `worst-case` (adversarial), `best-case` (identical curves), and `random`. Includes `generate_datasets.py`.
- `experiment/` — the experiment itself:
    - `runner.cpp`: runs one algorithm on one sample and prints one CSV line of results. Compiled twice — once plain (timing/memory), once with `-DCOUNT_OPS` (operation counts) — see `experiment/Makefile`.
    - `main.py`: the orchestrator that sweeps every `(dataset, N, sample, algorithm)` combination, handles resumability, timeouts, and per-algorithm failure walls, and writes results to `results/`.
    - `PLAN.md` / `PSEUDOCODE.md` / `HANDOFF.md`: the experimental design and reasoning, file-by-file pseudocode, and current project status, respectively.
    - `calibration/`: a calibration script (`calibrate.py`) and a step-by-step plan (`AWS_HANDOFF.md`) for sanity-checking the timeout and curve-size grid against real hardware before committing to the full run.
- `results/` — where `main.py` writes its output CSVs (`timing_memory.csv`, `opcounts.csv` per dataset). Empty until a run happens.

Earlier Python prototypes and the ad hoc, per-question experiments used during development have been moved to the `outdated-experiments` branch to keep this structure focused on the final experiment.

## The main experiment

The experiment compares `BBMSCore`, `BBMSInter`, and `DijkstraPrims` against each other across the three synthetic datasets above, at curve sizes ranging from N=500 to N=50,000, collecting three kinds of measurement:

- **Runtime and memory** (`timing_memory.csv`): wall-clock time and `getrusage`-based memory/fault/context-switch statistics, repeated a few times per sample for statistical stability.
- **Operation counts** (`opcounts.csv`): machine-independent counts — NCA-walk steps, shortcut hops, heap pushes/pops, cells processed — collected in a single deterministic run per sample, since these don't vary run to run.
- **Cross-algorithm agreement**: after each dataset's operation-count pass, every algorithm's reported Fréchet distance on the same instance is checked for agreement, flagging any disagreement as a warning.

The sweep is resumable (a restart skips already-completed rows) and self-limiting: once an algorithm hits a timeout or out-of-memory failure at some N, larger N values are skipped for that algorithm rather than retried, since cost only grows with N. The full reasoning behind the dataset design, sample counts, and failure-handling is in `experiment/PLAN.md`; current status is in `experiment/HANDOFF.md`.

**Building and running:**
```bash
cd experiment
make                        # builds runner.exe and runner_counted.exe
cd ..
python3 experiment/main.py  # runs the full sweep, writes results/<dataset>/*.csv
```

Before committing to a real multi-hour/day run on rented hardware, see `experiment/calibration/AWS_HANDOFF.md` for a step-by-step plan to calibrate the timeout and curve-size grid first.
