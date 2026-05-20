#pragma once
#include "common.h"

// Standard O(nm) discrete Fréchet DP — correctness oracle only, not benchmarked.
double dp_frechet(const Curve& p, const Curve& q);
