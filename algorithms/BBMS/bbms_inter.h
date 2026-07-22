#pragma once
#include "common.h"


// BBMS-Inter algorithm for computing discrete Frechet distance and matching between two curves p and q.
// Assumes p and q have length >= 1.
MatchingAndFrechetDistance bbms_inter(const Curve& p, const Curve& q);
