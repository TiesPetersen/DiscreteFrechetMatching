# Main Experiment: Pseudocode

Companion to `PLAN.md` — this is the pseudocode for everything still to be written
(dataset generation, the instrumented algorithms, the runner, the orchestrator).
Not literal syntax, but structured closely enough to translate directly into the
real thing.

---

## Dataset file format

One file per `(dataset, N)`, plain text, no external library needed on either the
Python (writer) or C++ (reader) side:

```
K                          # number of samples in this file
m                          # length of p, sample 0
x1 y1
x2 y2
...
n                          # length of q, sample 0
x1 y1
...
m                          # length of p, sample 1
...
                            # (repeated K times total)
```

Filenames: `datasets/<dataset>/N_<N>.txt`, e.g. `datasets/worst-case/N_7000.txt`.

---

## `datasets/generate_datasets.py`

```
function generate_worst_case(N, seed):
    rng = seeded_rng(seed)
    p = [random point in unit disk, N times]
    q = [random point in unit disk, N-1 times] + [(D, 0)]   # D = 1000, fixed outlier
    return p, q

function generate_best_case(N, seed):
    rng = seeded_rng(seed)
    p = [some random curve, N points]                        # shape doesn't matter much
    q = copy(p)                                               # identical, by definition
    return p, q

function generate_random(N, seed):
    rng = seeded_rng(seed)
    p = [uniform random point, N times]
    q = [uniform random point, N times]                       # independent draws from p
    return p, q

function write_dataset_file(path, list_of_(p,q)_pairs):
    open path for writing
    write len(list_of_pairs)
    for (p, q) in list_of_pairs:
        write len(p); write each point in p as "x y"
        write len(q); write each point in q as "x y"

function main():
    GRID = [500, 1000, 2000, 4000, 7000, 11000, 18000, 28000, 40000, 50000]
    K = 5   # uniform across all three datasets
    GENERATOR = {worst-case: generate_worst_case,
                 best-case:  generate_best_case,
                 random:     generate_random}

    for dataset_name in [worst-case, best-case, random]:
        for N in GRID:
            out_path = f"datasets/{dataset_name}/N_{N}.txt"
            if exists(out_path): continue          # idempotent — cheap, deterministic, skip if present

            samples = []
            for sample_idx in range(K):
                seed = hash(dataset_name, N, sample_idx)      # deterministic, reproducible
                samples.append(GENERATOR[dataset_name](N, seed))

            write_dataset_file(out_path, samples)
```

---

## `algorithms/counters.h` + `algorithms/counters.cpp`

One shared struct covering every algorithm's fields (each algorithm only populates
its own subset) — split into a header (declaration) and a `.cpp` (the one real
definition), so linking all three algorithms into a single runner binary doesn't
produce duplicate-symbol errors:

```
// counters.h
#pragma once
#ifdef COUNT_OPS
struct Counters {
    long long nca_regular_hops   = 0;   // BBMSCore, BBMSInter
    long long nca_shortcut_hops  = 0;   // BBMSInter only (structurally 0 for Core)
    long long shortcuts_written  = 0;   // BBMSInter only
    long long heap_pushes        = 0;   // DijkstraPrims
    long long heap_pops          = 0;   // DijkstraPrims
};
extern Counters g_counters;
#define COUNT(field) (++g_counters.field)
#else
#define COUNT(field) ((void)0)
#endif
```

```
// counters.cpp — the ONE real definition, everything else just declares `extern`
#include "counters.h"
#ifdef COUNT_OPS
Counters g_counters;
#endif
```

---

## Instrumentation additions (existing files, only the new lines)

```
// bbms_core.cpp — inside max_distance_to_nca's three while-loops
while (G[u].depth > G[v].depth) { ...; u = G[u].parent; COUNT(nca_regular_hops); }
while (G[v].depth > G[u].depth) { ...; v = G[v].parent; COUNT(nca_regular_hops); }
while (u != v) {
    ...; u = G[u].parent; COUNT(nca_regular_hops);
    ...; v = G[v].parent; COUNT(nca_regular_hops);
}
```

