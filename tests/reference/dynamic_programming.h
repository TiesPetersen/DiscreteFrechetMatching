#pragma once
#include "common.h"

// Naive O(mn) reference implementation of the discrete Frechet distance and matching, using dynamic programming.
// Used for testing and validation of other implementations.
// Note: This does not compute the locally correct / retractable matching, only a valid matching that achieves the discrete Frechet distance.
MatchingAndFrechetDistance dynamic_programming(const Curve& p, const Curve& q);
