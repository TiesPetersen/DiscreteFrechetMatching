#pragma once
#include "common.h"
#include <vector>
#include <utility>

struct BBMSDppInstantResult {
    std::vector<std::pair<int,int>> matching;
    double frechet_dist;
};

BBMSDppInstantResult bbms_dpp_instant(const Curve& p, const Curve& q);
