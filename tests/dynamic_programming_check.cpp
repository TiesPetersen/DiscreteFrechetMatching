// Usage: ./dynamic_programming_check.exe [num_trials]

#include "common.h"
#include "bbms_core.h"
#include "bbms_inter.h"
#include "bbms_dpp_instant.h"
#include "bbms_dpp_stepwise.h"
#include "dijkstra_prims.h"
#include "reference/dynamic_programming.h"
#include "utils.h"

#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <string>
#include <vector>

namespace {

constexpr double EPS = 1e-9;

// Check if the given matching is a valid staircase path from (0,0) to (m-1,n-1) and if its maximum distance matches the claimed distance.
bool matching_is_valid(const Matching& matching, const Curve& p, const Curve& q, double claimed_distance) {
    long long m = (long long) p.size(), n = (long long) q.size();

    // Check if the matching is empty; if so, it's invalid
    if (matching.empty()) return false;

    // Check if the first and last points of the matching are correct; if not, it's invalid
    if (matching.front() != std::make_pair(0LL, 0LL)) return false;
    if (matching.back() != std::make_pair(m - 1, n - 1)) return false;

    // Check if the matching is a valid staircase path and compute the maximum distance along the way
    double max_distance = -INF;
    for (size_t k = 0; k < matching.size(); ++k) {
        auto [i, j] = matching[k];

        // Check if the current point is within bounds; if not, it's invalid
        if (i < 0 || i >= m || j < 0 || j >= n) return false;

        // Update the maximum distance encountered so far
        max_distance = std::max(max_distance, dist(p[i], q[j]));

        // Check if the current point is a valid step from the previous point; if not, it's invalid
        if (k > 0) {
            auto [prev_i, prev_j] = matching[k - 1];
            long long di = i - prev_i, dj = j - prev_j;
            if (di < 0 || dj < 0 || di > 1 || dj > 1 || (di == 0 && dj == 0)) return false;
        }
    }

    return std::fabs(max_distance - claimed_distance) < EPS;
}

struct Algorithm {
    std::string name;
    MatchingAndFrechetDistance (*run)(const Curve&, const Curve&);
};

// Check one algorithm on one pair of curves against the reference distance and matching.
bool check_one(const Algorithm& algo, const Curve& p, const Curve& q, double reference_distance, long long trial) {
    MatchingAndFrechetDistance result = algo.run(p, q);

    // Check if the computed Frechet distance matches the reference distance within a small epsilon; if not, report failure
    if (std::fabs(result.frechet_distance - reference_distance) > EPS) {
        std::printf("FAIL  trial %lld  %-16s  distance %.9f != reference %.9f\n",
                     trial, algo.name.c_str(), result.frechet_distance, reference_distance);
        return false;
    }

    // Check if the computed matching is valid and its maximum distance matches the computed Frechet distance; if not, report failure
    if (!matching_is_valid(result.matching, p, q, result.frechet_distance)) {
        std::printf("FAIL  trial %lld  %-16s  matching is not a valid staircase path, "
                     "or its max distance disagrees with frechet_distance\n",
                     trial, algo.name.c_str());
        return false;
    }

    return true;
}

} // namespace

int main(int argc, char* argv[]) {
    // Default to 500 trials if no argument is provided, otherwise use the first argument as the number of trials
    long long num_trials = (argc > 1) ? std::atoll(argv[1]) : 500;

    std::vector<Algorithm> algorithms = {
        {"BBMSCore", bbms_core},
        {"BBMSInter", bbms_inter},
        {"BBMSDppInstant", bbms_dpp_instant},
        {"BBMSDppStepwise", bbms_dpp_stepwise},
        {"DijkstraPrims", dijkstra_prims},
    };

    // Run the specified number of trials, generating random curves and checking each algorithm against the reference implementation
    long long failures = 0;
    for (long long trial = 0; trial < num_trials; ++trial) {
        // Generate two random curves with lengths in [2, 500] and coordinates in [0, 100)
        auto [p, q] = make_random_curves(2, 500, (unsigned) trial);

        // Compute the reference Frechet distance using the naive dynamic programming implementation
        double reference_distance = dynamic_programming(p, q).frechet_distance;

        // Check each algorithm against the reference distance and matching; if any check fails, increment the failure count
        for (const Algorithm& algo : algorithms) {
            if (!check_one(algo, p, q, reference_distance, trial)) ++failures;
        }
    }

    // Print a summary of the test results and return an appropriate exit code
    std::printf("%lld trials x %zu algorithms, %lld failure(s)\n",
                 num_trials, algorithms.size(), failures);
    return failures == 0 ? 0 : 1;
}
