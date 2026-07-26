#pragma once
#include "common.h"
#include <random>
#include <utility>

// Generate a pair of random curves, each with an independently random length in [min_length, max_length], and coordinates in [0, scale). 
// Deterministic given the same seed.
inline std::pair<Curve, Curve> make_random_curves(long long min_length, long long max_length, unsigned seed, double scale = 100.0) {
    std::mt19937 rng(seed);
    std::uniform_int_distribution<long long> length(min_length, max_length);
    std::uniform_real_distribution<double> coord(0.0, scale);

    Curve p(length(rng)), q(length(rng));
    for (auto& point : p) { point.x = coord(rng); point.y = coord(rng); }
    for (auto& point : q) { point.x = coord(rng); point.y = coord(rng); }
    return {p, q};
}
