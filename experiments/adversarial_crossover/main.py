"""
Experiment: Adversarial crossover search

Runs DijkstraPrims, BBMS_inter, and BBMS_dpp_instant on adversarial
(outlier-end) inputs only, pushing to larger N to locate memory walls
and algorithm crossover points.

Adversarial construction: curve1 in disk r=1, curve2 same disk but
final point at (D=1000, 0), forcing d(p_{n-1}, q_{m-1}) >> all others.

Resumable: existing CSV rows are loaded at startup; any (algorithm, N,
sample) triple that already has ok=True is skipped.

Interruptible: Ctrl+C finishes the current run then exits cleanly.

Wall detection: if a completed run's mean runtime is >= WALL_RATIO times
the previous N's mean, the algorithm is flagged and all remaining jobs
for it are skipped automatically.

Job ordering:
  1. DP jobs (N=7500, 8000 are the interesting region)
  2. Existing BBMS jobs (skipped by resume logic)
  3. New large-N BBMS jobs interleaved: BBMS_inter and BBMS_dpp_instant
     alternate at each N step so both make progress even if one hits a wall
  4. Extra targeted samples at crossover / memory-wall N values
"""

import csv
import os
import signal
import sys
import time
from collections import defaultdict

# Ensure project root is on the path regardless of working directory
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
os.chdir(_PROJECT_ROOT)

from polyline_datasets.generate_adversarial import generate_outlier_end_pair
from src.DijkstraPrims.main import DijkstraPrims_with_stats
from src.BBMS_inter.main import BBMS_inter
from src.BBMS_dpp_instant.main import BBMS_dpp_instant

RESULTS_DIR = "experiments/adversarial_crossover/results"
CSV_PATH = os.path.join(RESULTS_DIR, "results.csv")
SAMPLES = 3
ADV_R = 1.0
ADV_D = 1000.0

# Wall detection: if (actual ratio) / (expected O(N^2) ratio) >= WALL_EXCESS,
# the runtime grew far beyond what the algorithm's own scaling predicts,
# indicating a memory wall. Using expected O(N^2) as baseline so that
# normal O(N^2) or even O(N^3) scaling does not false-trigger.
WALL_EXCESS = 3.0

DP_NS    = [1000, 2000, 3000, 4000, 5000, 6000, 7000, 7500, 8000]
INTER_NS = [1000, 2000, 3000, 3500, 4000, 5000, 5500, 6000, 6500, 7000, 7500, 8000,
            8500, 9000, 9500, 10000, 10500, 11000, 11500, 12000]
DPP_NS   = [1000, 2000, 2500, 3000, 3500, 4000, 4500, 5000,
            5500, 6000, 6500, 7000, 7500, 8000]

_NEW_INTER = [8500, 9000, 9500, 10000, 10500, 11000, 11500, 12000]
_NEW_DPP   = [5500, 6000, 6500, 7000, 7500, 8000]

FIELDNAMES = ["algorithm", "N", "sample", "runtime_s", "frechet_dist", "ok"]

_interrupted = False


def _handle_sigint(sig, frame):
    global _interrupted
    _interrupted = True
    print("\nInterrupt received — finishing current run then exiting.", flush=True)


signal.signal(signal.SIGINT, _handle_sigint)


def append_row(row):
    write_header = not os.path.exists(CSV_PATH)
    with open(CSV_PATH, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDNAMES)
        if write_header:
            w.writeheader()
        w.writerow(row)


def load_csv():
    """Return list of completed rows with runtime data."""
    rows = []
    if not os.path.exists(CSV_PATH):
        return rows
    with open(CSV_PATH, newline="") as f:
        for r in csv.DictReader(f):
            if r["ok"] == "True":
                rows.append(dict(algorithm=r["algorithm"],
                                 N=int(r["N"]),
                                 sample=int(r["sample"]),
                                 runtime_s=float(r["runtime_s"])))
    return rows


def mean_runtime(rows, alg, N):
    times = [r["runtime_s"] for r in rows if r["algorithm"] == alg and r["N"] == N]
    return sum(times) / len(times) if times else None


def check_wall(rows, alg, N):
    """Return True if (alg, N) grew far beyond expected O(N^2) scaling.

    Compares (actual ratio) / (expected O(N^2) ratio) against WALL_EXCESS so
    that normal quadratic or mildly super-quadratic growth does not trigger.
    """
    cur_mean = mean_runtime(rows, alg, N)
    if cur_mean is None:
        return False
    prev_Ns = sorted(set(r["N"] for r in rows if r["algorithm"] == alg and r["N"] < N))
    if not prev_Ns:
        return False
    prev_N = prev_Ns[-1]
    prev_mean = mean_runtime(rows, alg, prev_N)
    if not prev_mean:
        return False
    actual_ratio   = cur_mean / prev_mean
    expected_ratio = (N / prev_N) ** 2          # baseline: pure O(N^2)
    excess         = actual_ratio / expected_ratio
    if excess >= WALL_EXCESS:
        print(f"  [WALL] {alg} N={N}: {cur_mean:.0f}s is {actual_ratio:.1f}× "
              f"N={prev_N} ({prev_mean:.0f}s), {excess:.1f}× above O(N²) expectation"
              f" — skipping larger N.", flush=True)
        return True
    return False


