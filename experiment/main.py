"""
Main experiment orchestrator. Runs runner.exe / runner_counted.exe across every
(dataset, N, sample[, repeat], algorithm) combination described in PLAN.md, and
writes the results to results/<dataset>/timing_memory.csv and opcounts.csv.

Resumable: on restart, already-completed rows are skipped, and any algorithm that
already hit a timeout or OOM at some N is not retried at larger N (cost only grows
with N, so a bigger N is essentially certain to fail again too).

Run from the project root:
    python3 experiment/main.py
"""

import csv
import os
import subprocess
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(PROJECT_ROOT)

# Log lines are timestamped in Amsterdam local time (CET/CEST, DST-aware via
# zoneinfo) regardless of what timezone the machine actually running this
# (WSL laptop tonight, AWS tomorrow) happens to be set to.
AMSTERDAM_TZ = ZoneInfo("Europe/Amsterdam")


def log_timestamp():
    return datetime.now(AMSTERDAM_TZ).strftime("%Y-%m-%d %H:%M:%S %Z")

RUNNER         = os.path.join("experiment", "runner.exe")
RUNNER_COUNTED = os.path.join("experiment", "runner_counted.exe")

# Overridable by experiment/calibration/calibrate.py, which reuses these functions
# against a separate output directory so calibration runs can never be mistaken
# for, or clobber, real experiment data.
RESULTS_DIR = "results"

DATASETS   = ["worst-case", "best-case", "random"]
GRID       = [500, 1000, 2000, 4000, 7000, 11000, 18000, 28000, 40000, 50000]
K          = 5     # samples per (dataset, N), same for all three datasets
R          = 3     # timing repeats per sample
ALGORITHMS = ["BBMSCore", "BBMSInter", "BBMSDppInstant", "BBMSDppStepwise", "DijkstraPrims"]

TIMEOUT_S = 7200  # 2h -- set from the AWS calibration run (see PLAN.md 6). BBMSCore's
                  # true cost at N=11000 and BBMSInter/DijkstraPrims' at N=18000 all
                  # exceeded the calibration script's own tight 120s cap without being
                  # anywhere near a real wall (extrapolated true times: ~150-260s) --
                  # 45 min risked mistaking ordinary noise for a genuine wall right
                  # around DijkstraPrims' top-of-grid runtime; 2h gives real headroom.

# A run that hits either of these is expected to fail again at any larger N for the
# same (dataset, algorithm), so testing stops there. "error" is excluded on purpose --
# a bug or crash isn't necessarily tied to N the way a timeout or OOM is.
FAILURE_STATUSES = {"timeout", "oom"}

# Field names the runner binaries print, in order, on their one stdout line.
RUNNER_TIMING_FIELDS = [
    "algorithm", "N", "sample", "runtime_s", "frechet_dist",
    "maxrss_before_mb", "maxrss_after_mb", "minor_faults", "major_faults",
    "block_input_ops", "block_output_ops",
    "voluntary_ctx_switches", "involuntary_ctx_switches",
    "user_time_s", "sys_time_s", "blocked_time_s", "status",
]
OPCOUNT_FIELDS = [
    "algorithm", "N", "sample", "frechet_dist",
    "nca_regular_hops", "nca_shortcut_hops", "total_nca_steps", "shortcuts_written",
    "dead_paths_pruned", "shortcuts_extended", "dead_path_walk_steps",
    "heap_pushes", "heap_pops", "cells_processed", "pct_cells_explored", "status",
]
# The CSV on disk also carries `repeat`, which the runner doesn't know about --
# that's bookkeeping the orchestrator adds, not something measured per run.
TIMING_FIELDS = RUNNER_TIMING_FIELDS + ["repeat"]


def blank_row(fieldnames, known, status):
    """A row of -1 placeholders for a run that didn't produce real output -- except
    for `known` (algorithm/N/sample), which must be kept even on failure. Losing
    those would make it impossible to tell which run failed, and would also break
    wall-reconstruction on resume, which depends on reading them back from the CSV."""
    row = {name: -1 for name in fieldnames}
    row.update(known)
    row["status"] = status
    return row


