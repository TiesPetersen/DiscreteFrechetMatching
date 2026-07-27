"""
Main experiment orchestrator. Runs runner.exe / runner_counted.exe across every
(dataset, N, sample[, repeat], algorithm) combination and writes the results to
results/<dataset>/timing_memory.csv and opcounts.csv.

Unlike the previous version, every dataset-shaped parameter (which datasets exist,
the N grid, K samples per (dataset, N)) is discovered directly from the files under
datasets/ instead of being hardcoded here -- so the files are the single source of
truth and can't drift out of sync with what this script assumes. REPEAT and TIMEOUT
are the only parameters that can't be derived from the dataset files themselves.

Resumable: on restart, already-completed rows are skipped. If a run hits `timeout`
or `oom` for a given (dataset, algorithm) at some N, that (dataset, algorithm) is
never attempted again at that N or any larger N -- cost only grows with N, so a
bigger N is essentially certain to fail again too. This applies across both the
timing/memory pass and the op-count pass: a failure in either one walls both.

Run from the project root:
    python3 experiment/main.py
"""

import csv
import os
import re
import subprocess
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(PROJECT_ROOT)

AMSTERDAM_TZ = ZoneInfo("Europe/Amsterdam")

RUNNER         = os.path.join("experiment", "runner.exe")
RUNNER_COUNTED = os.path.join("experiment", "runner_counted.exe")

DATASETS_DIR = "datasets"
RESULTS_DIR  = "results"
LOG_PATH     = os.path.join(RESULTS_DIR, "experiment.log")

REPEAT     = 3     # timing repeats per sample -- the one parameter dataset files can't tell us
ALGORITHMS = ["BBMSCore", "BBMSInter", "BBMSDppInstant", "BBMSDppStepwise", "DijkstraPrims"]
TIMEOUT    = 7200  # seconds, timing/memory pass only -- see run_and_classify

FAILURE_STATUSES = {"timeout", "oom"}

DATASET_FILE_RE = re.compile(r"^N_(\d+)\.txt$")

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
TIMING_FIELDS = RUNNER_TIMING_FIELDS + ["repeat"]

_log_file = None


def log(msg):
    """Prints `msg` and appends it to LOG_PATH, both timestamped in Amsterdam local
    time. Opened once in append mode (not truncated) so a resumed run's log keeps
    the full history rather than losing what came before the restart."""
    line = f"{datetime.now(AMSTERDAM_TZ).strftime('%Y-%m-%d %H:%M:%S %Z')}  {msg}"
    print(line, flush=True)
    _log_file.write(line + "\n")
    _log_file.flush()


def read_dataset_header(path):
    """Reads just enough of a dataset file to get (K, first_sample_m) without
    loading the whole file -- K is the sample count on line 1, first_sample_m is
    the point count of the very first curve (p) in sample 0. A small fixed-size
    read is enough since these are just two small integers at the very start of
    the file, regardless of how large N or K are."""
    with open(path) as f:
        head = f.read(256)
    tokens = head.split()
    if len(tokens) < 2:
        return None, None
    return int(tokens[0]), int(tokens[1])


def discover_datasets():
    """Scans datasets/ and returns {dataset: {"grid": [n, ...], "k": {n: K}}},
    sorted lexicographically by dataset name and numerically ascending by N.
    Directories with no N_*.txt files (e.g. the still-empty datasets/real-world/)
    are silently excluded rather than erroring, since an empty dataset folder
    just means that dataset isn't part of this run yet.

    Returns None (after logging why) if datasets/ is missing, no dataset has any
    files, or something is inconsistent: grids must be identical across every
    dataset (K may legitimately differ between individual files), and each file's
    filename-claimed N must match the actual point count of its first curve."""
    if not os.path.isdir(DATASETS_DIR):
        log(f"ERROR: no '{DATASETS_DIR}/' folder found.")
        return None

    datasets = {}
    for name in sorted(os.listdir(DATASETS_DIR)):
        dataset_dir = os.path.join(DATASETS_DIR, name)
        if not os.path.isdir(dataset_dir):
            continue

        grid = []
        k_by_n = {}
        for filename in os.listdir(dataset_dir):
            match = DATASET_FILE_RE.match(filename)
            if not match:
                continue
            n = int(match.group(1))
            k, first_m = read_dataset_header(os.path.join(dataset_dir, filename))
            if k is None:
                log(f"ERROR: {name}/{filename} is empty or malformed.")
                return None
            if first_m != n:
                log(f"ERROR: {name}/{filename} claims N={n} but its first sample's "
                    f"p curve has {first_m} points.")
                return None
            grid.append(n)
            k_by_n[n] = k

        if not grid:
            continue  # e.g. datasets/real-world/ while it's still empty

        grid.sort()
        datasets[name] = {"grid": grid, "k": k_by_n}

    if not datasets:
        log(f"ERROR: no dataset folders with N_*.txt files found under '{DATASETS_DIR}/'.")
        return None

    reference_name = next(iter(datasets))
    reference_grid = datasets[reference_name]["grid"]
    for name, info in datasets.items():
        if info["grid"] != reference_grid:
            log(f"ERROR: grid mismatch -- '{reference_name}' has N values {reference_grid}, "
                f"but '{name}' has {info['grid']}. Every dataset must cover the same grid.")
            return None

    return datasets


