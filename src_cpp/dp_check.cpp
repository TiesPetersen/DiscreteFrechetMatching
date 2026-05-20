#include "dp_check.h"
#include <algorithm>
#include <cassert>

double dp_frechet(const Curve& p, const Curve& q) {
    int m = (int)p.size(), n = (int)q.size();
    assert(m > 0 && n > 0);

    std::vector<double> dp(m * n);

    dp[0] = dist(p[0], q[0]);

    for (int i = 1; i < m; ++i)
        dp[i*n] = std::max(dp[(i-1)*n], dist(p[i], q[0]));

    for (int j = 1; j < n; ++j)
        dp[j] = std::max(dp[j-1], dist(p[0], q[j]));

    for (int i = 1; i < m; ++i)
        for (int j = 1; j < n; ++j)
            dp[i*n+j] = std::max(
                std::min({dp[(i-1)*n+j], dp[i*n+(j-1)], dp[(i-1)*n+(j-1)]}),
                dist(p[i], q[j])
            );

    return dp[(m-1)*n + (n-1)];
}
