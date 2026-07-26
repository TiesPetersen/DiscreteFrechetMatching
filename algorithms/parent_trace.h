#pragma once


#ifdef TRACE_TEST
#include <vector>

extern std::vector<long long> g_parent_trace;
#define TRACE_PARENT(parent) (g_parent_trace.push_back(parent))
#else
#define TRACE_PARENT(parent) ((void) 0)
#endif
