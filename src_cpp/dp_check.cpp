#include "dp_check.h"


double dp_frechet(const Curve& p, const Curve& q) {
    long long m = (long long)p.size(), n = (long long)q.size();

    std::vector<double> dp((size_t) m * n);

    // Base case: (0, 0)
    dp[0] = dist(p[0], q[0]);

    // First column: p[i] can only match q[0]
    for (long long i = 1; i < m; ++i)
        dp[i * n] = std::max(dp[(i - 1) * n], dist(p[i], q[0]));

    // First row: q[j] can only match p[0]
    for (long long j = 1; j < n; ++j)
        dp[j] = std::max(dp[j - 1], dist(p[0], q[j]));

    // Interior cells: take the best of the three predecessors (left, diagonal, below) and the current distance
    for (long long i = 1; i < m; ++i)
        for (long long j = 1; j < n; ++j)
            dp[i * n + j] = std::max(
                std::min({dp[(i - 1) * n + j], dp[i * n + (j - 1)], dp[(i - 1) * n + (j - 1)]}),
                dist(p[i], q[j])
            );

    return dp[(m - 1) * n + (n - 1)];
}
