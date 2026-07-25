#pragma once


#ifdef COUNT_OPS

struct Counters {
    long long nca_regular_hops  = 0;  // BBMSCore, BBMSInter
    long long nca_shortcut_hops = 0;  // BBMSInter only (stays 0 for BBMSCore)
    long long shortcuts_written = 0;  // BBMSInter only
    long long heap_pushes       = 0;  // DijkstraPrims
    long long heap_pops         = 0;  // DijkstraPrims
};

extern Counters g_counters;

#define COUNT(field) (++g_counters.field)

#else

#define COUNT(field) ((void) 0)

#endif
