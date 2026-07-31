#pragma once

#include <algorithm>

#ifdef COUNT_OPS

struct Counters {
    long long nca_regular_hops    = 0;  // BBMSCore, BBMSInter, BBMSDppInstant, BBMSDppStepwise
    long long nca_shortcut_hops   = 0;  // BBMSInter, BBMSDppInstant, BBMSDppStepwise (stays 0 for BBMSCore)
    long long shortcuts_written   = 0;  // BBMSInter, BBMSDppInstant, BBMSDppStepwise
    long long dead_paths_pruned   = 0;  // BBMSDppInstant, BBMSDppStepwise only -- how often dead-path pruning fires
    long long shortcuts_extended  = 0;  // BBMSDppInstant, BBMSDppStepwise only -- shortcuts redirected by a pruning event
    long long dead_path_walk_steps = 0; // BBMSDppInstant, BBMSDppStepwise -- cost of locating the dead path base per
                                         // event: always +1 for BBMSDppInstant (a single O(1) jump via an existing
                                         // shortcut), +1 per intermediate node for BBMSDppStepwise's O(depth) walk
    long long heap_pushes         = 0;  // DijkstraPrims
    long long heap_pops           = 0;  // DijkstraPrims
    long long max_heap_size       = 0;  // DijkstraPrims -- peak pq.size(), sampled after every push
    long long sum_heap_size       = 0;  // DijkstraPrims -- running sum of pq.size(), sampled once per pop;
                                         // divide by heap_pops for the average (see runner.cpp)
};

extern Counters g_counters;

#define COUNT(field) (++g_counters.field)
#define COUNT_MAX(field, value) (g_counters.field = std::max(g_counters.field, (long long)(value)))
#define COUNT_ADD(field, value) (g_counters.field += (value))

#else

#define COUNT(field) ((void) 0)
#define COUNT_MAX(field, value) ((void) 0)
#define COUNT_ADD(field, value) ((void) 0)

#endif
