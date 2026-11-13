// Usage: ./local_correctness_check.exe [num_trials]
//
// Checks that every algorithm returns a locally correct matching: for every two matched
// cells a before b, the largest distance on the matching from a to b equals the discrete
// Frechet distance of the two subcurves between them. Uses small integer coordinates, so
// there are many exact ties. With ties, DijkstraPrims and BBMS may return different
// matchings; both must still be locally correct.

#include "common.h"
#include "bbms_core.h"
#include "bbms_inter.h"
#include "bbms_dpp_instant.h"
#include "bbms_dpp_stepwise.h"
#include "dijkstra_prims.h"
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

// Discrete Frechet distance from cell (i0, j0) to every cell above and to the right of it
std::vector<double> frechet_from(const Curve& p, const Curve& q, long long i0, long long j0) {
    long long rows = (long long) p.size() - i0, cols = (long long) q.size() - j0;
    std::vector<double> dp(rows * cols, INF);
    for (long long i = 0; i < rows; ++i) {
        for (long long j = 0; j < cols; ++j) {
            double best = (i == 0 && j == 0) ? -INF : INF;
            if (i > 0) best = std::min(best, dp[(i - 1) * cols + j]);
            if (j > 0) best = std::min(best, dp[i * cols + j - 1]);
            if (i > 0 && j > 0) best = std::min(best, dp[(i - 1) * cols + j - 1]);
            dp[i * cols + j] = std::max(best, dist(p[i0 + i], q[j0 + j]));
        }
    }
    return dp;
}

// True if every part of the matching is a Frechet matching of its subcurves
bool is_locally_correct(const Matching& matching, const Curve& p, const Curve& q) {
    for (size_t a = 0; a < matching.size(); ++a) {
        auto [i0, j0] = matching[a];
        long long cols = (long long) q.size() - j0;
        std::vector<double> dp = frechet_from(p, q, i0, j0);

        // Walk the matching from a onwards, keeping the largest distance seen
        double largest = -INF;
        for (size_t b = a; b < matching.size(); ++b) {
            auto [i, j] = matching[b];
            largest = std::max(largest, dist(p[i], q[j]));
            if (largest > dp[(i - i0) * cols + (j - j0)] + 1e-9) return false;
        }
    }
    return true;
}

// Rounds every coordinate down to an integer, which creates many equal distances
void make_ties(Curve& curve) {
    for (auto& point : curve) { point.x = (int) point.x; point.y = (int) point.y; }
}

} // namespace

int main(int argc, char* argv[]) {
    // Default to 300 trials if no argument is provided
    long long num_trials = (argc > 1) ? std::atoll(argv[1]) : 300;

    std::vector<Algorithm> algorithms = {
        {"BBMSCore", bbms_core},
        {"BBMSInter", bbms_inter},
        {"BBMSDppInstant", bbms_dpp_instant},
        {"BBMSDppStepwise", bbms_dpp_stepwise},
        {"DijkstraPrims", dijkstra_prims},
    };

    auto start_time = std::chrono::steady_clock::now();

    // Check every algorithm's matching on random tie-heavy curves
    long long failures = 0;
    for (long long trial = 0; trial < num_trials; ++trial) {
        auto [p, q] = make_random_curves(2, 60, (unsigned) trial, 4.0);
        make_ties(p);
        make_ties(q);

        for (const Algorithm& algo : algorithms) {
            MatchingAndFrechetDistance result = algo.run(p, q);
            if (!is_locally_correct(result.matching, p, q)) {
                std::printf("FAIL  trial %lld  %s  matching is not locally correct (m=%zu, n=%zu)\n",
                            trial, algo.name.c_str(), p.size(), q.size());
                ++failures;
            }
        }
    }

    // Print a summary
    double seconds = std::chrono::duration<double>(std::chrono::steady_clock::now() - start_time).count();
    std::printf("%lld trials x %zu algorithms, %lld failure(s)  (%.2fs)\n",
                num_trials, algorithms.size(), failures, seconds);
    return failures == 0 ? 0 : 1;
}
