"""
Builds the four reports of the November 2026 AWS run.

  overview.html       the headline results, block by block (analysis/app_aws_2026_11.py)
  main.html           final code on every synthetic set, plus the current DPP (blocks B, C, E)
  before_after.html   old code against new code (block A)
  real_world.html     real-world datasets (block D)

The last three use the general report scripts, which read one folder per
dataset with timing_memory.csv and opcounts.csv. This script first converts
results_aws_2026_11/timing.csv and counts.csv into that layout.

Usage, from the repo root:
    python3 experiment/aws_2026_11/make_reports.py
    python3 experiment/aws_2026_11/make_reports.py results_aws_2026_11 -o analysis/output/aws_2026_11
"""

import argparse
import csv
import os
import subprocess
import sys

SYNTHETIC_TIMING = ["algorithm", "N", "sample", "runtime_s", "frechet_dist", "maxrss_before_mb", "maxrss_after_mb",
                    "minor_faults", "major_faults", "block_input_ops", "block_output_ops", "voluntary_ctx_switches",
                    "involuntary_ctx_switches", "user_time_s", "sys_time_s", "blocked_time_s", "status", "repeat"]
SYNTHETIC_COUNTS = ["algorithm", "N", "sample", "frechet_dist", "nca_regular_hops", "nca_shortcut_hops",
                    "total_nca_steps", "shortcuts_written", "dead_paths_pruned", "shortcuts_extended",
                    "dead_path_walk_steps", "heap_pushes", "heap_pops", "max_heap_size", "avg_heap_size",
                    "cells_processed", "pct_cells_explored", "status"]
REAL_WORLD_TIMING = ["algorithm", "pair_index", "m", "n", "cells"] + SYNTHETIC_TIMING[3:]
REAL_WORLD_COUNTS = ["algorithm", "pair_index", "m", "n", "cells"] + SYNTHETIC_COUNTS[3:]


def read(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write(path, records, fields):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)


def renamed(row, algorithm):
    """A copy of a run row in the general scripts' layout: N is the curve length, sample the pair."""
    row = dict(row, algorithm=algorithm, N=row["m"], sample=row["pair"])
    if row["outcome"] != "ok":
        row["status"] = row["outcome"]
    return row


def convert(results, data):
    for kind, source in [("timing", "timing.csv"), ("counts", "counts.csv")]:
        rows = read(os.path.join(results, source))
        synthetic_fields = SYNTHETIC_TIMING if kind == "timing" else SYNTHETIC_COUNTS
        filename = "timing_memory.csv" if kind == "timing" else "opcounts.csv"
        groups = {}
        for row in rows:
            if row["block"] in ("B", "E"):
                groups.setdefault(("main", row["dataset"]), []).append(renamed(row, row["algorithm"]))
            elif row["block"] == "C":
                groups.setdefault(("main", row["dataset"]), []).append(renamed(row, row["algorithm"] + " (current)"))
            elif row["block"] == "A":
                groups.setdefault(("before_after", row["dataset"]), []).append(
                    renamed(row, f"{row['algorithm']} ({row['code']})"))
            elif row["block"] == "D":
                groups.setdefault(("real_world", row["dataset"]), []).append(row)
        for (report, dataset), records in groups.items():
            if report == "real_world":
                # Number the pairs across the part files of a dataset
                index = {key: i for i, key in enumerate(sorted({(r["file"], int(r["pair"])) for r in records}))}
                records = [dict(r, pair_index=index[(r["file"], int(r["pair"]))],
                                algorithm=r["algorithm"] + (" (current)" if r["algorithm"] == "BBMSDppStepwise" else ""),
                                status=r["status"] if r["outcome"] == "ok" else r["outcome"])
                           for r in records]
                fields = REAL_WORLD_TIMING if kind == "timing" else REAL_WORLD_COUNTS
            else:
                fields = synthetic_fields
            write(os.path.join(data, report, dataset, filename), records, fields)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("results_folder", nargs="?", default="results_aws_2026_11")
    parser.add_argument("-o", "--output", default="analysis/output/aws_2026_11")
    args = parser.parse_args()

    data = os.path.join(args.output, "data")
    convert(args.results_folder, data)
    jobs = [
        ["analysis/app_aws_2026_11.py", args.results_folder, "-o", os.path.join(args.output, "overview.html")],
        ["analysis/app_synthetic.py", os.path.join(data, "main"), "-o", os.path.join(args.output, "main.html")],
        ["analysis/app_synthetic.py", os.path.join(data, "before_after"), "-o", os.path.join(args.output, "before_after.html")],
        ["analysis/app_real_world.py", os.path.join(data, "real_world"), "-o", os.path.join(args.output, "real_world.html")],
    ]
    for job in jobs:
        subprocess.run([sys.executable] + job, check=True)


if __name__ == "__main__":
    main()