def append_row(csv_path, fieldnames, row):
    write_header = not os.path.exists(csv_path)
    with open(csv_path, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()
        writer.writerow(row)


def load_done_and_walls(csv_path, key_fields):
    """Reconstructs both the completed-row set and the wall state from the CSV.
    These must be seeded together on resume -- if walls started empty every time,
    resuming past an already-discovered wall would re-attempt those larger-N runs
    and burn a full timeout re-discovering what a previous run already found."""
    done = set()
    walls = {}
    if not os.path.exists(csv_path):
        return done, walls

    with open(csv_path, newline="") as f:
        for row in csv.DictReader(f):
            done.add(tuple(row[field] for field in key_fields))
            if row["status"] in FAILURE_STATUSES:
                n = int(row["N"])
                walls[row["algorithm"]] = min(walls.get(row["algorithm"], n), n)

    return done, walls


def run_and_classify(cmd, fieldnames, known, timeout=TIMEOUT_S):
    """Runs one subprocess and returns (row, status). Handles three outcomes:
    a normal exit with a parseable CSV line ("ok" or the runner's own "error"),
    a timeout, and a killed/crashed process with no usable output.

    On Linux, a process that runs out of memory is usually killed by the kernel's
    OOM killer (SIGKILL) rather than raising an exception the runner could catch --
    so an unparseable result from an otherwise-completed run is treated as OOM. This
    is an inference, not a direct observation (see PLAN.md 5.5) -- worth confirming
    empirically once real OOM conditions can actually be triggered.

    `known` is what the orchestrator already knows before running (algorithm, N,
    sample) -- kept in the row even on failure, so a failed run can still be
    identified and so wall-reconstruction on resume has something to read back.

    `timeout=None` disables the subprocess timeout entirely -- used by the op-count
    pass, which only ever attempts N values the timing pass already succeeded at
    (see run_opcount_pass), so a timeout there was never expected to fire anyway.
    """
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return blank_row(fieldnames, known, "timeout"), "timeout"

    line = result.stdout.strip()
    if result.returncode != 0 or not line:
        return blank_row(fieldnames, known, "oom"), "oom"

    values = line.split(",")
    if len(values) != len(fieldnames):
        return blank_row(fieldnames, known, "oom"), "oom"

    row = dict(zip(fieldnames, values))
    return row, row["status"]


def run_timing_pass(dataset):
    csv_path = os.path.join(RESULTS_DIR, dataset, "timing_memory.csv")
    done, walls = load_done_and_walls(csv_path, ["algorithm", "N", "sample", "repeat"])

    for n in GRID:
        dataset_file = os.path.join("datasets", dataset, f"N_{n}.txt")
        for sample in range(K):
            for repeat in range(R):
                for algorithm in ALGORITHMS:
                    if n >= walls.get(algorithm, float("inf")):
                        continue
                    key = (algorithm, str(n), str(sample), str(repeat))
                    if key in done:
                        continue

                    known = {"algorithm": algorithm, "N": n, "sample": sample}
                    cmd = [RUNNER, algorithm, dataset_file, str(sample)]
                    row, status = run_and_classify(cmd, RUNNER_TIMING_FIELDS, known)
                    row["repeat"] = repeat

                    if status in FAILURE_STATUSES:
                        walls[algorithm] = min(walls.get(algorithm, n), n)

                    print(f"{log_timestamp()}  [timing]   {dataset:10s} {algorithm:15s} N={n:6d} "
                          f"sample={sample} repeat={repeat}  status={status}", flush=True)
                    append_row(csv_path, TIMING_FIELDS, row)


def run_opcount_pass(dataset):
    csv_path = os.path.join(RESULTS_DIR, dataset, "opcounts.csv")
    done, walls = load_done_and_walls(csv_path, ["algorithm", "N", "sample"])

    # Op-counting does the same algorithmic work as timing (same code, plus cheap
    # increments), so an N that already failed there is expected to fail here too --
    # no need to re-pay a real timeout or risk a real OOM just to re-learn a wall
    # the timing pass already found. Only ever narrows `walls`, never widens it.
    timing_csv_path = os.path.join(RESULTS_DIR, dataset, "timing_memory.csv")
    _, timing_walls = load_done_and_walls(timing_csv_path, ["algorithm", "N", "sample", "repeat"])
    for algorithm, timing_wall_n in timing_walls.items():
        walls[algorithm] = min(walls.get(algorithm, timing_wall_n), timing_wall_n)

    for n in GRID:
        dataset_file = os.path.join("datasets", dataset, f"N_{n}.txt")
        for sample in range(K):
            for algorithm in ALGORITHMS:
                if n >= walls.get(algorithm, float("inf")):
                    continue
                key = (algorithm, str(n), str(sample))
                if key in done:
                    continue

                known = {"algorithm": algorithm, "N": n, "sample": sample}
                cmd = [RUNNER_COUNTED, algorithm, dataset_file, str(sample)]
                row, status = run_and_classify(cmd, OPCOUNT_FIELDS, known, timeout=None)

                if status in FAILURE_STATUSES:
                    walls[algorithm] = min(walls.get(algorithm, n), n)

                print(f"{log_timestamp()}  [opcounts] {dataset:10s} {algorithm:15s} N={n:6d} "
                      f"sample={sample}  status={status}", flush=True)
                append_row(csv_path, OPCOUNT_FIELDS, row)

    verify_cross_algorithm_agreement(dataset)


def verify_cross_algorithm_agreement(dataset):
    """Checks that every algorithm reports the same Frechet distance on the same
    instance. Uses only the op-count CSV -- exactly one row per (algorithm, N,
    sample), no repeats to reconcile -- so this needs no extra runs."""
    csv_path = os.path.join(RESULTS_DIR, dataset, "opcounts.csv")
    if not os.path.exists(csv_path):
        return

    by_instance = {}
    with open(csv_path, newline="") as f:
        for row in csv.DictReader(f):
            if row["status"] != "ok":
                continue
            key = (row["N"], row["sample"])
            by_instance.setdefault(key, []).append((row["algorithm"], float(row["frechet_dist"])))

    for (n, sample), results in by_instance.items():
        distances = [d for _, d in results]
        if max(distances) - min(distances) > 1e-9:
            print(f"{log_timestamp()}  WARNING: {dataset} N={n} sample={sample}: algorithms disagree "
                  f"on frechet_distance -- {results}", flush=True)


def main():
    if not os.path.exists(RUNNER) or not os.path.exists(RUNNER_COUNTED):
        print(f"ERROR: runner binaries not found. Run: cd experiment && make", flush=True)
        sys.exit(1)

    print(f"{log_timestamp()}  Starting run.", flush=True)

    for dataset in DATASETS:
        os.makedirs(os.path.join(RESULTS_DIR, dataset), exist_ok=True)
        run_timing_pass(dataset)
        run_opcount_pass(dataset)

    print(f"\n{log_timestamp()}  All runs complete.", flush=True)


if __name__ == "__main__":
    main()
