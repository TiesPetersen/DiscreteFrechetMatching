"""
The AWS run of November 2026: a fixed list of jobs, run one at a time.

Each job runs one algorithm on one curve pair, either timed (runner.exe) or with
operation counts (runner_counted.exe). Jobs come in blocks, in the order below, so
the most important results exist first if the run is stopped early:

  A  before and after the audit fixes: the old code (08ca567) against the new code
  B  main comparison with the final code, all synthetic datasets, up to N=11000
  C  current DPP (vector lists) against the lean DPP, memory and time
  D  real-world datasets with the fixed projection, and pigeons without repeated points
  E  main comparison at the largest sizes, N=18000 and N=30000

Resumable: a job already in a results file is skipped. Once an algorithm fails
(timeout or out of memory) on some pair, larger pairs of the same block, dataset,
code and pass are skipped for it.

Run from the project root:
    python3 experiment/aws_2026_11/run_plan.py --dry-run   # list the jobs and the worst-case time
    python3 experiment/aws_2026_11/run_plan.py             # run them
"""

import argparse
import csv
import glob
import os
import subprocess
import sys
import time

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(PROJECT_ROOT)

RESULTS_DIR = "results_aws_2026_11"
LOG_PATH = os.path.join(RESULTS_DIR, "run.log")

# Runner binaries per code version: "new" is this branch, "old" is 08ca567 built in old_code/
RUNNERS = {
    ("new", "time"): "experiment/runner.exe",
    ("new", "count"): "experiment/runner_counted.exe",
    ("old", "time"): "old_code/experiment/runner.exe",
    ("old", "count"): "old_code/experiment/runner_counted.exe",
}

TIMING_FIELDS = [
    "algorithm", "N", "sample", "runtime_s", "frechet_dist",
    "maxrss_before_mb", "maxrss_after_mb", "minor_faults", "major_faults",
    "block_input_ops", "block_output_ops",
    "voluntary_ctx_switches", "involuntary_ctx_switches",
    "user_time_s", "sys_time_s", "blocked_time_s", "status",
]
COUNT_FIELDS = [
    "algorithm", "N", "sample", "frechet_dist",
    "nca_regular_hops", "nca_shortcut_hops", "total_nca_steps", "shortcuts_written",
    "dead_paths_pruned", "shortcuts_extended", "dead_path_walk_steps",
    "heap_pushes", "heap_pops", "max_heap_size", "avg_heap_size",
    "cells_processed", "pct_cells_explored", "status",
]
JOB_FIELDS = ["job_id", "block", "code", "dataset", "file", "pair", "m", "n", "cells", "repeat", "wall_s", "outcome"]
FAILURES = {"timeout", "oom", "crash"}

BBMS_OLD_NAMES = ["BBMSCore", "BBMSInter", "BBMSDppStepwise", "BBMSDppInstant"]
LEAN = ["BBMSDppStepwiseLean", "BBMSDppInstantLean"]


# --- Building the job list ---------------------------------------------------

def synthetic_file(dataset, n):
    return f"datasets/synthetic/{dataset}/N_{n}.txt"


def real_world_pairs(dataset):
    """Every pair of a real-world dataset as (file, index in file, m, n), in file order."""
    pairs = []
    for path in sorted(glob.glob(f"datasets/real-world/{dataset}/part_*.txt")):
        with open(path) as f:
            words = f.read().split()
        k = 1
        for index in range(int(words[0])):
            m = int(words[k]); k += 1 + 2 * m
            n = int(words[k]); k += 1 + 2 * n
            pairs.append((path, index, m, n))
    return pairs


def job(block, code, kind, algorithm, dataset, path, sample, m, n, timeout, repeat=0):
    job_id = f"{block}|{code}|{kind}|{algorithm}|{dataset}|{os.path.basename(path)}|{sample}|{repeat}"
    return dict(job_id=job_id, block=block, code=code, kind=kind, algorithm=algorithm, dataset=dataset,
                file=path, sample=sample, m=m, n=n, cells=m * n, timeout=timeout, repeat=repeat)