def blank_row(fieldnames, known, status):
    """A row of -1 placeholders for a run that didn't produce real output -- except
    for `known`, which must be kept even on failure so a failed run can still be
    identified and wall-reconstruction on resume has something to read back."""
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


def load_existing_results(datasets):
    """Reconstructs, across every dataset at once: the completed-row sets for both
    passes, the shared per-(dataset, algorithm) wall state, and a cache of every
    existing op-count row (needed later so the cross-algorithm agreement check can
    see algorithms whose row already existed from a previous run, not just ones
    freshly run this session).

    Walls are shared between the timing and op-count passes -- a failure in either
    one permanently walls that (dataset, algorithm) at that N and everything
    larger, for both passes -- so both CSVs are scanned into the same `walls` dict."""
    done_timing = set()
    done_opcount = set()
    walls = {}
    opcount_rows = {}

    for dataset in datasets:
        timing_csv = os.path.join(RESULTS_DIR, dataset, "timing_memory.csv")
        if os.path.exists(timing_csv):
            with open(timing_csv, newline="") as f:
                for row in csv.DictReader(f):
                    done_timing.add((dataset, row["algorithm"], row["N"], row["sample"], row["repeat"]))
                    if row["status"] in FAILURE_STATUSES:
                        n = int(row["N"])
                        key = (dataset, row["algorithm"])
                        walls[key] = min(walls.get(key, n), n)

        opcount_csv = os.path.join(RESULTS_DIR, dataset, "opcounts.csv")
        if os.path.exists(opcount_csv):
            with open(opcount_csv, newline="") as f:
                for row in csv.DictReader(f):
                    key3 = (dataset, row["algorithm"], row["N"], row["sample"])
                    done_opcount.add(key3)
                    opcount_rows[key3] = row
                    if row["status"] in FAILURE_STATUSES:
                        n = int(row["N"])
                        key = (dataset, row["algorithm"])
                        walls[key] = min(walls.get(key, n), n)

    return done_timing, done_opcount, walls, opcount_rows


def run_and_classify(cmd, fieldnames, known, timeout):
    """Runs one subprocess and returns (row, status). Handles three outcomes: a
    normal exit with a parseable CSV line ("ok" or the runner's own "error"), a
    timeout, and a killed/crashed process with no usable output.

    On Linux, a process that runs out of memory is usually killed by the kernel's
    OOM killer (SIGKILL) rather than raising an exception the runner could catch --
    so an unparseable result from an otherwise-completed run is treated as OOM.

    `timeout=None` disables the subprocess timeout entirely -- used by the op-count
    pass, which only ever attempts (dataset, algorithm, N) combinations the timing
    pass already succeeded at, so a timeout there was never expected to fire."""
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


def check_cross_agreement(dataset, n, sample, opcount_rows):
    """Checks that every algorithm which reports status=ok on this exact
    (dataset, N, sample) instance agrees on frechet_distance. Reads from the shared
    opcount_rows cache rather than the CSV on disk, so it sees algorithms whose row
    already existed from a previous run just as well as ones freshly run this
    session -- a resumed run must not silently skip half the comparison just
    because those specific rows weren't (re-)written this time."""
    results = []
    for algorithm in ALGORITHMS:
        row = opcount_rows.get((dataset, algorithm, str(n), str(sample)))
        if row is not None and row["status"] == "ok":
            results.append((algorithm, float(row["frechet_dist"])))

    if len(results) < 2:
        return True

    distances = [d for _, d in results]
    if max(distances) - min(distances) > 1e-9:
        log(f"WARNING: {dataset} N={n} sample={sample}: algorithms disagree on "
            f"frechet_distance -- {results}")
        return False
    return True


