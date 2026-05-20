#pragma once
#include "common.h"
#include <utility>

// Replicates Python's generate_outlier_end_pair(n, n, r, D, seed):
//   curve1: n points uniformly sampled in disk of radius r centred at origin
//   curve2: n-1 points in the same disk, then a final point at (D, 0)
// Both curves are drawn from a single RNG seeded with `seed`.
std::pair<Curve, Curve> generate_adversarial_pair(int n, double r, double D, unsigned seed);
