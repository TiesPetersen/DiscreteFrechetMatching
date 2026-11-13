CXX      = g++
CXXFLAGS = -O0 -g -std=c++17 -Wall -Wextra -I. -I../algorithms -I../algorithms/BBMS -I../algorithms/DP -MMD -MP

ALGO_DIR = ../algorithms

ALGO_OBJS = $(ALGO_DIR)/BBMS/bbms_core.o $(ALGO_DIR)/BBMS/bbms_inter.o \
            $(ALGO_DIR)/BBMS/bbms_dpp_instant.o $(ALGO_DIR)/BBMS/bbms_dpp_stepwise.o \
            $(ALGO_DIR)/DP/dijkstra_prims.o $(ALGO_DIR)/counters.o

# Always ask algorithms/ to rebuild what changed, so no stale objects get linked
algorithms:
	$(MAKE) -C $(ALGO_DIR)

$(ALGO_OBJS): algorithms ;

reference/dynamic_programming.o: reference/dynamic_programming.cpp reference/dynamic_programming.h
	$(CXX) $(CXXFLAGS) -c -o $@ reference/dynamic_programming.cpp

ORACLE_OBJS = $(ALGO_OBJS) reference/dynamic_programming.o

dynamic_programming_check.exe: dynamic_programming_check.cpp $(ORACLE_OBJS)
	$(CXX) $(CXXFLAGS) -o $@ dynamic_programming_check.cpp $(ORACLE_OBJS)

local_correctness_check.exe: local_correctness_check.cpp $(ALGO_OBJS)
	$(CXX) $(CXXFLAGS) -o $@ local_correctness_check.cpp $(ALGO_OBJS)

BBMS_OBJS = $(ALGO_DIR)/BBMS/bbms_core.o $(ALGO_DIR)/BBMS/bbms_inter.o $(ALGO_DIR)/counters.o \
            $(ALGO_DIR)/BBMS/bbms_dpp_instant.o $(ALGO_DIR)/BBMS/bbms_dpp_stepwise.o

matching_check.exe: matching_check.cpp $(BBMS_OBJS)
	$(CXX) $(CXXFLAGS) -o $@ matching_check.cpp $(BBMS_OBJS)

TRACED_OBJS = bbms_core_traced.o bbms_inter_traced.o bbms_dpp_instant_traced.o \
              bbms_dpp_stepwise_traced.o parent_trace_traced.o

bbms_core_traced.o: $(ALGO_DIR)/BBMS/bbms_core.cpp
	$(CXX) $(CXXFLAGS) -DTRACE_TEST -c -o $@ $<

bbms_inter_traced.o: $(ALGO_DIR)/BBMS/bbms_inter.cpp
	$(CXX) $(CXXFLAGS) -DTRACE_TEST -c -o $@ $<

bbms_dpp_instant_traced.o: $(ALGO_DIR)/BBMS/bbms_dpp_instant.cpp
	$(CXX) $(CXXFLAGS) -DTRACE_TEST -c -o $@ $<

bbms_dpp_stepwise_traced.o: $(ALGO_DIR)/BBMS/bbms_dpp_stepwise.cpp
	$(CXX) $(CXXFLAGS) -DTRACE_TEST -c -o $@ $<

parent_trace_traced.o: $(ALGO_DIR)/parent_trace.cpp
	$(CXX) $(CXXFLAGS) -DTRACE_TEST -c -o $@ $<

parent_trace_check.exe: parent_trace_check.cpp $(TRACED_OBJS)
	$(CXX) $(CXXFLAGS) -DTRACE_TEST -o $@ parent_trace_check.cpp $(TRACED_OBJS)

COUNTED_OBJS = $(ALGO_DIR)/BBMS/bbms_core_counted.o $(ALGO_DIR)/BBMS/bbms_inter_counted.o \
               $(ALGO_DIR)/BBMS/bbms_dpp_instant_counted.o $(ALGO_DIR)/BBMS/bbms_dpp_stepwise_counted.o \
               $(ALGO_DIR)/DP/dijkstra_prims_counted.o $(ALGO_DIR)/counters_counted.o

$(COUNTED_OBJS): algorithms ;

hand_counted_check.exe: hand_counted_check.cpp $(COUNTED_OBJS)
	$(CXX) $(CXXFLAGS) -DCOUNT_OPS -o $@ hand_counted_check.cpp $(COUNTED_OBJS)

# Lean layout check: current and lean DPP variants, built with parent tracing, op counting and the
# lean checking build (which stops on any use of a freed shortcut)
LEAN_SRCS = $(ALGO_DIR)/BBMS/bbms_dpp_instant.cpp $(ALGO_DIR)/BBMS/bbms_dpp_stepwise.cpp \
            $(ALGO_DIR)/BBMS/bbms_dpp_instant_lean.cpp $(ALGO_DIR)/BBMS/bbms_dpp_stepwise_lean.cpp \
            $(ALGO_DIR)/counters.cpp $(ALGO_DIR)/parent_trace.cpp

# The sources are compiled straight into the test, so list their shared headers explicitly
LEAN_HEADERS = $(ALGO_DIR)/BBMS/bbms_dpp_common.h $(ALGO_DIR)/BBMS/bbms_dpp_lean_common.h $(ALGO_DIR)/common.h

lean_equivalence_check.exe: lean_equivalence_check.cpp $(LEAN_SRCS) $(LEAN_HEADERS)
	$(CXX) $(CXXFLAGS) -DTRACE_TEST -DCOUNT_OPS -DLEAN_CHECKS -o $@ lean_equivalence_check.cpp $(LEAN_SRCS)

all: dynamic_programming_check.exe matching_check.exe parent_trace_check.exe hand_counted_check.exe local_correctness_check.exe lean_equivalence_check.exe

clean:
	rm -f *.o *.d reference/*.o reference/*.d *.exe
	rm -rf *.exe.dSYM

.PHONY: all clean algorithms

# Rebuild objects when a header they include changes
-include $(wildcard *.d reference/*.d)
