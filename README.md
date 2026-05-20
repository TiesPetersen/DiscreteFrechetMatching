# DiscreteFrechetMatching
An analysis of different discrete locally correct (retractable) Fréchet matching algorithms.

The discrite Fréchet distance is a measure of the similarity between two curves. It is defined as the minimum length of a leash required to connect a dog and its owner as they walk along their respective curves, without backtracking. The discrete Fréchet distance is a variant of the Fréchet distance that is computed using a discrete set of points along the curves, rather than continuous curves. When calculating the "locally correct" (also referred to as "retractable") variant of this distance, the matching is restricted so that the leash is kept as short as possible at any point in time.

This repository contains implementations of two different algorithms for computing the discrete locally correct Fréchet distance and matching between two curves, as well as scripts for testing their correctness and benchmarking their performance.

### Visualizations
Enjoy some visualizations of the concepts and algorithms involved in this project:

![Shortcut Creation Case Distinction](figures/case_distinction6.drawio.png)
*Case distinction for when and where to create shortcuts for a new node.*

![Possible Shortcut Extensions](figures/shortcut_extension.drawio.png)
*Possible shortcut extensions for a node, given a dead path and incoming shortcuts.*

TODO: redo this visulalization

## Algorithms
In this project we are interested in 2 different algorithms for computing the discrete locally correct Fréchet matching between two curves: the **BBMS** algorithm and the **DijkstraPrims** algorithm:

### 1. BBMS
Based on the paper "Locally correct Fréchet matchings" by Buchin, K., Buchin, M., Meulemans, W., & Speckmann, B. (2012). "

#### Optimizations

BBMS includes two main optimizations to improve the runtime of the algorithm: _shortcuts_ and _dead path pruning_.

_Shortcuts_ are additional edges added to the tree structure used in the algorithm, which allow for faster queries of the nearest common ancestor (NCA) of two nodes. This can significantly reduce the time spent on NCA queries.

_Dead path pruning_ is a technique for removing nodes from the tree that are no longer relevant for future computations. Removing dead paths will reduce the number of steps needed to query the NCA of two nodes, which can further improve the runtime of the algorithm.


#### Versions

In the repository, we use 4 versions of this algorithm, based on which optimizations are included: 
- `BBMS_core`: BBMS without any optimizations (so no shortcuts or dead path pruning). Serves as a baseline for debugging and development purposes.
- `BBMS_inter`: BBMS with shortcut optimization, but without dead path pruning.
- `BBMS_dpp_instant`: BBMS with both shortcut optimization and dead path pruning. When dead path pruning is done, it jumps directly to the root of the dead path and only cleans up the shortcuts there.
- `BBMS_dpp_stepwise`: BBMS with both shortcut optimization and dead path pruning. When dead path pruning is done, it walks through the dead path step by step and cleans up shortcuts along the way.


### 2. DijkstraPrims
Based on the paper "The Fréchet Distance Unleashed: Approximating a Dog with a Frog" by Sariel Har-Peled, Benjamin Raichel and Eliot W. Robson (2026). 

This algorithm is simple to implement and thus only has one version.

## File Structure

- `experiments` : Contains scripts for running experiments to compare the performance of the different algorithms. Each subdirectory contains a separate experiment, with its own main script and any necessary helper functions or data.
    - `adversarial_crossover/`: See [Adversarial crossover experiment](#adversarial-crossover-experiment) below for a description of this experiment.
    - `cpp_adversarial/`: See [C++ adversarial experiment](#c-adversarial-experiment) below for a description of this experiment.
- `figures` : Contains figures/diagrams used during development, in the README, or elsewhere. 
- `polyline_datasets/`: Contains scripts for generating and loading datasets of polylines for use in testing and benchmarking the algorithms. Also includes the generated datasets themselves.
- `src_python/`: Contains the **Python** implementations of the different algorithms for computing the discrete locally correct Fréchet distance and matching, as well as any necessary helper functions and classes.
- `src_cpp/`: Contains the **C++** implementations of the different algorithms for computing the discrete locally correct Fréchet distance and matching, as well as any necessary helper functions and classes.
- `tests` : Contains scripts for testing the correctness of the different **Python** implementations by comparing their outputs on the same test curves.
    - `compare_matching.py`: Compares the matchings between BBMS_core, BBMS_inter and BBMS, to ensure that the shortcut optimizations in BBMS do not change the resulting matching.
    - `compare_frechet_distance.py`: Compares the Fréchet distances produced by all three algorithms to the distance produced by the dynamic programming solution, to ensure that all algorithms are producing the correct distance.


## C++ implementations

`src_cpp/` contains C++ reimplementations of all five algorithms, intended for benchmarking at input sizes that are impractical in Python. The implementations mirror the Python versions in algorithmic behaviour and compile with `-O2` for efficient memory access patterns.

A `dp_check` reference oracle (standard O(nm) DP) is also included for correctness verification.

**Building and running:**
```bash
cd src_cpp
make              # builds verify.exe and benchmark.exe
make run          # builds and runs verify.exe (correctness check against DP oracle)
make clean        # removes object files and executables
```

`benchmark.exe` is invoked as:
```
benchmark.exe <AlgorithmName> <N> <sample>
```
and prints one CSV line: `algo,N,sample,runtime_s,frechet_dist,ok`. `verify.exe` runs all algorithms on random inputs and reports pass/fail counts.

## Experiments
Below is a description of the experiments included in the `experiments/` directory. Each experiment is contained in its own subdirectory, with a main script that can be run to execute the experiment.

### Adversarial crossover experiment
The `adversarial_crossover` experiment benchmarks DijkstraPrims, BBMS_inter, and BBMS_dpp_instant on adversarial "outlier-end" inputs using the Python implementations. Each test pair consists of N points sampled uniformly in a unit disk for curve 1, with curve 2 being the same except its final point is replaced by a distant outlier at (1000, 0).

The experiment is resumable: results are stored to a CSV and any already-completed (algorithm, N, sample) triple is skipped on restart. If an algorithm's mean runtime exceeds 3× the O(N²) prediction it is flagged as hitting a "memory wall" and larger N values are skipped for that algorithm. A companion `plot.py` script generates runtime, speedup-ratio, and log-log scaling plots from the CSV.

```bash
python -m experiments.adversarial_crossover.main
python -m experiments.adversarial_crossover.plot
```

### C++ adversarial experiment
The `cpp_adversarial` experiment is the C++-backed counterpart of the adversarial crossover experiment. It uses the same adversarial construction and wall-detection logic, but orchestrates `src_cpp/benchmark.exe` via subprocess, which allows testing much larger input sizes. Memory wall thresholds are estimated theoretically from per-cell byte costs of each algorithm's data structures, and are overlaid on the generated plots.

Build `src_cpp/benchmark.exe` before running:

```bash
cd src_cpp && make benchmark.exe
python -m experiments.cpp_adversarial.main
python -m experiments.cpp_adversarial.plot
```


---


### Run experiments
To run the example experiment (or any other experiment), please run the following command from the root directory of the repository:

```bash
python -m experiments.example.main
```

_Note: You can replace "example" with the name of any other experiment subdirectory to run that experiment instead (e.g. `python -m experiments.adversarial_crossover.main`)._


## Tests

TODO