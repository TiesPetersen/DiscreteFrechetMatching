"""
Runs every (dataset, pair, algorithm) combination from datasets/real-world/ and
writes results to RESULTS_DIR. Closely based on experiment/synthetic/main.py,
with three deliberate differences from it, all stemming from real-world curve
pairs having independent, unequal lengths (m != n) with no shared "N" grid:

1. No cross-pair walling. The synthetic experiment skips larger N once an
   algorithm fails at a smaller N, because cost is monotonic in N there. Real
   pairs have no such ordering -- pair #47 might be smaller than pair #12 -- so
   walling would unfairly deny some pairs a chance to run. Every (algorithm,
   pair) is attempted independently; timeouts/OOM are expected, reportable
   outcomes here, not something to avoid.

2. The op-count pass is timeout-bounded here (the synthetic experiment leaves
   it uncapped, since op counts are deterministic and BBMS work is always
   exactly m*n regardless of input). Real curves have shown far worse
   per-cell behavior than synthetic ones for BBMSCore/BBMSInter (see the pilot
   in external_datasets/pilot.py -- e.g. a 120s timeout on a Pigeons pair at
   just ~7.2M cells, a size that takes ~4s on synthetic data), so leaving this
   pass uncapped risked one pathological pair stalling the whole run
   indefinitely. Both passes share TIMEOUT here.

3. Schema: "N"/"sample" are replaced with "pair_index"/"m"/"n"/"cells" --
   runner.cpp itself only ever reports a single N (= p.size()), hard-assuming
   m == n, which isn't true for real curve pairs. m and n are recorded here
   instead, from what this script already knows about each pair before
   invoking the runner.

Run from the project root:
    python3 experiment/real-world/main.py
"""

import csv
import os
import subprocess
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(PROJECT_ROOT)

AMSTERDAM_TZ = ZoneInfo("Europe/Amsterdam")

RUNNER         = os.path.join("experiment", "runner.exe")
RUNNER_COUNTED = os.path.join("experiment", "runner_counted.exe")

DATASETS_DIR = os.path.join("datasets", "real-world")
RESULTS_DIR  = "results_real_world"
LOG_PATH     = os.path.join(RESULTS_DIR, "experiment.log")

REPEAT     = 3     # timing repeats per pair, same as the synthetic experiment
ALGORITHMS = ["BBMSCore", "BBMSInter", "BBMSDppInstant", "BBMSDppStepwise", "DijkstraPrims"]
TIMEOUT    = 300   # seconds -- applies to BOTH passes here, see module docstring point 2

FAILURE_STATUSES = {"timeout", "oom"}

# Same field names runner.cpp prints, in order, on its one stdout line -- the
# binary itself is untouched, still labels its own length field "N" (= m).
RUNNER_TIMING_FIELDS = [
    "algorithm", "N", "sample", "runtime_s", "frechet_dist",
    "maxrss_before_mb", "maxrss_after_mb", "minor_faults", "major_faults",
    "block_input_ops", "block_output_ops",
    "voluntary_ctx_switches", "involuntary_ctx_switches",
    "user_time_s", "sys_time_s", "blocked_time_s", "status",
]
RUNNER_OPCOUNT_FIELDS = [
    "algorithm", "N", "sample", "frechet_dist",
    "nca_regular_hops", "nca_shortcut_hops", "total_nca_steps", "shortcuts_written",
    "dead_paths_pruned", "shortcuts_extended", "dead_path_walk_steps",
    "heap_pushes", "heap_pops", "max_heap_size", "avg_heap_size",
    "cells_processed", "pct_cells_explored", "status",
]

# The CSV schemas this script actually writes -- "N"/"sample" swapped for
# "pair_index"/"m"/"n"/"cells" (see module docstring point 3).
TIMING_FIELDS = ["algorithm", "pair_index", "m", "n", "cells", "runtime_s", "frechet_dist",
                  "maxrss_before_mb", "maxrss_after_mb", "minor_faults", "major_faults",
                  "block_input_ops", "block_output_ops",
                  "voluntary_ctx_switches", "involuntary_ctx_switches",
                  "user_time_s", "sys_time_s", "blocked_time_s", "status", "repeat"]
