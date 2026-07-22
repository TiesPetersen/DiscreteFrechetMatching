#pragma once
#include "common.h"
#include <vector>
#include <utility>

// Dijkstra/Prim's algorithm for computing discrete Frechet distance and matching between two curves p and q.
// Assumes p and q have length >= 1.
MatchingAndFrechetDistance dijkstra_prims(const Curve& p, const Curve& q);
