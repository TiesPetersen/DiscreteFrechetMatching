// Runs one algorithm on one sample curve pair and prints one CSV line with the
// results. Invoked by experiment/main.py, once per (algorithm, N, sample[, repeat]).
//
// Compiled twice from this same file (see experiment/Makefile):
//   - plain build:        measures runtime + memory (getrusage), used for the
//                          timing/memory pass.
//   - COUNT_OPS build:     measures operation counts instead, used for the
//                          op-count pass. Deterministic, so only needs one run
//                          per sample (see PLAN.md 5.2 for why these are kept separate).
//
// usage: runner <BBMSCore|BBMSInter|BBMSDppInstant|BBMSDppStepwise|DijkstraPrims> <dataset_file> <sample_index>

#include "common.h"
#include "bbms_core.h"
#include "bbms_inter.h"
#include "bbms_dpp_instant.h"
#include "bbms_dpp_stepwise.h"
#include "bbms_dpp_instant_lean.h"
#include "bbms_dpp_stepwise_lean.h"
#include "dijkstra_prims.h"
#include "counters.h"

#include <chrono>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <string>
#include <sys/resource.h>

// Reads sample number `sample_index` out of a dataset file. See PSEUDOCODE.md for
// the file format. Earlier samples are parsed and discarded rather than skipped
// byte-for-byte -- simpler code, and the file sizes involved make this cheap enough.
static void load_sample(const std::string& path, int sample_index, Curve& p, Curve& q) {
    std::ifstream in(path);
    if (!in) {
        std::cerr << "cannot open dataset file: " << path << "\n";
        std::exit(1);
    }

    int sample_count;
    in >> sample_count;
    if (sample_index < 0 || sample_index >= sample_count) {
        std::cerr << "sample index " << sample_index << " out of range (file has "
                   << sample_count << " samples)\n";
        std::exit(1);
    }

    for (int s = 0; s <= sample_index; ++s) {
        int m;
        in >> m;
        p.resize(m);
        for (int i = 0; i < m; ++i) in >> p[i].x >> p[i].y;

        int n;
        in >> n;
        q.resize(n);
        for (int i = 0; i < n; ++i) in >> q[i].x >> q[i].y;
    }
}

static MatchingAndFrechetDistance run_algorithm(const std::string& algorithm, const Curve& p, const Curve& q) {
    if (algorithm == "BBMSCore")        return bbms_core(p, q);
    if (algorithm == "BBMSInter")       return bbms_inter(p, q);
    if (algorithm == "BBMSDppInstant")  return bbms_dpp_instant(p, q);
    if (algorithm == "BBMSDppStepwise") return bbms_dpp_stepwise(p, q);
    if (algorithm == "BBMSDppInstantLean")  return bbms_dpp_instant_lean(p, q);
    if (algorithm == "BBMSDppStepwiseLean") return bbms_dpp_stepwise_lean(p, q);
    if (algorithm == "DijkstraPrims")   return dijkstra_prims(p, q);
    std::cerr << "unknown algorithm: " << algorithm << "\n";
    std::exit(1);
}

#ifndef COUNT_OPS

// ru_maxrss is reported in bytes on macOS, but kilobytes on Linux -- this converts
// either one to megabytes so the two platforms produce directly comparable numbers.
static double maxrss_to_mb(long raw) {
#ifdef __APPLE__
    return raw / (1024.0 * 1024.0);
#else
    return raw / 1024.0;
#endif
}

// Peak memory of this process so far, in MB.
//
// On Linux, ru_maxrss is kept across execve, so a runner started by a Python
// script begins with that script's peak (about 34 MB in the November 2026 AWS
// run). Every pair that needed less than that showed the same value. VmHWM in
// /proc/self/status is the peak of this program alone, so Linux reads that.
// macOS has no such carry-over, so it keeps ru_maxrss.
static double peak_memory_mb(const struct rusage& usage) {
#ifdef __linux__
    std::ifstream status("/proc/self/status");
    std::string line;
    while (std::getline(status, line)) {
        if (line.rfind("VmHWM:", 0) == 0) return std::stol(line.substr(6)) / 1024.0;  // "VmHWM:   1234 kB"
    }
#endif
    return maxrss_to_mb(usage.ru_maxrss);
}

static double timeval_diff_s(const struct timeval& a, const struct timeval& b) {
    return (a.tv_sec - b.tv_sec) + (a.tv_usec - b.tv_usec) / 1e6;
}

