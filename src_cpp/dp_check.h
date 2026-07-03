#pragma once
#include "common.h"

// Standard O(nm) discrete Frechet distance between two curves p and q, via dynamic programming.
// Assumes p and q have length >= 1. Note: only computes the distance, not the matching.
double dp_frechet(const Curve& p, const Curve& q);