def main():
    global _log_file

    os.makedirs(RESULTS_DIR, exist_ok=True)
    _log_file = open(LOG_PATH, "a")

    log("Starting run.")

    if not os.path.exists(RUNNER) or not os.path.exists(RUNNER_COUNTED):
        log("ERROR: runner binaries not found. Run: cd experiment && make")
        sys.exit(1)

    datasets = discover_datasets()
    if datasets is None:
        sys.exit(1)

    reference_grid = next(iter(datasets.values()))["grid"]
    log(f"Discovered {len(datasets)} dataset(s): {', '.join(datasets)}")
    log(f"Grid ({len(reference_grid)} points): {reference_grid}")
    for name, info in datasets.items():
        k_values = sorted(set(info["k"].values()))
        if len(k_values) == 1:
            log(f"  {name}: K={k_values[0]} for every N")
        else:
            log(f"  {name}: K varies by N -- {info['k']}")

    for name in datasets:
        os.makedirs(os.path.join(RESULTS_DIR, name), exist_ok=True)

    done_timing, done_opcount, walls, opcount_rows = load_existing_results(datasets)
    log(f"Existing results: {len(done_timing)} timing row(s), {len(done_opcount)} "
        f"op-count row(s), {len(walls)} existing wall(s)")
    for (dataset, algorithm), n in sorted(walls.items()):
        log(f"  wall: {dataset}/{algorithm} already failed at N={n} (or smaller) -- skipping N>={n}")

    for dataset in sorted(datasets):
        log(f"=== dataset: {dataset} ===")
        grid = datasets[dataset]["grid"]
        k_by_n = datasets[dataset]["k"]
        timing_csv = os.path.join(RESULTS_DIR, dataset, "timing_memory.csv")
        opcount_csv = os.path.join(RESULTS_DIR, dataset, "opcounts.csv")

        for n in grid:
            log(f"--- N={n} ---")
            dataset_file = os.path.join(DATASETS_DIR, dataset, f"N_{n}.txt")
            k = k_by_n[n]

            for sample in range(k):
                log(f"sample={sample}")

                log("runtime/memory pass")
                for repeat in range(REPEAT):
                    for algorithm in ALGORITHMS:
                        wall = walls.get((dataset, algorithm))
                        if wall is not None and n >= wall:
                            log(f"  repeat={repeat} {algorithm}: SKIP (walled at N={wall})")
                            continue

                        key = (dataset, algorithm, str(n), str(sample), str(repeat))
                        if key in done_timing:
                            log(f"  repeat={repeat} {algorithm}: SKIP (already completed)")
                            continue

                        log(f"  repeat={repeat} {algorithm}: running...")
                        known = {"algorithm": algorithm, "N": n, "sample": sample}
                        cmd = [RUNNER, algorithm, dataset_file, str(sample)]
                        row, status = run_and_classify(cmd, RUNNER_TIMING_FIELDS, known, timeout=TIMEOUT)
                        row["repeat"] = repeat

                        if status in FAILURE_STATUSES:
                            wall_key = (dataset, algorithm)
                            walls[wall_key] = min(walls.get(wall_key, n), n)

                        log(f"  repeat={repeat} {algorithm}: status={status}")
                        append_row(timing_csv, TIMING_FIELDS, row)
                        done_timing.add(key)

                log("op-count pass")
                for algorithm in ALGORITHMS:
                    wall = walls.get((dataset, algorithm))
                    if wall is not None and n >= wall:
                        log(f"  {algorithm}: SKIP (walled at N={wall})")
                        continue

                    key3 = (dataset, algorithm, str(n), str(sample))
                    if key3 in done_opcount:
                        log(f"  {algorithm}: SKIP (already completed)")
                        continue

                    log(f"  {algorithm}: running...")
                    known = {"algorithm": algorithm, "N": n, "sample": sample}
                    cmd = [RUNNER_COUNTED, algorithm, dataset_file, str(sample)]
                    row, status = run_and_classify(cmd, OPCOUNT_FIELDS, known, timeout=None)

                    if status in FAILURE_STATUSES:
                        wall_key = (dataset, algorithm)
                        walls[wall_key] = min(walls.get(wall_key, n), n)

                    log(f"  {algorithm}: status={status}")
                    append_row(opcount_csv, OPCOUNT_FIELDS, row)
                    done_opcount.add(key3)
                    opcount_rows[key3] = row

                ok = check_cross_agreement(dataset, n, sample, opcount_rows)
                if ok:
                    log("cross-algorithm agreement: ok")

    log("All runs complete.")


if __name__ == "__main__":
    main()
