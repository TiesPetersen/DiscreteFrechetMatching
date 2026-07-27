"""
Generates the identical, random, and outlier curve datasets used by the main
experiment. One file per (dataset, N), each containing K sample curve pairs.

Run from the project root:
    python3 datasets/generate_datasets.py
"""

import hashlib
import os
import random

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATASETS_DIR = os.path.join(PROJECT_ROOT, "datasets")

SEED = 42069 # random seed for reproducibility of the datasets

GRID = [500, 830, 1400, 2300, 3900, 6500, 11000, 18000, 30000, 50000]
K = 5  # default number of sample curve pairs per (dataset, N)
K_OVERRIDES = {
    "random": 10,
}

OUTLIER_DISTANCE = 1000.0  # outlier: fixed distance of the outlier point


def deterministic_seed(*parts):
    """A per-sample seed that's reproducible across runs and machines."""
    key = "|".join(str(part) for part in parts).encode()
    return int(hashlib.sha256(key).hexdigest(), 16)


def random_point(rng, scale=10.0):
    """A uniformly random point in a square of the given side length, centered at the origin."""
    return (rng.uniform(-scale, scale), rng.uniform(-scale, scale))


def generate_outlier(n, seed):
    """p: n random points, same distribution as identical/random. q: the same, but
    its last point is a distant outlier. This is the adversarial construction meant
    to defeat DijkstraPrims' sparse pruning: every cell outside the last column is
    cheap, so it must exhaust almost the entire grid before it can ever pop a cell
    in the one expensive column, defeating its early termination."""
    rng = random.Random(seed)
    p = [random_point(rng) for _ in range(n)]
    q = [random_point(rng) for _ in range(n - 1)]
    q.append((OUTLIER_DISTANCE, 0.0))
    return p, q


def generate_identical(n, seed):
    """p: n random points. q: identical to p. The Fréchet distance is always 0,
    achieved by matching each point to itself along the diagonal."""
    rng = random.Random(seed)
    p = [random_point(rng) for _ in range(n)]
    q = list(p)
    return p, q


def generate_random(n, seed):
    """p and q: independent random points, unrelated to each other."""
    rng = random.Random(seed)
    p = [random_point(rng) for _ in range(n)]
    q = [random_point(rng) for _ in range(n)]
    return p, q


GENERATORS = {
    "outlier": generate_outlier,
    "identical": generate_identical,
    "random": generate_random,
}


def write_dataset_file(path, samples):
    """samples: list of (p, q) curve pairs. See PSEUDOCODE.md for the file format."""
    with open(path, "w") as f:
        f.write(f"{len(samples)}\n")
        for p, q in samples:
            f.write(f"{len(p)}\n")
            for x, y in p:
                f.write(f"{x} {y}\n")
            f.write(f"{len(q)}\n")
            for x, y in q:
                f.write(f"{x} {y}\n")


def main():
    for dataset_name, generator in GENERATORS.items():
        out_dir = os.path.join(DATASETS_DIR, dataset_name)
        k = K_OVERRIDES.get(dataset_name, K)
        for n in GRID:
            out_path = os.path.join(out_dir, f"N_{n}.txt")
            if os.path.exists(out_path):
                print(f"  [SKIP] {dataset_name} N={n} (already generated)")
                continue

            samples = []
            for sample_idx in range(k):
                # Deterministic per (dataset, N, sample, SEED) so results are reproducible.
                seed = deterministic_seed(dataset_name, n, sample_idx, SEED)
                samples.append(generator(n, seed))

            write_dataset_file(out_path, samples)
            print(f"  {dataset_name:12s} N={n:6d}  wrote {len(samples)} samples")

    print("\nAll datasets generated.")


if __name__ == "__main__":
    main()
