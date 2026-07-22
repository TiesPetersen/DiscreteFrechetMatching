CXX      = g++
CXXFLAGS = -O2 -std=c++17 -Wall -Wextra -I../algorithms -I../algorithms/BBMS -I../algorithms/DP

ALGO_DIR = ../algorithms
ALGO_OBJS = $(ALGO_DIR)/BBMS/bbms_core.o $(ALGO_DIR)/BBMS/bbms_inter.o \
            $(ALGO_DIR)/DP/dijkstra_prims.o $(ALGO_DIR)/counters.o
ALGO_COUNTED_OBJS = $(ALGO_DIR)/BBMS/bbms_core_counted.o $(ALGO_DIR)/BBMS/bbms_inter_counted.o \
                     $(ALGO_DIR)/DP/dijkstra_prims_counted.o $(ALGO_DIR)/counters_counted.o

all: runner.exe runner_counted.exe

# Build the algorithm objects by delegating to algorithms/Makefile.
$(ALGO_OBJS) $(ALGO_COUNTED_OBJS):
	$(MAKE) -C $(ALGO_DIR)

runner.exe: runner.cpp $(ALGO_OBJS)
	$(CXX) $(CXXFLAGS) -o $@ runner.cpp $(ALGO_OBJS)

runner_counted.exe: runner.cpp $(ALGO_COUNTED_OBJS)
	$(CXX) $(CXXFLAGS) -DCOUNT_OPS -o $@ runner.cpp $(ALGO_COUNTED_OBJS)

clean:
	rm -f runner.exe runner_counted.exe

.PHONY: all clean
