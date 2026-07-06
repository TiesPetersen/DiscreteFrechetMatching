"""
Experiment: memory usage / page-fault onset

Runs BBMSInter (C++) on increasingly large adversarial polylines
(N = 1000..30000, step 1000) and records everything getrusage() can tell us
about each run: peak RSS, minor/major page faults, block I/O ops, context
switches, and user/sys CPU time.

On macOS, major_faults/block_io_ops don't reliably light up (the memory
compressor intercepts reclaim before it becomes classic disk-block I/O) — the
signals that actually showed the wall in earlier runs were RSS plateauing
while runtime blows past O(N^2), and involuntary_ctx_switches/
voluntary_ctx_switches jumping sharply once memory pressure kicks in.

One sample per N: fault/memory counts are driven by N deterministically
(O(N^2) allocation), unlike wall-clock time, so repeated sampling adds little
here.

Resumable: existing CSV rows are skipped on startup.
"""

import csv
import os
import subprocess
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(_PROJECT_ROOT)

MEMORY_USAGE_EXE = os.path.join("src_cpp", "memory_usage.exe")
RESULTS_DIR      = os.path.join("experiments", "memory_usage", "results")
CSV_PATH         = os.path.join(RESULTS_DIR, "results.csv")

NS     = list(range(1000, 30001, 1000))
SAMPLE = 0  # single sample per N; kept as a column for consistency with other experiments

FIELDNAMES = [
    "N", "sample", "runtime_s", "frechet_dist",
    "before_rss_mb", "after_rss_mb",
    "minor_faults", "major_faults", "swaps",
    "block_input_ops", "block_output_ops",
    "voluntary_ctx_switches", "involuntary_ctx_switches",
    "user_time_s", "sys_time_s", "ok",
]


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
            done.add((int(r["N"]), int(r["sample"])))
    return done


def run_one(N, sample):
    cmd = [MEMORY_USAGE_EXE, str(N), str(sample)]
    print(f"  BBMSInter N={N:6d} s={sample}  running...", flush=True)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=7200)
        line = result.stdout.strip()
        if not line:
            raise RuntimeError(result.stderr.strip() or "no output")
        parts = line.split(",")
        row = dict(zip(FIELDNAMES, parts))
        row["N"], row["sample"] = int(row["N"]), int(row["sample"])
        status = (f"{float(row['runtime_s']):8.3f}s  "
                  f"rss {row['before_rss_mb']}->{row['after_rss_mb']} MB  "
                  f"major_faults={row['major_faults']}") if row["ok"] == "True" else "FAIL"
        print(f"  BBMSInter N={N:6d} s={sample}  {status}", flush=True)
    except subprocess.TimeoutExpired:
        row = dict(zip(FIELDNAMES, [N, sample] + ["-1"] * (len(FIELDNAMES) - 3) + ["False"]))
        print(f"  BBMSInter N={N:6d} s={sample}  TIMEOUT", flush=True)
    except Exception as e:
        row = dict(zip(FIELDNAMES, [N, sample] + ["-1"] * (len(FIELDNAMES) - 3) + ["False"]))
        print(f"  BBMSInter N={N:6d} s={sample}  ERROR: {e}", flush=True)
    append_row(row)


def main():
    if not os.path.exists(MEMORY_USAGE_EXE):
        print(f"ERROR: binary not found at {MEMORY_USAGE_EXE}", flush=True)
        print("Run: cd src_cpp && make memory_usage.exe", flush=True)
        sys.exit(1)

    os.makedirs(RESULTS_DIR, exist_ok=True)
    done = load_done()

    for N in NS:
        if (N, SAMPLE) in done:
            print(f"  [SKIP] N={N} s={SAMPLE} (already in results.csv)", flush=True)
            continue
        run_one(N, SAMPLE)

    print("\nAll runs complete.", flush=True)


if __name__ == "__main__":
    main()
