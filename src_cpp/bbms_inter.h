#pragma once
#include "common.h"
#include <vector>
#include <utility>

struct BBMSInterResult {
    std::vector<std::pair<int,int>> matching;
    double frechet_dist;
};

BBMSInterResult bbms_inter(const Curve& p, const Curve& q);
