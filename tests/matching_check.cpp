// Usage: ./matching_check.exe [num_trials]

#include "common.h"
#include "bbms_core.h"
#include "bbms_inter.h"
#include "bbms_dpp_instant.h"
#include "bbms_dpp_stepwise.h"
#include "utils.h"

#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <string>
#include <vector>

namespace {

struct Algorithm {
    std::string name;
    MatchingAndFrechetDistance (*run)(const Curve&, const Curve&);
};

} // namespace

int main(int argc, char* argv[]) {
    // Default to 500 trials if no argument is provided, otherwise use the first argument as the number of trials
    long long num_trials = (argc > 1) ? std::atoll(argv[1]) : 500;

    std::vector<Algorithm> algorithms = {
        {"BBMSCore", bbms_core},
        {"BBMSInter", bbms_inter},
        {"BBMSDppInstant", bbms_dpp_instant},
        {"BBMSDppStepwise", bbms_dpp_stepwise},
    };

    auto start_time = std::chrono::steady_clock::now();

    // Run the specified number of trials, generating random curves and comparing each algorithm's matching against the reference
    long long failures = 0;
    for (long long trial = 0; trial < num_trials; ++trial) {
        // Generate two random curves with lengths in [2, 500] and coordinates in [0, 100)
        auto [p, q] = make_random_curves(2, 500, (unsigned) trial);

        // Run the first algorithm to get the reference matching
        Matching reference_matching = algorithms[0].run(p, q).matching;

        // Compare the matchings of the other algorithms against the reference matching
        for (size_t a = 1; a < algorithms.size(); ++a) {
            Matching matching = algorithms[a].run(p, q).matching;

            // Check if the matching lengths are equal; if not, report a failure and continue to the next algorithm
            if (matching.size() != reference_matching.size()) {
                std::printf("FAIL  trial %lld  %s vs %s  matching length %zu != %zu\n",
                             trial, algorithms[a].name.c_str(), algorithms[0].name.c_str(),
                             matching.size(), reference_matching.size());
                ++failures;
                continue;
            }

            // Check if the matchings are equal; if not, report a failure and break out of the loop to avoid redundant checks
            for (size_t k = 0; k < matching.size(); ++k) {
                if (matching[k] != reference_matching[k]) {
                    std::printf("FAIL  trial %lld  %s vs %s  diverge at step %zu: (%lld,%lld) != (%lld,%lld)\n",
                                 trial, algorithms[a].name.c_str(), algorithms[0].name.c_str(), k,
                                 matching[k].first, matching[k].second,
                                 reference_matching[k].first, reference_matching[k].second);
                    ++failures;
                    break;
                }
            }
        }
    }

    double elapsed_s = std::chrono::duration<double>(std::chrono::steady_clock::now() - start_time).count();

    // Print a summary of the test results and return an appropriate exit code
    std::printf("%lld trials x %zu algorithms, %lld failure(s)  (%.2fs)\n",
                 num_trials, algorithms.size(), failures, elapsed_s);
    return failures == 0 ? 0 : 1;
}
