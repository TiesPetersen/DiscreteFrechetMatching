# DiscreteFrechetMatching
An analysis of different discrete locally correct Fréchet matching algorithms.

The discrite Fréchet distance is a measure of similarity between two curves. It is defined as the minimum length of a leash required to connect a dog and its owner as they walk along their respective curves, without backtracking. The discrete Fréchet distance is a variant of the Fréchet distance that is computed using a discrete set of points along the curves, rather than continuous curves. When calculating the "locally correct" (also referred to as "retractable") variant of this distance, the matching is restricted so that the leash is kept as short as possible at any point in time.

## File Structure
- `discreteDistance/`: Contains the "standard" implementation of the discrete Fréchet **distance** algorithm using dynamic programming.
- `DijkstraPrim's/`: Contains the implementation of the discrete locally correct Fréchet **matching** algorithm, as described in the paper "The Fréchet Distance Unleashed: Approximating a Dog with a Frog" by Sariel Har-Peled, Benjamin Raichel and Eliot W. Robson (2026).
- `BBMS/`: Contains the implementation of the discrete locally correct Fréchet **matching** algorithm, as described in the paper "Locally correct Fréchet matchings" by Buchin, K., Buchin, M., Meulemans, W., & Speckmann, B. (2012). **Note: The current implementation of this algorithm does not yet include the shortcut optimization described in the paper.**