def detect_walls_in_existing_data(rows):
    """Scan existing CSV data and return dict {algorithm: wall_N}.

    wall_N is the first N where a memory wall was detected. Jobs for that
    algorithm at N >= wall_N will be skipped; lower-N jobs still run.
    """
    walls = {}  # algorithm -> wall_N
    algs = set(r["algorithm"] for r in rows)
    for alg in algs:
        Ns = sorted(set(r["N"] for r in rows if r["algorithm"] == alg))
        for i in range(1, len(Ns)):
            if check_wall(rows, alg, Ns[i]):
                walls[alg] = Ns[i]
                break
    return walls


def run_one(algorithm_name, fn, N, sample):
    seed = sample * 9999 + N
    c1, c2 = generate_outlier_end_pair(N, N, r=ADV_R, D=ADV_D, seed=seed)
    try:
        t0 = time.perf_counter()
        result = fn(c1, c2)
        elapsed = time.perf_counter() - t0
        fd = result[1]
        row = dict(algorithm=algorithm_name, N=N, sample=sample,
                   runtime_s=round(elapsed, 4), frechet_dist=round(fd, 4), ok=True)
        print(f"  {algorithm_name:22s} N={N:5d} s={sample}  {elapsed:8.2f}s  fd={fd:.3f}", flush=True)
    except MemoryError:
        row = dict(algorithm=algorithm_name, N=N, sample=sample,
                   runtime_s=-1, frechet_dist=-1, ok=False)
        print(f"  {algorithm_name:22s} N={N:5d} s={sample}  OOM", flush=True)
    except Exception as e:
        row = dict(algorithm=algorithm_name, N=N, sample=sample,
                   runtime_s=-1, frechet_dist=-1, ok=False)
        print(f"  {algorithm_name:22s} N={N:5d} s={sample}  ERROR: {e}", flush=True)
    append_row(row)


def build_jobs():
    jobs = []

    # 1. DP jobs
    for N in DP_NS:
        for s in range(SAMPLES):
            jobs.append(("DijkstraPrims", DijkstraPrims_with_stats, N, s))

    # 2. Existing BBMS jobs (already done, skipped by resume logic)
    for N in [n for n in INTER_NS if n <= 8000]:
        for s in range(SAMPLES):
            jobs.append(("BBMS_inter", BBMS_inter, N, s))
    for N in [n for n in DPP_NS if n <= 5000]:
        for s in range(SAMPLES):
            jobs.append(("BBMS_dpp_instant", BBMS_dpp_instant, N, s))

    # 3. New large-N jobs interleaved round by round
    for i in range(max(len(_NEW_INTER), len(_NEW_DPP))):
        if i < len(_NEW_INTER):
            for s in range(SAMPLES):
                jobs.append(("BBMS_inter", BBMS_inter, _NEW_INTER[i], s))
        if i < len(_NEW_DPP):
            for s in range(SAMPLES):
                jobs.append(("BBMS_dpp_instant", BBMS_dpp_instant, _NEW_DPP[i], s))

    # 4. Extra targeted samples at crossover / wall N values
    extra = [
        ("DijkstraPrims",    DijkstraPrims_with_stats, 7000, [3, 4]),
        ("DijkstraPrims",    DijkstraPrims_with_stats, 7500, [3, 4]),
        ("DijkstraPrims",    DijkstraPrims_with_stats, 8000, [3, 4]),
        ("BBMS_inter",       BBMS_inter,               7500, [3, 4]),
        ("BBMS_inter",       BBMS_inter,               8000, [3, 4]),
        ("BBMS_inter",       BBMS_inter,               8500, [3, 4]),
        ("BBMS_dpp_instant", BBMS_dpp_instant,         4500, [3, 4]),
        ("BBMS_dpp_instant", BBMS_dpp_instant,         5000, [3, 4]),
        ("BBMS_dpp_instant", BBMS_dpp_instant,         5500, [3, 4]),
    ]
    for alg, fn, N, samples in extra:
        for s in samples:
            jobs.append((alg, fn, N, s))

    return jobs


def main():
    os.makedirs(RESULTS_DIR, exist_ok=True)

    jobs = build_jobs()
    rows = load_csv()
    done = {(r["algorithm"], r["N"], r["sample"]) for r in rows}
    pending = [(alg, fn, N, s) for alg, fn, N, s in jobs if (alg, N, s) not in done]

    # Detect walls in data already collected
    walls = detect_walls_in_existing_data(rows)
    if walls:
        print(f"  [WALL] Already walled from previous runs: "
              + ", ".join(f"{a} at N={n}" for a, n in walls.items()), flush=True)

    print(f"Total jobs: {len(jobs)}  |  Already done: {len(done)}  |  "
          f"Remaining: {len(pending)}", flush=True)

    for alg, fn, N, s in pending:
        if _interrupted:
            print("Stopping early — progress saved to CSV.", flush=True)
            sys.exit(0)
        if alg in walls and N >= walls[alg]:
            print(f"  [SKIP] {alg} N={N} s={s} — at or past memory wall (N={walls[alg]})", flush=True)
            continue
        run_one(alg, fn, N, s)
        # Re-check wall after each completed run
        rows = load_csv()
        if alg not in walls and check_wall(rows, alg, N):
            walls[alg] = N

    print("\nAll runs complete.")


if __name__ == "__main__":
    main()
