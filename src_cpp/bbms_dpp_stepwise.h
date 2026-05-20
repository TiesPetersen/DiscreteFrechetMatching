#pragma once
#include "common.h"
#include <vector>
#include <utility>

struct BBMSDppStepwiseResult {
    std::vector<std::pair<int,int>> matching;
    double frechet_dist;
};

BBMSDppStepwiseResult bbms_dpp_stepwise(const Curve& p, const Curve& q);
