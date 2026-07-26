#include "dynamic_programming.h"
#include <algorithm>

// Textbook discrete Frechet distance using dynamic programming:
// dp[i][j] is the smallest possible max-distance over any valid staircase path from (0,0) to (i,j).
MatchingAndFrechetDistance dynamic_programming(const Curve& p, const Curve& q) {
    long long m = (long long) p.size(), n = (long long) q.size();

    // Initialize the DP table with -INF to indicate uncomputed states
    std::vector<std::vector<double>> dp(m, std::vector<double>(n, -INF));

    // Base case: the distance from (0,0) to (0,0) is simply the distance between p[0] and q[0]
    dp[0][0] = dist(p[0], q[0]);

    // Fill the first row and first column of the DP table
    for (long long i = 1; i < m; ++i) dp[i][0] = std::max(dp[i - 1][0], dist(p[i], q[0]));
    for (long long j = 1; j < n; ++j) dp[0][j] = std::max(dp[0][j - 1], dist(p[0], q[j]));

    // Fill the rest of the DP table using the recurrence relation
    for (long long i = 1; i < m; ++i) {
        for (long long j = 1; j < n; ++j) {
            double best_prev = std::min({dp[i - 1][j], dp[i - 1][j - 1], dp[i][j - 1]});
            dp[i][j] = std::max(best_prev, dist(p[i], q[j]));
        }
    }

    // Backtrack from (m-1, n-1) to (0,0), preferring diagonal, then up, then left on ties
    Matching matching;
    long long i = m - 1, j = n - 1;
    matching.push_back({i, j});
    while (i != 0 || j != 0) {
        double diag = (i > 0 && j > 0) ? dp[i - 1][j - 1] : INF;
        double up   = (i > 0) ? dp[i - 1][j] : INF;
        double left = (j > 0) ? dp[i][j - 1] : INF;

        if (diag <= up && diag <= left) { --i; --j; }
        else if (up <= left) { --i; }
        else { --j; }

        matching.push_back({i, j});
    }

    // Reverse the matching to get it from (0,0) to (m-1,n-1)
    std::reverse(matching.begin(), matching.end());

    return {matching, dp[m - 1][n - 1]};
}
