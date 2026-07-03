#pragma once
#include "common.h"

// Generate a pair of curves (c1, c2) both of length n, such that c1 is contained in a disk of radius r, and c2 is contained in a disk of radius r except for its last point which is at distance D from the origin.
// The random number generator is seeded with the given seed for reproducibility.
std::pair<Curve, Curve> generate_adversarial_pair(int n, double r, double D, unsigned seed);