#pragma once
#include <vector>
#include <cmath>
#include <algorithm>
#include <limits>


constexpr double INF = std::numeric_limits<double>::infinity();


using Matching = std::vector<std::pair<long long, long long>>;


struct MatchingAndFrechetDistance {
    Matching matching;
    double frechet_distance;
};


struct Point { double x, y; };


using Curve = std::vector<Point>;


// Compute squared Euclidean distance between two points
inline double dist(const Point& a, const Point& b) {
    double dx = a.x - b.x, dy = a.y - b.y;
    return dx * dx + dy * dy;
}


// Extract the matching and maximum distance from the graph G.
// Node must have a `parent` (long long) and `distance` (double) field.
template <typename Node>
MatchingAndFrechetDistance extract_matching(const std::vector<Node>& G, long long m, long long n) {
    Matching matching;
    double max_distance = -INF;

    // Trace path from (m-1, n-1) to root
    for (long long cur = (m - 1) * n + (n - 1); cur != -1; cur = G[cur].parent) {
        matching.push_back({cur / n, cur % n});
        max_distance = std::max(max_distance, G[cur].distance);
    }

    // Reverse to get matching in order from (0,0) to (m-1,n-1)
    std::reverse(matching.begin(), matching.end());

    return {matching, max_distance};
}