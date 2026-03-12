# DiscreteFrechetMatching
An analysis of different discrete locally correct Fréchet matching algorithms.

The discrite Fréchet distance is a measure of similarity between two curves. It is defined as the minimum length of a leash required to connect a dog and its owner as they walk along their respective curves, without backtracking. The discrete Fréchet distance is a variant of the Fréchet distance that is computed using a discrete set of points along the curves, rather than continuous curves. When calculating the "locally correct" (also referred to as "retractable") variant of this distance, the matching is restricted so that the leash is kept as short as possible at any point in time.

## File Structure
- `discreteDistance/`: Contains the "standard" implementation of the discrete Fréchet **distance** algorithm using dynamic programming.

- `DijkstraPrims/`: Contains the implementation of the discrete locally correct Fréchet **matching** algorithm, as described in the paper "The Fréchet Distance Unleashed: Approximating a Dog with a Frog" by Sariel Har-Peled, Benjamin Raichel and Eliot W. Robson (2026).

- `BBMS/`: Contains the implementation of the discrete locally correct Fréchet **matching** algorithm, as described in the paper "Locally correct Fréchet matchings" by Buchin, K., Buchin, M., Meulemans, W., & Speckmann, B. (2012). **Note: The current implementation of this algorithm does not yet include the shortcut optimization described in the paper.**

- `BBMS_basic/`: Contains a simplified version of the BBMS algorithm. This implementation does not include any shortcut optimizations and serves as a baseline for comparison with the optimized version in `BBMS/`. Mainly used for testing and debugging purposes.

- `correctness_comparison/`: Contains scripts for comparing the correctness of the different algorithms by running them on the same test curves (as defined in `test_data/`) and comparing their outputs.
    - `compare_matching.py`: Compares the matchings produced by BBMS to BBMS_basic, to ensure that the optimizations in BBMS do not change the resulting matching.
    - `compare_frechet_distance.py`: Compares the Fréchet distances produced by all three algorithms to the distance produced by the dynamic programming solution, to ensure that all algorithms are producing the correct distance.
    - `test_data/`: Contains test curves for use in the correctness comparison scripts. Each file contains multiple curves, with each curve represented by multiple lines of x and y coordinates. The curves are ordered so that the first two curves in the file form a pair to be compared, the next two curves form another pair, and so on.