#pragma once
#include "common.h"


// BBMS-DPP-Stepwise algorithm with the lean memory layout (linked incoming lists), for computing discrete Frechet distance and matching between two curves p and q.
// Assumes p and q have length >= 1.
MatchingAndFrechetDistance bbms_dpp_stepwise_lean(const Curve& p, const Curve& q);