def synthetic_jobs(block, code, algorithms, datasets_and_samples, sizes, kinds, timeout, repeats=1):
    """Every combination, ordered by size first so smaller sizes finish before larger ones."""
    jobs = []
    for n in sizes:
        for dataset, samples in datasets_and_samples:
            for sample in samples:
                for kind in kinds:
                    for repeat in range(repeats if kind == "time" else 1):
                        for algorithm in algorithms:
                            jobs.append(job(block, code, kind, algorithm, dataset, synthetic_file(dataset, n),
                                            sample, n, n, timeout, repeat))
    return jobs


def block_a():
    """Before and after the audit fixes, same machine: two NCA queries, list removal from the back, orientation."""
    jobs = []
    sets = [("random", [0]), ("outlier", [0]), ("alternating", [0]), ("alternating_swapped", [0])]
    for code in ["old", "new"]:
        # Everything at N=2300; BBMSCore and BBMSInter are cubic on alternating, so no larger N for them there
        jobs += synthetic_jobs("A", code, BBMS_OLD_NAMES + ["DijkstraPrims"], sets, [2300], ["time", "count"], 600)
        jobs += synthetic_jobs("A", code, BBMS_OLD_NAMES + ["DijkstraPrims"], sets[:2], [3900], ["time", "count"], 600)
        jobs += synthetic_jobs("A", code, ["BBMSDppStepwise", "BBMSDppInstant", "DijkstraPrims"], sets[2:], [3900], ["time", "count"], 600)
        jobs += synthetic_jobs("A", code, ["BBMSDppStepwise", "BBMSDppInstant", "DijkstraPrims"],
                               [("random", [0]), ("alternating", [0])], [11000], ["time", "count"], 900)
    return jobs


PLAIN_SETS = [("random", [0, 1, 2]), ("identical", [0]), ("outlier", [0, 1]), ("outlier_swapped", [0, 1])]
ALTERNATING_SETS = [("alternating", [0, 1]), ("alternating_swapped", [0, 1]), ("alternating_cheap_column", [0, 1])]


def block_b():
    """Main comparison with the final code up to N=11000. On the alternating sets, BBMSCore and BBMSInter
    take about N steps per cell, so they only run at N=2300 there; at 6500 they would hit the time limit."""
    jobs = []
    everything = ["BBMSCore", "BBMSInter"] + LEAN + ["DijkstraPrims"]
    jobs += synthetic_jobs("B", "new", everything, PLAIN_SETS + ALTERNATING_SETS, [2300], ["time", "count"], 900)
    jobs += synthetic_jobs("B", "new", ["BBMSCore"], PLAIN_SETS, [6500], ["time", "count"], 900)
    jobs += synthetic_jobs("B", "new", ["BBMSInter"], PLAIN_SETS, [6500, 11000], ["time", "count"], 900)
    jobs += synthetic_jobs("B", "new", LEAN + ["DijkstraPrims"], PLAIN_SETS + ALTERNATING_SETS, [6500, 11000], ["time", "count"], 900)
    return sorted(jobs, key=lambda j: j["cells"])


def block_c():
    """Current DPP (vector lists, no reuse) against the lean DPP at large sizes; the lean side is in blocks B and E."""
    sets = [("random", [0]), ("alternating", [0])]
    return synthetic_jobs("C", "new", ["BBMSDppStepwise", "BBMSDppInstant"], sets, [11000, 18000, 30000], ["time"], 1800)


