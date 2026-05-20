"""
Experiment: C++ adversarial crossover

Runs DijkstraPrims, BBMSCore, and BBMSInter (C++ implementations) on adversarial
outlier-end inputs at increasing N to find crossover points and memory walls.

Same adversarial construction as the Python experiment:
  curve1: N points in disk r=1, curve2: N-1 points in same disk + (D=1000, 0)

Resumable: existing CSV rows are skipped on startup.
Interruptible: Ctrl+C finishes the current run then exits.
Wall detection: excess-based (same logic as Python experiment, WALL_EXCESS=3.0).
"""

import csv
import os
import signal
import subprocess
import sys
import time
from collections import defaultdict

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(_PROJECT_ROOT)

BENCHMARK_EXE = os.path.join("src_cpp", "benchmark.exe")
RESULTS_DIR   = os.path.join("experiments", "cpp_adversarial", "results")
CSV_PATH      = os.path.join(RESULTS_DIR, "results.csv")

SAMPLES    = 3
WALL_EXCESS = 3.0

# N ranges — interleaved so both algorithms make progress in lockstep.
# Wall detection stops each algorithm automatically.
NS = list(range(1000, 55001, 1000))  # 1000 .. 50000

ALGORITHMS = ["DijkstraPrims"] #, "BBMSInter", "BBMSDppStepwise", "BBMSCore", "BBMSDppInstant"]  # BBMSCore, BBMSDppInstant excluded — scaling characterised up to N=12000
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
    cur = mean_runtime(rows, alg, N)
    if cur is None:
        return False
    prev_Ns = sorted(set(r["N"] for r in rows if r["algorithm"] == alg and r["N"] < N))
    if not prev_Ns:
        return False
    prev_N   = prev_Ns[-1]
    prev     = mean_runtime(rows, alg, prev_N)
    if not prev:
        return False
    actual_ratio   = cur / prev
    expected_ratio = (N / prev_N) ** 2
    excess         = actual_ratio / expected_ratio
    if excess >= WALL_EXCESS:
        print(f"  [WALL] {alg} N={N}: {cur:.2f}s is {actual_ratio:.1f}x "
              f"N={prev_N} ({prev:.2f}s), {excess:.1f}x above O(N²) — skipping larger N.", flush=True)
        return True
    return False


def detect_walls_in_existing(rows):
    walls = {}
    for alg in set(r["algorithm"] for r in rows):
        Ns = sorted(set(r["N"] for r in rows if r["algorithm"] == alg))
        for i in range(1, len(Ns)):
            if check_wall(rows, alg, Ns[i]):
                walls[alg] = Ns[i]
                break
    return walls


def run_one(alg, N, sample):
    cmd = [BENCHMARK_EXE, alg, str(N), str(sample)]
    t0 = time.perf_counter()
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=7200)
        elapsed = time.perf_counter() - t0
        line = result.stdout.strip()
        if not line:
            raise RuntimeError(result.stderr.strip() or "no output")
        parts = line.split(",")
        runtime_s   = float(parts[3])
        frechet_dist = float(parts[4])
        ok           = parts[5] == "True"
        row = dict(algorithm=alg, N=N, sample=sample,
                   runtime_s=round(runtime_s, 6),
                   frechet_dist=round(frechet_dist, 4), ok=ok)
        status = f"{runtime_s:8.4f}s  fd={frechet_dist:.3f}" if ok else "FAIL"
        print(f"  {alg:20s} N={N:6d} s={sample}  {status}", flush=True)
    except subprocess.TimeoutExpired:
        row = dict(algorithm=alg, N=N, sample=sample,
                   runtime_s=-1, frechet_dist=-1, ok=False)
        print(f"  {alg:20s} N={N:6d} s={sample}  TIMEOUT", flush=True)
    except Exception as e:
        row = dict(algorithm=alg, N=N, sample=sample,
                   runtime_s=-1, frechet_dist=-1, ok=False)
        print(f"  {alg:20s} N={N:6d} s={sample}  ERROR: {e}", flush=True)
    append_row(row)


def build_jobs():
    """Interleave both algorithms at each N so they make equal progress."""
    jobs = []
    for N in NS:
        for alg in ALGORITHMS:
            for s in range(SAMPLES):
                jobs.append((alg, N, s))
    return jobs


def main():
    if not os.path.exists(BENCHMARK_EXE):
        print(f"ERROR: benchmark binary not found at {BENCHMARK_EXE}", flush=True)
        print("Run: cd src_cpp && make benchmark.exe", flush=True)
        sys.exit(1)

    os.makedirs(RESULTS_DIR, exist_ok=True)
    jobs  = build_jobs()
    rows  = load_csv()
    done  = {(r["algorithm"], r["N"], r["sample"]) for r in rows}
    pending = [(a, N, s) for a, N, s in jobs if (a, N, s) not in done]

    walls = detect_walls_in_existing(rows)
    if walls:
        print("  [WALL] Already walled: " +
              ", ".join(f"{a} at N={n}" for a, n in walls.items()), flush=True)

    print(f"Total jobs: {len(jobs)}  |  Done: {len(done)}  |  Remaining: {len(pending)}", flush=True)

    for alg, N, s in pending:
        if _interrupted:
            print("Stopping early — progress saved.", flush=True)
            sys.exit(0)
        if alg in walls and N >= walls[alg]:
            print(f"  [SKIP] {alg} N={N} s={s}", flush=True)
            continue
        run_one(alg, N, s)
        rows = load_csv()
        if alg not in walls and check_wall(rows, alg, N):
            walls[alg] = N

    print("\nAll runs complete.", flush=True)


if __name__ == "__main__":
    main()
