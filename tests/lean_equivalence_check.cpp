// Usage: ./lean_equivalence_check.exe [num_trials]
//
// Checks that the lean memory layout does not change the algorithm. Each lean DPP variant
// must make the same parent choice at every cell as its current version, return the same
// matching and distance, and produce the same operation counts.
// Inputs: random curves, random curves with many ties, and the first pair of each synthetic
// dataset at N=500.

#include "common.h"
#include "bbms_dpp_instant.h"
#include "bbms_dpp_stepwise.h"
#include "bbms_dpp_instant_lean.h"
#include "bbms_dpp_stepwise_lean.h"
#include "counters.h"
#include "parent_trace.h"
#include "utils.h"

#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <string>
#include <vector>

namespace {

using Run = MatchingAndFrechetDistance (*)(const Curve&, const Curve&);

struct Pair {
    std::string name;
    Run current, lean;
};

struct Outcome {
    MatchingAndFrechetDistance result;
    std::vector<long long> trace;
    Counters counters;
};

// Runs one algorithm and keeps its result, its parent choices and its counters
Outcome run(Run algorithm, const Curve& p, const Curve& q) {
    g_parent_trace.clear();
    g_counters = Counters{};
    Outcome outcome{algorithm(p, q), {}, {}};
    outcome.trace = g_parent_trace;
    outcome.counters = g_counters;
    return outcome;
}

// Names every counter that differs; empty if all are equal
std::string counter_differences(const Counters& a, const Counters& b) {
    std::string out;
    auto check = [&](const char* name, long long x, long long y) {
        if (x != y) out += std::string(" ") + name + " " + std::to_string(x) + "!=" + std::to_string(y);
    };
    check("nca_regular_hops", a.nca_regular_hops, b.nca_regular_hops);
    check("nca_shortcut_hops", a.nca_shortcut_hops, b.nca_shortcut_hops);
    check("shortcuts_written", a.shortcuts_written, b.shortcuts_written);
    check("dead_paths_pruned", a.dead_paths_pruned, b.dead_paths_pruned);
    check("shortcuts_extended", a.shortcuts_extended, b.shortcuts_extended);
    check("dead_path_walk_steps", a.dead_path_walk_steps, b.dead_path_walk_steps);
    return out;
}

// Compares the lean variant with the current one on one input; prints and returns false on a difference
bool same(const Pair& pair, const Curve& p, const Curve& q, const std::string& input) {
    Outcome a = run(pair.current, p, q), b = run(pair.lean, p, q);
    std::string problem;
    if (a.trace != b.trace) problem += " parent choices differ;";
    if (a.result.matching != b.result.matching) problem += " matchings differ;";
    if (a.result.frechet_distance != b.result.frechet_distance) problem += " distances differ;";
    std::string counters = counter_differences(a.counters, b.counters);
    if (!counters.empty()) problem += " counters differ:" + counters;
    if (problem.empty()) return true;
    std::printf("FAIL  %s  %s (m=%zu, n=%zu):%s\n", pair.name.c_str(), input.c_str(), p.size(), q.size(), problem.c_str());
    return false;
}

// Rounds every coordinate down to an integer, which creates many equal distances
void make_ties(Curve& curve) {
    for (auto& point : curve) { point.x = (int) point.x; point.y = (int) point.y; }
}

// Reads the first pair of a dataset file; returns false if the file is missing
bool read_first_pair(const std::string& path, Curve& p, Curve& q) {
    std::ifstream in(path);
    if (!in) return false;
    int count, m, n;
    in >> count >> m;
    p.resize(m);
    for (auto& point : p) in >> point.x >> point.y;
    in >> n;
    q.resize(n);
    for (auto& point : q) in >> point.x >> point.y;
    return (bool) in;
}

} // namespace

int main(int argc, char* argv[]) {
    // Default to 300 trials per kind of random input
    long long num_trials = (argc > 1) ? std::atoll(argv[1]) : 300;

    std::vector<Pair> pairs = {
        {"BBMSDppStepwiseLean", bbms_dpp_stepwise, bbms_dpp_stepwise_lean},
        {"BBMSDppInstantLean", bbms_dpp_instant, bbms_dpp_instant_lean},
    };

    auto start_time = std::chrono::steady_clock::now();
    long long checks = 0, failures = 0;

    for (const Pair& pair : pairs) {
        // Random curves with lengths 1 to 300
        for (long long trial = 0; trial < num_trials; ++trial) {
            auto [p, q] = make_random_curves(1, 300, (unsigned) trial);
            failures += !same(pair, p, q, "random trial " + std::to_string(trial));
            ++checks;
        }

        // Random curves with many ties, lengths 1 to 80
        for (long long trial = 0; trial < num_trials; ++trial) {
            auto [p, q] = make_random_curves(1, 80, (unsigned) trial + 100000, 4.0);
            make_ties(p);
            make_ties(q);
            failures += !same(pair, p, q, "tie trial " + std::to_string(trial));
            ++checks;
        }

        // The first pair of every synthetic dataset at N=500
        for (const char* dataset : {"identical", "random", "outlier", "outlier_swapped", "alternating",
                                    "alternating_swapped", "alternating_cheap_column"}) {
            Curve p, q;
            std::string path = std::string("../datasets/synthetic/") + dataset + "/N_500.txt";
            if (!read_first_pair(path, p, q)) {
                std::printf("FAIL  cannot read %s\n", path.c_str());
                ++failures;
                continue;
            }
            failures += !same(pair, p, q, dataset);
            ++checks;
        }
    }

    // Print a summary
    double seconds = std::chrono::duration<double>(std::chrono::steady_clock::now() - start_time).count();
    std::printf("%lld comparisons, %lld failure(s)  (%.2fs)\n", checks, failures, seconds);
    return failures == 0 ? 0 : 1;
}