```
// bbms_inter.cpp — inside max_distance_to_nca, distinguish which kind of hop
if (G[v].high.target != -1) { ...; v = G[v].high.target; COUNT(nca_shortcut_hops); }
else                         { ...; v = G[v].parent;      COUNT(nca_regular_hops);  }
// (mirror for the u side using .low)

// inside update_shortcuts, one COUNT after every "G[X].low = ..." / "G[X].high = ..." line
G[A].low  = {B, G[A].distance};  COUNT(shortcuts_written);
G[C].high = {B, G[C].distance};  COUNT(shortcuts_written);
// ... (1-4 per branch, depending on which case fires)
```

```
// dijkstra_prims.cpp — main loop and neighbor-push loop
while (!pq.empty()) {
    pop(); COUNT(heap_pops);
    ...
    for each neighbor:
        if not already discovered:
            push(...); COUNT(heap_pushes);
}
```

---

## `algorithms/Makefile`

```
CXX = g++
CXXFLAGS = -O2 -std=c++17 -Wall -Wextra -I.

SRCS = BBMS/bbms_core.cpp BBMS/bbms_inter.cpp DP/dijkstra_prims.cpp counters.cpp
OBJS         = $(SRCS:.cpp=.o)
COUNTED_OBJS = $(SRCS:.cpp=_counted.o)

all: $(OBJS) $(COUNTED_OBJS)

%.o: %.cpp
	$(CXX) $(CXXFLAGS) -c -o $@ $<

%_counted.o: %.cpp
	$(CXX) $(CXXFLAGS) -DCOUNT_OPS -c -o $@ $<

clean:
	rm -f $(OBJS) $(COUNTED_OBJS)
```

---

## `experiment/runner.cpp` — the actual measurement binary, compiled twice

**`catch (bad_alloc)` is a secondary path only — it is not the primary OOM detection.**
On Linux, a huge allocation is typically satisfied virtually under default overcommit,
and the process is killed later by the kernel's OOM killer (`SIGKILL`) the moment it
touches enough of that memory — no exception is ever thrown, so this `catch` may never
fire for the exact scenario (BBMSInter/DijkstraPrims near N=50000) this experiment
most wants to observe. It's kept because it can still fire on macOS/WSL during
development, or for smaller over-limit allocations. The real OOM detection happens in
`main.py` (see below), which must independently notice the child process was killed.

Memory fields captured every run, unconditionally — the full meaningful subset of
`getrusage`, not a hand-picked selection (see the discussion this doc followed from):
`ru_maxrss` (before + after), `ru_minflt`, `ru_majflt`, `ru_inblock`, `ru_oublock`,
`ru_nvcsw`, `ru_nivcsw`, `ru_utime`, `ru_stime`, plus the derived
`wall_time - (user_time + sys_time)` "blocked time" value. Excluded: `ru_ixrss`/
`ru_idrss`/`ru_isrss` and `ru_msgsnd`/`ru_msgrcv`/`ru_nsignals` — not because they're
costly, but because they're structurally always zero for this program (never
implemented by any modern kernel, or never triggered since we use no IPC/signals).

