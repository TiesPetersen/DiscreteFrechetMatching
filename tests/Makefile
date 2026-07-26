CXX      = g++
CXXFLAGS = -O0 -g -std=c++17 -Wall -Wextra -I. -I../algorithms -I../algorithms/BBMS -I../algorithms/DP

ALGO_DIR = ../algorithms

ALGO_OBJS = $(ALGO_DIR)/BBMS/bbms_core.o $(ALGO_DIR)/BBMS/bbms_inter.o \
            $(ALGO_DIR)/BBMS/bbms_dpp_instant.o $(ALGO_DIR)/BBMS/bbms_dpp_stepwise.o \
            $(ALGO_DIR)/DP/dijkstra_prims.o $(ALGO_DIR)/counters.o

$(ALGO_OBJS):
	$(MAKE) -C $(ALGO_DIR)

reference/dynamic_programming.o: reference/dynamic_programming.cpp reference/dynamic_programming.h
	$(CXX) $(CXXFLAGS) -c -o $@ reference/dynamic_programming.cpp

ORACLE_OBJS = $(ALGO_OBJS) reference/dynamic_programming.o

dynamic_programming_check.exe: dynamic_programming_check.cpp $(ORACLE_OBJS)
	$(CXX) $(CXXFLAGS) -o $@ dynamic_programming_check.cpp $(ORACLE_OBJS)

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

all: dynamic_programming_check.exe matching_check.exe parent_trace_check.exe

clean:
	rm -f *.o reference/*.o *.exe
	rm -rf *.exe.dSYM

.PHONY: all clean
