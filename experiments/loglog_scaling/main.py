"""
Experiment: log-log complexity scaling

Runs DijkstraPrims, BBMSCore, and BBMSInter (C++) on adversarial-outlier
polylines at log-spaced N, with repeated samples per N. This is the
empirical-validation counterpart to the theoretical O(N^2) time complexity
claim for all three: plot.py takes the minimum runtime per (algorithm, N)
(system noise only ever slows a run down, so the min is the best estimate of
the noise-free cost), fits a line on log-log axes, and reports the fitted
exponent to compare against the theoretical one.

N is capped at 8000 deliberately: BBMSInter's memory_usage experiment showed
timing becomes erratic (system memory pressure, not algorithmic behavior)
starting around N=9000-19000 on this machine. Staying under that keeps this
plot a clean read of algorithmic complexity, not memory-wall noise.

BBMSDppInstant/BBMSDppStepwise are deliberately excluded for now — they still
use int indices and don't build against the widened Matching type.

Resumable: existing CSV rows are skipped on startup.
"""

import csv
import os
import subprocess
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(_PROJECT_ROOT)

LOGLOG_EXE  = os.path.join("src_cpp", "loglog_scaling.exe")
RESULTS_DIR = os.path.join("experiments", "loglog_scaling", "results")
CSV_PATH    = os.path.join(RESULTS_DIR, "results.csv")

ALGORITHMS = ["DijkstraPrims", "BBMSCore", "BBMSInter"]
NS         = [250, 500, 1000, 2000, 4000, 8000]  # log-spaced (doubling) for an evenly-weighted log-log fit
SAMPLES    = 5  # per (algorithm, N); plot.py takes the minimum

FIELDNAMES = ["algorithm", "N", "sample", "runtime_s", "frechet_dist", "ok"]


def append_row(row):
    write_header = not os.path.exists(CSV_PATH)
    with open(CSV_PATH, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDNAMES)
        if write_header:
            w.writeheader()
        w.writerow(row)


def load_done():
    done = set()
    if not os.path.exists(CSV_PATH):
        return done
    with open(CSV_PATH, newline="") as f:
        for r in csv.DictReader(f):
            done.add((r["algorithm"], int(r["N"]), int(r["sample"])))
    return done


def run_one(algo, N, sample):
    cmd = [LOGLOG_EXE, algo, str(N), str(sample)]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=7200)
        line = result.stdout.strip()
        if not line:
            raise RuntimeError(result.stderr.strip() or "no output")
        parts = line.split(",")
        row = dict(zip(FIELDNAMES, parts))
        row["N"], row["sample"] = int(row["N"]), int(row["sample"])
        status = f"{float(row['runtime_s']):8.4f}s  fd={row['frechet_dist']}" if row["ok"] == "True" else "FAIL"
        print(f"  {algo:15s} N={N:6d} s={sample}  {status}", flush=True)
    except subprocess.TimeoutExpired:
        row = dict(zip(FIELDNAMES, [algo, N, sample, -1, -1, "False"]))
        print(f"  {algo:15s} N={N:6d} s={sample}  TIMEOUT", flush=True)
    except Exception as e:
        row = dict(zip(FIELDNAMES, [algo, N, sample, -1, -1, "False"]))
        print(f"  {algo:15s} N={N:6d} s={sample}  ERROR: {e}", flush=True)
    append_row(row)


def main():
    if not os.path.exists(LOGLOG_EXE):
        print(f"ERROR: binary not found at {LOGLOG_EXE}", flush=True)
        print("Run: cd src_cpp && make loglog_scaling.exe", flush=True)
        sys.exit(1)

    os.makedirs(RESULTS_DIR, exist_ok=True)
    done = load_done()

    for N in NS:
        for algo in ALGORITHMS:
            for s in range(SAMPLES):
                if (algo, N, s) in done:
                    print(f"  [SKIP] {algo} N={N} s={s} (already in results.csv)", flush=True)
                    continue
                run_one(algo, N, s)

    print("\nAll runs complete.", flush=True)


if __name__ == "__main__":
    main()