```
#include "common.h", "bbms_core.h", "bbms_inter.h", "dijkstra_prims.h", "counters.h"
#include <sys/resource.h>, <chrono>, <fstream>, <iostream>

function load_dataset(path, sample_index) -> (Curve p, Curve q):
    open path; read K; assert sample_index < K
    skip (sample_index) earlier samples
    read m, then m points -> p
    read n, then n points -> q
    return p, q

function dispatch(name, p, q) -> MatchingAndFrechetDistance:
    match name: "BBMSCore" -> bbms_core(p,q) | "BBMSInter" -> bbms_inter(p,q)
              | "DijkstraPrims" -> dijkstra_prims(p,q)

main(argc, argv):     // argv: <algorithm> <dataset_file> <sample_index>
    algorithm, dataset_file, sample_index = parse(argv)
    p, q = load_dataset(dataset_file, sample_index)
    status = "ok"

#ifndef COUNT_OPS
    try:
        getrusage(&before)
        t0 = now(); result = dispatch(algorithm, p, q); t1 = now()
        getrusage(&after)
        runtime_s = t1 - t0
        maxrss_before, maxrss_after = before.ru_maxrss, after.ru_maxrss
        minor_faults      = after.ru_minflt  - before.ru_minflt
        major_faults       = after.ru_majflt  - before.ru_majflt
        block_input_ops    = after.ru_inblock - before.ru_inblock
        block_output_ops    = after.ru_oublock - before.ru_oublock
        voluntary_ctx_sw   = after.ru_nvcsw   - before.ru_nvcsw
        involuntary_ctx_sw = after.ru_nivcsw  - before.ru_nivcsw
        user_time_s        = timeval_diff(after.ru_utime, before.ru_utime)
        sys_time_s         = timeval_diff(after.ru_stime, before.ru_stime)
        blocked_time_s     = runtime_s - (user_time_s + sys_time_s)   // derived
    catch bad_alloc: status = "oom"
    catch ...:       status = "error"
    print_csv_line(algorithm, N=len(p), sample_index, runtime_s, result.frechet_distance,
                    maxrss_before, maxrss_after, minor_faults, major_faults,
                    block_input_ops, block_output_ops,
                    voluntary_ctx_sw, involuntary_ctx_sw,
                    user_time_s, sys_time_s, blocked_time_s, status)
#else
    g_counters = Counters{}   // reset
    try:
        result = dispatch(algorithm, p, q)
        total_nca_steps = g_counters.nca_regular_hops + g_counters.nca_shortcut_hops   // derived, no ambiguity — a plain sum, not an aggregation choice

        // cells_processed: uniform, cross-algorithm column. NOT instrumented via a
        // COUNT() for BBMS — that would just always print m*n, pure redundant
        // overhead for a value already known the instant the dataset is loaded.
        // For DijkstraPrims it's an alias of heap_pops (kept as its own column too,
        // for the PQ-specific pushes/pops story).
        if algorithm in [BBMSCore, BBMSInter]:
            cells_processed = m * n                        // known, not measured
        else:  // DijkstraPrims
            cells_processed = g_counters.heap_pops
        pct_cells_explored = 100.0 * cells_processed / (m * n)   // always 100% for BBMS, by construction
    catch bad_alloc: status = "oom"
    catch ...:       status = "error"
    // On failure, cells_processed/pct_cells_explored/total_nca_steps stay unset.
    // Reporting the "would-have-been" value on a failed run would misrepresent it
    // as successful — e.g. BBMS OOMing during its initial grid allocation never
    // processed a single cell, even though m*n is computable from the input alone.
    print_csv_line(algorithm, N=len(p), sample_index, result.frechet_distance,
                    g_counters.nca_regular_hops, g_counters.nca_shortcut_hops, total_nca_steps,
                    g_counters.shortcuts_written, g_counters.heap_pushes, g_counters.heap_pops,
                    cells_processed, pct_cells_explored, status)
#endif
```

---

## `experiment/Makefile`

```
CXX = g++
CXXFLAGS = -O2 -std=c++17 -Wall -Wextra -I../algorithms

ALGO_OBJS         = ../algorithms/BBMS/bbms_core.o ../algorithms/BBMS/bbms_inter.o \
                    ../algorithms/DP/dijkstra_prims.o ../algorithms/counters.o
ALGO_COUNTED_OBJS = <same list, _counted.o variants>

runner.exe:         runner.cpp $(ALGO_OBJS)
	$(CXX) $(CXXFLAGS) -o $@ runner.cpp $(ALGO_OBJS)

runner_counted.exe: runner.cpp $(ALGO_COUNTED_OBJS)
	$(CXX) $(CXXFLAGS) -DCOUNT_OPS -o $@ runner.cpp $(ALGO_COUNTED_OBJS)

all: runner.exe runner_counted.exe
```

---

## `experiment/main.py` — the orchestrator

