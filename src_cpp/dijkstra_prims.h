#pragma once
#include "common.h"
#include <vector>
#include <utility>

struct DPrimsResult {
    std::vector<std::pair<int,int>> matching;
    double frechet_dist;
};

DPrimsResult dijkstra_prims(const Curve& p, const Curve& q);