OPCOUNT_FIELDS = ["algorithm", "pair_index", "m", "n", "cells", "frechet_dist",
                   "nca_regular_hops", "nca_shortcut_hops", "total_nca_steps", "shortcuts_written",
                   "dead_paths_pruned", "shortcuts_extended", "dead_path_walk_steps",
                   "heap_pushes", "heap_pops", "max_heap_size", "avg_heap_size",
                   "cells_processed", "pct_cells_explored", "status"]

_log_file = None


def log(msg):
    line = f"{datetime.now(AMSTERDAM_TZ).strftime('%Y-%m-%d %H:%M:%S %Z')}  {msg}"
    print(line, flush=True)
    _log_file.write(line + "\n")
    _log_file.flush()


def scan_part_file(path):
    """Reads a part_NNN.txt file's own pair count and each pair's (m, n) --
    without materializing the actual point data -- by walking it token by
    token and skipping over 2*m and 2*n coordinate tokens per pair. Returns
    [(m, n), ...] in file order (index i = the sample_index the runner expects
    for that pair)."""
    with open(path) as f:
        tokens = f.read().split()
    pos = 0
    count = int(tokens[pos]); pos += 1
    shapes = []
    for _ in range(count):
        m = int(tokens[pos]); pos += 1 + 2 * m
        n = int(tokens[pos]); pos += 1 + 2 * n
        shapes.append((m, n))
    return shapes


def discover_datasets():
    """Scans datasets/real-world/*/part_*.txt. Returns
    {dataset: [(part_file, local_index, m, n), ...]} -- one entry per pair,
    in a stable global order (sorted by part filename, then file order within
    each part) so "pair_index" in the output CSVs is a stable global index."""
    if not os.path.isdir(DATASETS_DIR):
        log(f"ERROR: no '{DATASETS_DIR}/' folder found.")
        return None

    datasets = {}
    for name in sorted(os.listdir(DATASETS_DIR)):
        dataset_dir = os.path.join(DATASETS_DIR, name)
        if not os.path.isdir(dataset_dir):
            continue
        part_files = sorted(fn for fn in os.listdir(dataset_dir)
                             if fn.startswith("part_") and fn.endswith(".txt"))
        if not part_files:
            continue

        pairs = []
        for part_fn in part_files:
            part_path = os.path.join(dataset_dir, part_fn)
            for local_index, (m, n) in enumerate(scan_part_file(part_path)):
                pairs.append((part_path, local_index, m, n))
        datasets[name] = pairs

    if not datasets:
        log(f"ERROR: no dataset folders with part_*.txt files found under '{DATASETS_DIR}/'.")
        return None
    return datasets


def blank_row(fieldnames, known, status):
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


def load_existing_results(dataset_names):
    """Reconstructs the completed-row sets for both passes and a cache of every
    existing op-count row -- no wall state here, see module docstring point 1."""
    done_timing = set()
    done_opcount = set()
    opcount_rows = {}

    for dataset in dataset_names:
        timing_csv = os.path.join(RESULTS_DIR, dataset, "timing_memory.csv")
        if os.path.exists(timing_csv):
            with open(timing_csv, newline="") as f:
                for row in csv.DictReader(f):
                    done_timing.add((dataset, row["algorithm"], row["pair_index"], row["repeat"]))

        opcount_csv = os.path.join(RESULTS_DIR, dataset, "opcounts.csv")
        if os.path.exists(opcount_csv):
            with open(opcount_csv, newline="") as f:
                for row in csv.DictReader(f):
                    key = (dataset, row["algorithm"], row["pair_index"])
                    done_opcount.add(key)
                    opcount_rows[key] = row

    return done_timing, done_opcount, opcount_rows


