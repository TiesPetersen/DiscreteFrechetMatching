#pragma once
#include <vector>
#include <cmath>

struct MatchingAndFrechetDistance {
    std::vector<std::pair<int,int>> matching;
    double frechet_distance;
};

struct Point { double x, y; };

using Curve = std::vector<Point>;

inline double dist(const Point& a, const Point& b) {
    double dx = a.x - b.x, dy = a.y - b.y;
    return std::sqrt(dx*dx + dy*dy);
}
