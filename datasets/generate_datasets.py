"""
Generates the worst-case, best-case, and random curve datasets used by the main
experiment. One file per (dataset, N), each containing K sample curve pairs.

Run from the project root:
    python3 datasets/generate_datasets.py
"""

import hashlib
import os
import random

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATASETS_DIR = os.path.join(PROJECT_ROOT, "datasets")

SEED = 1234 # random seed for reproducibility of the datasets

GRID = [500, 830, 1400, 2300, 3900, 6500, 11000, 18000, 30000, 50000]
K = 5  # number of sample curve pairs per (dataset, N), same for all three datasets

OUTLIER_DISTANCE = 1000.0  # worst-case: fixed distance of the outlier point
DISK_RADIUS = 1.0          # worst-case: radius of the disk the other points are drawn from


def deterministic_seed(*parts):
    """A per-sample seed that's reproducible across runs and machines."""
    key = "|".join(str(part) for part in parts).encode()
    return int(hashlib.sha256(key).hexdigest(), 16)


def random_point_in_disk(rng, radius):
    """A uniformly random point inside a disk of the given radius, centered at the origin."""
    while True:
        x = rng.uniform(-radius, radius)
        y = rng.uniform(-radius, radius)
        if x * x + y * y <= radius * radius:
            return (x, y)


def random_point(rng, scale=10.0):
    """A uniformly random point in a square of the given side length, centered at the origin."""
    return (rng.uniform(-scale, scale), rng.uniform(-scale, scale))


def generate_worst_case(n, seed):
    """p: n points in a disk. q: the same, but its last point is a distant outlier.
    This is the adversarial construction meant to defeat DijkstraPrims' sparse pruning."""
    rng = random.Random(seed)
    p = [random_point_in_disk(rng, DISK_RADIUS) for _ in range(n)]
    q = [random_point_in_disk(rng, DISK_RADIUS) for _ in range(n - 1)]
    q.append((OUTLIER_DISTANCE, 0.0))
    return p, q


def generate_best_case(n, seed):
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
    "worst-case": generate_worst_case,
    "best-case": generate_best_case,
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
        for n in GRID:
            out_path = os.path.join(out_dir, f"N_{n}.txt")
            if os.path.exists(out_path):
                print(f"  [SKIP] {dataset_name} N={n} (already generated)")
                continue

            samples = []
            for sample_idx in range(K):
                # Deterministic per (dataset, N, sample, SEED) so results are reproducible.
                seed = deterministic_seed(dataset_name, n, sample_idx, SEED)
                samples.append(generator(n, seed))

            write_dataset_file(out_path, samples)
            print(f"  {dataset_name:12s} N={n:6d}  wrote {len(samples)} samples")

    print("\nAll datasets generated.")


if __name__ == "__main__":
    main()
