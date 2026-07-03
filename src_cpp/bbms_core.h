#pragma once
#include "common.h"


// BBMS-Core algorithm for computing the discrete Frechet distance and matching between two curves p and q.
// Assumes p and q have length >= 1.
MatchingAndFrechetDistance bbms_core(const Curve& p, const Curve& q);
