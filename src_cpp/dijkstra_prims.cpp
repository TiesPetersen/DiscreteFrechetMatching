#include "dijkstra_prims.h"
#include <queue>
#include <tuple>
#include <algorithm>
#include <cassert>
#include <unordered_map>

DPrimsResult dijkstra_prims(const Curve& p, const Curve& q) {
    int m = (int)p.size(), n = (int)q.size();
    assert(m > 0 && n > 0);

    // prev[i*n+j]: flat parent index; -1 = root sentinel; absent = undiscovered
    std::unordered_map<int, int> prev;

    using T = std::tuple<double, int, int>;
    std::priority_queue<T, std::vector<T>, std::greater<T>> pq;

    double d0 = dist(p[0], q[0]);
    pq.push({d0, 0, 0});
    prev[0] = -1;

    double frechet = d0;

    const int di[] = {1, 1, 0};
    const int dj[] = {0, 1, 1};

    while (!pq.empty()) {
        auto [cd, i, j] = pq.top(); pq.pop();
        frechet = std::max(frechet, cd);
        if (i == m-1 && j == n-1) break;

        for (int k = 0; k < 3; ++k) {
            int ni = i + di[k], nj = j + dj[k];
            if (ni >= m || nj >= n) continue;
            int idx = ni*n + nj;
            if (prev.count(idx)) continue;
            prev[idx] = i*n + j;
            pq.push({dist(p[ni], q[nj]), ni, nj});
        }
    }

    std::vector<std::pair<int,int>> matching;
    for (int cur = (m-1)*n + (n-1); cur != -1; cur = prev[cur])
        matching.push_back({cur / n, cur % n});
    std::reverse(matching.begin(), matching.end());

    return {matching, frechet};
}