// Times one algorithm call and measures its memory/fault/context-switch behavior via
// getrusage(), snapshotted immediately before and after the call so curve loading
// doesn't pollute the measurement. Prints one CSV line: on failure, every field past
// `status` is -1 (a run that didn't finish has nothing valid to report).
static void run_timing_and_memory(const std::string& algorithm, long long N, int sample_index,
                                   const Curve& p, const Curve& q) {
    std::string status = "ok";
    double runtime_s = -1, frechet = -1;
    double maxrss_before_mb = -1, maxrss_after_mb = -1;
    long long minor_faults = -1, major_faults = -1;
    long long block_input_ops = -1, block_output_ops = -1;
    long long voluntary_ctx_sw = -1, involuntary_ctx_sw = -1;
    double user_time_s = -1, sys_time_s = -1, blocked_time_s = -1;

    try {
        struct rusage before{}, after{};
        getrusage(RUSAGE_SELF, &before);
        maxrss_before_mb = peak_memory_mb(before);  // read now: on Linux it is read live, not from `before`

        auto t0 = std::chrono::steady_clock::now();
        MatchingAndFrechetDistance result = run_algorithm(algorithm, p, q);
        auto t1 = std::chrono::steady_clock::now();

        getrusage(RUSAGE_SELF, &after);

        runtime_s = std::chrono::duration<double>(t1 - t0).count();
        frechet   = result.frechet_distance;

        maxrss_after_mb    = peak_memory_mb(after);
        minor_faults       = after.ru_minflt  - before.ru_minflt;
        major_faults       = after.ru_majflt  - before.ru_majflt;
        block_input_ops    = after.ru_inblock - before.ru_inblock;
        block_output_ops   = after.ru_oublock - before.ru_oublock;
        voluntary_ctx_sw   = after.ru_nvcsw   - before.ru_nvcsw;
        involuntary_ctx_sw = after.ru_nivcsw  - before.ru_nivcsw;
        user_time_s        = timeval_diff_s(after.ru_utime, before.ru_utime);
        sys_time_s          = timeval_diff_s(after.ru_stime, before.ru_stime);
        blocked_time_s      = runtime_s - (user_time_s + sys_time_s);
    } catch (const std::bad_alloc&) {
        // Secondary OOM path only -- on Linux, an OOM is more likely to kill this
        // process outright than to raise bad_alloc. main.py detects that case by
        // noticing the child process was killed (see PLAN.md 5.5).
        status = "oom";
    } catch (...) {
        status = "error";
    }

    std::cout << algorithm << "," << N << "," << sample_index << ","
               << runtime_s << "," << std::setprecision(17) << frechet << std::setprecision(6) << ","
               << maxrss_before_mb << "," << maxrss_after_mb << ","
               << minor_faults << "," << major_faults << ","
               << block_input_ops << "," << block_output_ops << ","
               << voluntary_ctx_sw << "," << involuntary_ctx_sw << ","
               << user_time_s << "," << sys_time_s << "," << blocked_time_s << ","
               << status << "\n";
}

#else

// Runs one algorithm and prints its operation counts. No timing, no repeats needed --
// counts are deterministic given the same input.
static void run_op_counts(const std::string& algorithm, long long N, int sample_index,
                           const Curve& p, const Curve& q) {
    std::string status = "ok";
    double frechet = -1;
    long long total_nca_steps = -1, cells_processed = -1;
    double pct_cells_explored = -1;
    double avg_heap_size = -1;

    g_counters = Counters{};
    try {
        MatchingAndFrechetDistance result = run_algorithm(algorithm, p, q);
        frechet = result.frechet_distance;
        total_nca_steps = g_counters.nca_regular_hops + g_counters.nca_shortcut_hops;

        // cells_processed: a cross-algorithm-comparable column. For BBMS this is
        // m*n exactly -- known the instant the curves are loaded, not measured --
        // never m*n unless the run actually succeeded (see PLAN.md 4).
        long long m = (long long)p.size(), n = (long long)q.size();
        if (algorithm == "BBMSCore" || algorithm == "BBMSInter" ||
            algorithm == "BBMSDppInstant" || algorithm == "BBMSDppStepwise" ||
            algorithm == "BBMSDppInstantLean" || algorithm == "BBMSDppStepwiseLean") {
            cells_processed = m * n;
        } else {
            cells_processed = g_counters.heap_pops;
        }
        pct_cells_explored = 100.0 * (double)cells_processed / (double)(m * n);

        // avg_heap_size: sum_heap_size is sampled once per pop (see dijkstra_prims.cpp),
        // so dividing by heap_pops gives the average queue size across those samples.
        // Stays -1 (not 0) for BBMS algorithms, where heap_pops is always 0 -- "never
        // measured" and "measured as zero" shouldn't look the same.
        if (g_counters.heap_pops > 0) {
            avg_heap_size = (double)g_counters.sum_heap_size / (double)g_counters.heap_pops;
        }
    } catch (const std::bad_alloc&) {
        status = "oom";
    } catch (...) {
        status = "error";
    }

    std::cout << algorithm << "," << N << "," << sample_index << "," << std::setprecision(17) << frechet << std::setprecision(6) << ","
               << g_counters.nca_regular_hops << "," << g_counters.nca_shortcut_hops << ","
               << total_nca_steps << "," << g_counters.shortcuts_written << ","
               << g_counters.dead_paths_pruned << "," << g_counters.shortcuts_extended << ","
               << g_counters.dead_path_walk_steps << ","
               << g_counters.heap_pushes << "," << g_counters.heap_pops << ","
               << g_counters.max_heap_size << "," << avg_heap_size << ","
               << cells_processed << "," << pct_cells_explored << "," << status << "\n";
}

#endif

int main(int argc, char* argv[]) {
    if (argc != 4) {
        std::cerr << "usage: runner <BBMSCore|BBMSInter|DijkstraPrims> <dataset_file> <sample_index>\n";
        return 1;
    }
    std::string algorithm    = argv[1];
    std::string dataset_file = argv[2];
    int sample_index         = std::stoi(argv[3]);

    Curve p, q;
    load_sample(dataset_file, sample_index, p, q);
    long long N = (long long)p.size();  // m = n = N by construction (see PLAN.md 1)

#ifndef COUNT_OPS
    run_timing_and_memory(algorithm, N, sample_index, p, q);
#else
    run_op_counts(algorithm, N, sample_index, p, q);
#endif

    return 0;
}
