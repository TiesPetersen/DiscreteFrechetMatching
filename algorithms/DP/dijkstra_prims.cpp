#include "dijkstra_prims.h"
#include <queue>
#include <tuple>
#include <algorithm>
#include <cassert>
#include <unordered_map>

MatchingAndFrechetDistance dijkstra_prims(const Curve& p, const Curve& q) {
    long long m = (long long) p.size(), n = (long long) q.size();
    const long long di[] = {1, 1, 0};
    const long long dj[] = {0, 1, 1};

    // Initialize prev map
    std::unordered_map<long long, long long> prev;

    // Min-heap priority queue
    using T = std::tuple<double, int, int>;
    std::priority_queue<T, std::vector<T>, std::greater<T>> pq;

    // Start from the first cell (0, 0)
    double initial_distance = dist(p[0], q[0]);
    pq.push({initial_distance, 0, 0});
    prev[0] = -1;
    double frechet = initial_distance;

    while (!pq.empty()) {
        // Get the cell with the smallest distance from the priority queue
        auto [current_distance, i, j] = pq.top(); pq.pop();
        frechet = std::max(frechet, current_distance);

        // If we reached the last cell, we can stop
        if (i == m-1 && j == n-1) break;

        // Explore the neighbors (up, diagonal, right)
        for (int k = 0; k < 3; ++k) {
            // Calculate the neighbor's indices
            long long ni = i + di[k], nj = j + dj[k];

            // Check if the neighbor is within bounds
            if (ni >= m || nj >= n) continue;

            // Calculate the index of the neighbor
            long long idx = (long long) ni * n + nj;

            // Check if we have already visited this cell
            if (prev.count(idx)) continue;

            // Add the neighbor to the priority queue
            prev[idx] = (long long) i * n + j;
            pq.push({dist(p[ni], q[nj]), ni, nj});
        }
    }

    // Extract the matching from the prev map
    Matching matching;
    for (long long cur = (long long)(m - 1) * n + (n - 1); cur != -1; cur = prev[cur]) {
        matching.push_back({cur / n, cur % n});
    }
    // Reverse the matching to get it in the correct order
    std::reverse(matching.begin(), matching.end());

    return {matching, frechet};
}
