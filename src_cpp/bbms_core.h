#pragma once
#include "common.h"
#include <vector>
#include <utility>

struct BBMSCoreResult {
    std::vector<std::pair<int,int>> matching;
    double frechet_dist;
};

BBMSCoreResult bbms_core(const Curve& p, const Curve& q);