def block_d():
    """Real-world datasets with the fixed projection, plus pigeons without repeated points."""
    jobs = []
    everything = ["BBMSCore", "BBMSInter"] + LEAN + ["DijkstraPrims"]
    for dataset in ["drifter", "geolife", "pigeons_dedup"]:
        for path, index, m, n in real_world_pairs(dataset):
            for kind in ["time", "count"]:
                for algorithm in everything:
                    jobs.append(job("D", "new", kind, algorithm, dataset, path, index, m, n, 300))

    # Pigeons with repeated points: the fast algorithms on every pair, the slow ones only below 1e8 cells,
    # and the current DPP everywhere, to show where it runs out of memory and the lean DPP does not
    for path, index, m, n in real_world_pairs("pigeons"):
        for kind in ["time", "count"]:
            algorithms = ["BBMSDppStepwiseLean", "DijkstraPrims"]
            if m * n < 1e8:
                algorithms += ["BBMSInter", "BBMSDppInstantLean"]
            if kind == "time" and (m * n < 1e8 or m * n > 6e8):
                algorithms += ["BBMSDppStepwise"]   # small pairs to compare, the largest to show it runs out of memory
            for algorithm in algorithms:
                jobs.append(job("D", "new", kind, algorithm, "pigeons", path, index, m, n, 600))
    return sorted(jobs, key=lambda j: (j["dataset"], j["cells"]))


def block_e():
    """Main comparison at the largest sizes; only the algorithms that can get there."""
    sets = [("random", [0, 1]), ("outlier", [0]), ("alternating", [0]), ("alternating_swapped", [0]),
            ("alternating_cheap_column", [0])]
    jobs = []
    jobs += synthetic_jobs("E", "new", ["BBMSInter"], sets[:2], [18000], ["time"], 1200)
    jobs += synthetic_jobs("E", "new", LEAN + ["DijkstraPrims"], sets, [18000], ["time"], 1200)
    jobs += synthetic_jobs("E", "new", ["BBMSDppStepwiseLean", "DijkstraPrims"], sets, [30000], ["time"], 1800)
    return jobs


def all_jobs():
    return block_a() + block_b() + block_c() + block_d() + block_e()


# --- Running ----------------------------------------------------------------

def log(message):
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')}  {message}"
    print(line, flush=True)
    with open(LOG_PATH, "a") as f:
        f.write(line + "\n")


def results_path(kind):
    return os.path.join(RESULTS_DIR, "timing.csv" if kind == "time" else "counts.csv")


def load_done():
    """Job ids already in the results files, and the failures seen so far."""
    done, failures = set(), []
    for kind in ["time", "count"]:
        path = results_path(kind)
        if not os.path.exists(path):
            continue
        with open(path) as f:
            for row in csv.DictReader(f):
                done.add(row["job_id"])
                if row["outcome"] in FAILURES:
                    failures.append(wall_key_of(row, kind) + (int(row["cells"]),))
    return done, failures


def wall_key_of(j, kind):
    return (j["block"], j["code"], kind, j["algorithm"], j["dataset"])


def run_one(j):
    """Runs one job; returns (outcome, runner fields, wall seconds)."""
    fields = TIMING_FIELDS if j["kind"] == "time" else COUNT_FIELDS
    cmd = [RUNNERS[(j["code"], j["kind"])], j["algorithm"], j["file"], str(j["sample"])]
    start = time.time()
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=j["timeout"])
    except subprocess.TimeoutExpired:
        return "timeout", {}, time.time() - start
    seconds = time.time() - start

    # Killed by a signal: on Linux that is almost always the out-of-memory killer
    if result.returncode < 0:
        return "oom", {}, seconds
    values = result.stdout.strip().split(",")
    if result.returncode != 0 or len(values) != len(fields):
        return "crash", {}, seconds
    row = dict(zip(fields, values))
    return row["status"], row, seconds


def append_result(j, outcome, row, seconds):
    fields = TIMING_FIELDS if j["kind"] == "time" else COUNT_FIELDS
    path = results_path(j["kind"])
    new_file = not os.path.exists(path)
    record = {k: j[k] for k in JOB_FIELDS if k in j}
    record.update(pair=j["sample"], wall_s=f"{seconds:.3f}", outcome=outcome, algorithm=j["algorithm"])
    record.update(row)
    with open(path, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=JOB_FIELDS + fields)
        if new_file:
            writer.writeheader()
        writer.writerow(record)


