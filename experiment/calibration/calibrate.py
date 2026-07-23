"""
Calibration run for real hardware -- see experiment/calibration/AWS_HANDOFF.md for
the full step-by-step plan this script is part of.

Reuses experiment/main.py's runner-invocation, classification, and resumability
logic (run_timing_pass, run_opcount_pass, etc.) completely unchanged, just against
a much smaller sweep (fewer/no repeats, a short timeout) and a separate output
directory (results_calibration/, not results/) so a calibration run can never be
mistaken for, or clobber, real experiment data.

Usage (from anywhere -- importing main.py chdir's to the project root):
    python3 experiment/calibration/calibrate.py
    python3 experiment/calibration/calibrate.py --dataset all --timeout 120
    python3 experiment/calibration/calibrate.py --grid 500,1000,2000,4000 --k 2 --r 2

Resumable exactly like main.py: rerunning after an interruption picks up where it
left off. To start over, delete results_calibration/ first.
"""

import argparse
import csv
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import main as experiment_main  # noqa: E402  (import after sys.path tweak, on purpose)


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dataset", default="worst-case",
                    help="dataset name, or 'all' for worst-case+best-case+random (default: worst-case, "
                         "the most adversarial -- see PLAN.md for why it's the one most likely to reveal "
                         "an early wall)")
    p.add_argument("--grid", default=None,
                    help="comma-separated N values (default: the full production grid from main.py, "
                         "so calibration checks the same range the real run will use)")
    p.add_argument("--k", type=int, default=1, help="samples per N (default: 1, vs. main.py's 5)")
    p.add_argument("--r", type=int, default=1, help="timing repeats per sample (default: 1, vs. main.py's 3)")
    p.add_argument("--timeout", type=int, default=60,
                    help="per-run timeout in seconds (default: 60 -- main.py's real placeholder of 2700s "
                         "would make a stuck run take way too long to notice during calibration)")
    return p.parse_args()


def print_summary(datasets):
    for dataset in datasets:
        csv_path = os.path.join(experiment_main.RESULTS_DIR, dataset, "timing_memory.csv")
        if not os.path.exists(csv_path):
            continue

        print(f"\n=== {dataset}: avg runtime_s / avg maxrss_after_mb per (algorithm, N) ===")
        stats = {}
        failures = []
        with open(csv_path, newline="") as f:
            for row in csv.DictReader(f):
                key = (row["algorithm"], int(row["N"]))
                if row["status"] == "ok":
                    s = stats.setdefault(key, {"runtime": 0.0, "maxrss": 0.0, "n": 0})
                    s["runtime"] += float(row["runtime_s"])
                    s["maxrss"] += float(row["maxrss_after_mb"])
                    s["n"] += 1
                else:
                    failures.append((key[0], key[1], row.get("sample"), row.get("repeat"), row["status"]))

        for (algorithm, n), s in sorted(stats.items(), key=lambda kv: (kv[0][0], kv[0][1])):
            print(f"  {algorithm:15s} N={n:6d}  avg_runtime={s['runtime']/s['n']:9.4f}s  "
                  f"avg_maxrss={s['maxrss']/s['n']:9.2f}MB  (n={s['n']})")

        if failures:
            print(f"\n=== {dataset}: non-ok rows (these mark where an algorithm's wall was hit) ===")
            for algorithm, n, sample, repeat, status in failures:
                print(f"  {algorithm:15s} N={n:6d} sample={sample} repeat={repeat}  status={status}")
        else:
            print(f"\n  (no timeouts/OOMs/errors in {dataset} -- every configured N/sample/repeat succeeded)")

        opcounts_path = os.path.join(experiment_main.RESULTS_DIR, dataset, "opcounts.csv")
        if os.path.exists(opcounts_path):
            by_instance = {}
            with open(opcounts_path, newline="") as f:
                for row in csv.DictReader(f):
                    if row["status"] != "ok":
                        continue
                    key = (int(row["N"]), row["sample"])
                    by_instance.setdefault(key, []).append((row["algorithm"], float(row["frechet_dist"])))
            disagreements = 0
            for (n, sample), results in by_instance.items():
                distances = [d for _, d in results]
                if max(distances) - min(distances) > 1e-9:
                    disagreements += 1
                    print(f"  WARNING: {dataset} N={n} sample={sample}: algorithms disagree "
                          f"on frechet_distance -- {results}")
            if disagreements == 0 and by_instance:
                print(f"  cross-algorithm frechet_distance agreement: OK "
                      f"({len(by_instance)} instances checked)")


def main():
    args = parse_args()

    if not os.path.exists(experiment_main.RUNNER) or not os.path.exists(experiment_main.RUNNER_COUNTED):
        print("ERROR: runner binaries not found. Run: cd experiment && make", flush=True)
        sys.exit(1)

    datasets = ["worst-case", "best-case", "random"] if args.dataset == "all" else [args.dataset]

    experiment_main.RESULTS_DIR = "results_calibration"
    experiment_main.GRID = [int(x) for x in args.grid.split(",")] if args.grid else experiment_main.GRID
    experiment_main.K = args.k
    experiment_main.R = args.r
    experiment_main.TIMEOUT_S = args.timeout

    print(f"{experiment_main.log_timestamp()}  Calibration run: datasets={datasets} "
          f"grid={experiment_main.GRID} k={experiment_main.K} r={experiment_main.R} "
          f"timeout={experiment_main.TIMEOUT_S}s\n"
          f"Writing to {experiment_main.RESULTS_DIR}/ (not results/ -- this never touches real run data)\n",
          flush=True)

    for dataset in datasets:
        os.makedirs(os.path.join(experiment_main.RESULTS_DIR, dataset), exist_ok=True)
        experiment_main.run_timing_pass(dataset)
        experiment_main.run_opcount_pass(dataset)

    print(f"\n{experiment_main.log_timestamp()}  Calibration run complete.", flush=True)
    print_summary(datasets)


if __name__ == "__main__":
    main()