```
GRID = [500, 1000, 2000, 4000, 7000, 11000, 18000, 28000, 40000, 50000]
K = 5   # uniform across all three datasets
R = 3
ALGORITHMS = [BBMSCore, BBMSInter, DijkstraPrims]
TIMEOUT_S = <calibrate>
FAILURE_STATUSES = {"timeout", "oom"}   # both trigger wall-skipping; "error" does not
                                          # (a bug/crash isn't necessarily monotonic in N)

TIMING_FIELDS   = [algorithm, N, sample, repeat, runtime_s, frechet_dist,
                    maxrss_before, maxrss_after, minor_faults, major_faults,
                    block_input_ops, block_output_ops,
                    voluntary_ctx_switches, involuntary_ctx_switches,
                    user_time_s, sys_time_s, blocked_time_s, status]
OPCOUNT_FIELDS  = [algorithm, N, sample, frechet_dist,
                    nca_regular_hops, nca_shortcut_hops, total_nca_steps, shortcuts_written,
                    heap_pushes, heap_pops, cells_processed, pct_cells_explored, status]

function load_done_and_walls(csv_path, key_fields) -> (set, dict):
    # Reconstructs BOTH the completed-row set AND the wall state from the CSV — these
    # must be seeded together on resume, not just the completed-row set with walls
    # starting empty. Otherwise resuming past an already-discovered wall re-attempts
    # those larger-N runs and burns a full timeout re-discovering what the previous
    # run had already found.
    if not exists(csv_path): return {}, {}
    rows = read_csv(csv_path)
    done  = { tuple(row[f] for f in key_fields) for row in rows }
    walls = {}
    for row in rows:
        if row.status in FAILURE_STATUSES:
            walls[row.algorithm] = min(walls.get(row.algorithm, infinity), row.N)
    return done, walls

function classify_result(out) -> (row, status):
    # Called after a subprocess.run that did NOT raise TimeoutExpired. A negative
    # returncode on Unix means the child was killed by a signal; combined with an
    # unparseable/empty stdout, that's classified as OOM. This is an INFERENCE, not
    # a direct observation of the OOM killer — the most parsimonious explanation for
    # an unexplained kill during a high-memory run near the top of the N grid, but
    # not a certainty. Confirm empirically (PLAN.md §6) before trusting it blindly.
    if out.returncode < 0 or not parseable(out.stdout):
        return blank_row(status="oom"), "oom"
    row = parse(out.stdout)
    return row, row.status   # normally "ok", but the runner can also self-report "error"

function run_timing_pass(dataset):
    csv_path = results/{dataset}/timing_memory.csv
    done, walls = load_done_and_walls(csv_path, [algorithm, N, sample, repeat])

    for N in GRID:
        dataset_file = datasets/{dataset}/N_{N}.txt
        for sample in range(K):
            for repeat in range(R):
                for algorithm in ALGORITHMS:
                    if algorithm in walls and N >= walls[algorithm]: continue
                    if (algorithm, N, sample, repeat) in done: continue

                    try:
                        out = subprocess.run([runner.exe, algorithm, dataset_file, sample],
                                              timeout=TIMEOUT_S, capture_output=True)
                        row, status = classify_result(out)
                    except TimeoutExpired:
                        row, status = blank_row(status="timeout"), "timeout"

                    row.repeat = repeat
                    if status in FAILURE_STATUSES:
                        walls[algorithm] = min(walls.get(algorithm, infinity), N)

                    append_row(csv_path, TIMING_FIELDS, row)

function run_opcount_pass(dataset):
    # Same shape as run_timing_pass (including classify_result / load_done_and_walls),
    # but: no `repeat` loop (deterministic — 1 run suffices), uses runner_counted.exe,
    # writes to opcounts.csv, own `walls` dict — separate from the timing pass's,
    # since a timing timeout and an op-count timeout aren't necessarily the same N.
    # Deliberately run as its own pass, not interleaved into run_timing_pass — the
    # fairness/interleaving concern in the plan is specifically about *timing*
    # measurements between algorithms; op-counts don't measure wall-clock time at
    # all, so there's nothing for interleaving to protect against here.
    ...
    verify_cross_algorithm_agreement(dataset)   # after the pass, using its own output

function verify_cross_algorithm_agreement(dataset):
    # Uses only already-collected data (opcounts.csv — exactly one row per
    # (algorithm, N, sample), no repeats to reconcile). Doesn't require any new runs.
    rows = read_csv(results/{dataset}/opcounts.csv)
    for (N, sample), group in group_by(rows, key=[N, sample]):
        ok_rows = [r for r in group if r.status == "ok"]
        distances = { r.frechet_distance for r in ok_rows }
        if max(distances) - min(distances) > 1e-9:      # same tolerance used elsewhere in this project
            log_warning(f"{dataset} N={N} sample={sample}: algorithms disagree on "
                        f"frechet_distance — {[(r.algorithm, r.frechet_distance) for r in ok_rows]}")
            # Not a hard failure — a real disagreement is itself a finding to
            # investigate, not something that should crash the run.

function main():
    for dataset in [worst-case, best-case, random]:
        run_timing_pass(dataset)
        run_opcount_pass(dataset)
    print("All runs complete.")
```

`TIMEOUT_S` is still the `(calibrate)` placeholder from `PLAN.md` §6 — this pseudocode
doesn't resolve that open item, it just wires up where the value plugs in.