# Rough share of the cells DijkstraPrims processes, from the earlier AWS results
EXPLORED = {"identical": 0.0, "random": 0.4, "pigeons": 0.25, "pigeons_dedup": 0.25, "geolife": 0.5, "drifter": 0.56}


def estimate_seconds(j):
    """A rough guess of one job's time, from Mac measurements (13-14 Nov) in nanoseconds per cell, times 1.5
    for a slower server, and growing a little with size (cache misses). Capped at the job's time limit."""
    alternating = j["dataset"].startswith("alternating")
    side = (j["m"] * j["n"]) ** 0.5
    per_cell = {
        "BBMSDppStepwiseLean": 70, "BBMSDppInstantLean": 860 if j["dataset"] == "pigeons" else 90,
        "BBMSDppStepwise": 140, "BBMSDppInstant": 140,
        "BBMSInter": 4.9 * side if alternating else 150,
        "BBMSCore": 6.6 * side if alternating else 900 * (side / 3900) ** 0.6,
        "DijkstraPrims": 260 * EXPLORED.get(j["dataset"], 1.0),
    }[j["algorithm"]]
    if j["code"] == "old" and j["algorithm"].startswith("BBMSDpp"):
        per_cell *= 1.6
    seconds = j["cells"] * per_cell * 1e-9 * 1.5 * max(1.0, side / 2300) ** 0.2 + 0.2
    return min(seconds, j["timeout"])


def dry_run(jobs):
    """Prints how many jobs each block has, a rough time estimate, and the worst case if every job hit its time limit."""
    print(f"{'block':6s} {'jobs':>6s} {'estimate (h)':>13s} {'worst case (h)':>15s}")
    for block in "ABCDE":
        js = [j for j in jobs if j["block"] == block]
        print(f"{block:6s} {len(js):6d} {sum(map(estimate_seconds, js)) / 3600:13.1f} {sum(j['timeout'] for j in js) / 3600:15.1f}")
    print(f"{'all':6s} {len(jobs):6d} {sum(map(estimate_seconds, jobs)) / 3600:13.1f} {sum(j['timeout'] for j in jobs) / 3600:15.1f}")
    missing = sorted({j["file"] for j in jobs if not os.path.exists(j["file"])})
    print(f"missing dataset files: {len(missing)}" + ("" if not missing else f" (first: {missing[0]})"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="list the jobs and stop")
    parser.add_argument("--blocks", default="ABCDE", help="which blocks to run, for example ABD")
    parser.add_argument("--max-cells", type=float, default=None, help="skip pairs with more cells (for a quick test)")
    args = parser.parse_args()

    # Build the job list
    jobs = [j for j in all_jobs() if j["block"] in args.blocks]
    if args.max_cells is not None:
        jobs = [j for j in jobs if j["cells"] <= args.max_cells]
    if args.dry_run:
        dry_run(jobs)
        return

    # Check the runners and load what is already done
    os.makedirs(RESULTS_DIR, exist_ok=True)
    for (code, kind), path in RUNNERS.items():
        if any(j["code"] == code for j in jobs) and not os.path.exists(path):
            sys.exit(f"missing runner {path}; see experiment/aws_2026_11/README.md")
    done, failures = load_done()
    log(f"start: {len(jobs)} jobs, {len(done)} already done")

    # Run the jobs in order
    for number, j in enumerate(jobs, 1):
        if j["job_id"] in done:
            continue

        # Skip a pair larger than one this algorithm already failed on
        key = wall_key_of(j, j["kind"])
        failed_at = [cells for *k, cells in failures if tuple(k) == key]
        if failed_at and j["cells"] >= min(failed_at):
            continue

        outcome, row, seconds = run_one(j)
        append_result(j, outcome, row, seconds)
        if outcome in FAILURES:
            failures.append(key + (j["cells"],))
        log(f"{number}/{len(jobs)} {j['block']} {j['code']} {j['kind']} {j['algorithm']} {j['dataset']} "
            f"{os.path.basename(j['file'])}:{j['sample']} -> {outcome} in {seconds:.1f}s")

    log("all jobs done")


if __name__ == "__main__":
    main()
