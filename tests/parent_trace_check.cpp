// Usage: ./parent_trace_check.exe [num_trials]

#include "common.h"
#include "bbms_core.h"
#include "bbms_inter.h"
#include "bbms_dpp_instant.h"
#include "bbms_dpp_stepwise.h"
#include "parent_trace.h"
#include "utils.h"

#include <cstdio>
#include <cstdlib>
#include <string>
#include <vector>

namespace {

struct Algorithm {
    std::string name;
    MatchingAndFrechetDistance (*run)(const Curve&, const Curve&);
};

// Runs algo and returns a copy of the parent-choice trace it left behind in g_parent_trace.
std::vector<long long> traced_run(const Algorithm& algo, const Curve& p, const Curve& q) {
    g_parent_trace.clear();
    algo.run(p, q);
    return g_parent_trace;
}

} // namespace

int main(int argc, char* argv[]) {
    // Default to 200 trials if no argument is provided, otherwise use the first argument as the number of trials
    long long num_trials = (argc > 1) ? std::atoll(argv[1]) : 200;

    std::vector<Algorithm> algorithms = {
        {"BBMSCore", bbms_core},
        {"BBMSInter", bbms_inter},
        {"BBMSDppInstant", bbms_dpp_instant},
        {"BBMSDppStepwise", bbms_dpp_stepwise},
    };

    long long failures = 0;
    for (long long trial = 0; trial < num_trials; ++trial) {
        // Generate two random curves with lengths in [2, 1000] and coordinates in [0, 100)
        auto [p, q] = make_random_curves(2, 500, (unsigned) trial);

        // Run the first algorithm to get the reference trace.
        std::vector<long long> reference_trace = traced_run(algorithms[0], p, q);

        // Compare the traces of the other algorithms against the reference trace
        for (size_t a = 1; a < algorithms.size(); ++a) {
            std::vector<long long> trace = traced_run(algorithms[a], p, q);

            // Check if the trace lengths are equal; if not, report a failure and continue to the next algorithm
            if (trace.size() != reference_trace.size()) {
                std::printf("FAIL  trial %lld  %s vs %s  trace length %zu != %zu\n",
                             trial, algorithms[a].name.c_str(), algorithms[0].name.c_str(),
                             trace.size(), reference_trace.size());
                ++failures;
                continue;
            }

            // Check if the traces are equal; if not, report a failure and break out of the loop to avoid redundant checks
            for (size_t cell = 0; cell < trace.size(); ++cell) {
                if (trace[cell] != reference_trace[cell]) {
                    std::printf("FAIL  trial %lld  %s vs %s  diverge at cell %zu: parent %lld != %lld\n",
                                 trial, algorithms[a].name.c_str(), algorithms[0].name.c_str(),
                                 cell, trace[cell], reference_trace[cell]);
                    ++failures;
                    break;
                }
            }
        }
    }

    // Print a summary of the test results and return an appropriate exit code
    std::printf("%lld trials x %zu algorithms, %lld failure(s)\n",
                 num_trials, algorithms.size(), failures);
    return failures == 0 ? 0 : 1;
}
