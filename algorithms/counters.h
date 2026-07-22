#pragma once

// Operation counters for the main experiment. Only compiled in when COUNT_OPS is
// defined, so the normal (timing/memory) build contains none of this code at all —
// not just disabled, genuinely absent, so it cannot affect those measurements.
//
// Each algorithm only fills in the fields relevant to it (see PLAN.md and
// PSEUDOCODE.md for which fields belong to which algorithm).

#ifdef COUNT_OPS

struct Counters {
    long long nca_regular_hops  = 0;  // BBMSCore, BBMSInter
    long long nca_shortcut_hops = 0;  // BBMSInter only (stays 0 for BBMSCore)
    long long shortcuts_written = 0;  // BBMSInter only
    long long heap_pushes       = 0;  // DijkstraPrims
    long long heap_pops         = 0;  // DijkstraPrims
};

// The one real definition lives in counters.cpp, so linking multiple algorithm
// files into the same runner binary doesn't produce duplicate-symbol errors.
extern Counters g_counters;

#define COUNT(field) (++g_counters.field)

#else

#define COUNT(field) ((void)0)

#endif