def run_and_classify(cmd, runner_fieldnames, own_fieldnames, extra, timeout):
    """Like experiment/synthetic/main.py's version, but remaps the runner's own
    fixed-position CSV line into `own_fieldnames`'s schema (pair_index/m/n/cells)
    rather than trusting the runner's self-reported N/sample, which don't mean
    the same thing here (see module docstring point 3). `extra` carries the
    known pair_index/m/n/cells/algorithm[/repeat] values this script already
    has, independent of anything the runner itself reports."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return blank_row(own_fieldnames, extra, "timeout"), "timeout"

    line = result.stdout.strip()
    values = line.split(",") if line else []
    if result.returncode != 0 or len(values) != len(runner_fieldnames):
        return blank_row(own_fieldnames, extra, "oom"), "oom"

    parsed = dict(zip(runner_fieldnames, values))
    row = {k: v for k, v in parsed.items() if k not in ("N", "sample")}
    row.update(extra)
    return row, row["status"]


def check_cross_agreement(dataset, pair_index, opcount_rows):
    results = []
    for algorithm in ALGORITHMS:
        row = opcount_rows.get((dataset, algorithm, str(pair_index)))
        if row is not None and row["status"] == "ok":
            results.append((algorithm, float(row["frechet_dist"])))
    if len(results) < 2:
        return True
    distances = [d for _, d in results]
    if max(distances) - min(distances) > 1e-9:
        log(f"WARNING: {dataset} pair={pair_index}: algorithms disagree on "
            f"frechet_distance -- {results}")
        return False
    return True


def main():
    global _log_file

    os.makedirs(RESULTS_DIR, exist_ok=True)
    _log_file = open(LOG_PATH, "a")

    log("Starting real-world run.")

    if not os.path.exists(RUNNER) or not os.path.exists(RUNNER_COUNTED):
        log("ERROR: runner binaries not found. Run: cd experiment && make")
        sys.exit(1)

    datasets = discover_datasets()
    if datasets is None:
        sys.exit(1)

    log(f"Discovered {len(datasets)} dataset(s): "
        + ", ".join(f"{name} ({len(pairs)} pairs)" for name, pairs in datasets.items()))

    for name in datasets:
        os.makedirs(os.path.join(RESULTS_DIR, name), exist_ok=True)

    done_timing, done_opcount, opcount_rows = load_existing_results(datasets.keys())
    log(f"Existing results: {len(done_timing)} timing row(s), {len(done_opcount)} op-count row(s)")

    for dataset in sorted(datasets):
        pairs = datasets[dataset]
        log(f"=== dataset: {dataset} ({len(pairs)} pairs) ===")
        timing_csv = os.path.join(RESULTS_DIR, dataset, "timing_memory.csv")
        opcount_csv = os.path.join(RESULTS_DIR, dataset, "opcounts.csv")

        for pair_index, (part_path, local_index, m, n) in enumerate(pairs):
            log(f"--- pair={pair_index} (m={m}, n={n}, cells={m*n}) ---")
            extra_base = {"pair_index": pair_index, "m": m, "n": n, "cells": m * n}

            log("runtime/memory pass")
            for repeat in range(REPEAT):
                for algorithm in ALGORITHMS:
                    key = (dataset, algorithm, str(pair_index), str(repeat))
                    if key in done_timing:
                        log(f"  repeat={repeat} {algorithm}: SKIP (already completed)")
                        continue

                    log(f"  repeat={repeat} {algorithm}: running...")
                    cmd = [RUNNER, algorithm, part_path, str(local_index)]
                    extra = {"algorithm": algorithm, **extra_base, "repeat": repeat}
                    row, status = run_and_classify(cmd, RUNNER_TIMING_FIELDS, TIMING_FIELDS, extra, timeout=TIMEOUT)

                    log(f"  repeat={repeat} {algorithm}: status={status}")
                    append_row(timing_csv, TIMING_FIELDS, row)
                    done_timing.add(key)

            log("op-count pass")
            for algorithm in ALGORITHMS:
                key = (dataset, algorithm, str(pair_index))
                if key in done_opcount:
                    log(f"  {algorithm}: SKIP (already completed)")
                    continue

                log(f"  {algorithm}: running...")
                cmd = [RUNNER_COUNTED, algorithm, part_path, str(local_index)]
                extra = {"algorithm": algorithm, **extra_base}
                row, status = run_and_classify(cmd, RUNNER_OPCOUNT_FIELDS, OPCOUNT_FIELDS, extra, timeout=TIMEOUT)

                log(f"  {algorithm}: status={status}")
                append_row(opcount_csv, OPCOUNT_FIELDS, row)
                done_opcount.add(key)
                opcount_rows[key] = row

            ok = check_cross_agreement(dataset, pair_index, opcount_rows)
            log("cross-algorithm agreement: ok" if ok else "cross-algorithm agreement: FAIL")

    log("All runs complete.")


if __name__ == "__main__":
    main()
