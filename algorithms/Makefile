CXX      = g++
CXXFLAGS = -O2 -std=c++17 -Wall -Wextra -I.

SRCS         = BBMS/bbms_core.cpp BBMS/bbms_inter.cpp DP/dijkstra_prims.cpp counters.cpp
OBJS         = $(SRCS:.cpp=.o)
COUNTED_OBJS = $(SRCS:.cpp=_counted.o)

all: $(OBJS) $(COUNTED_OBJS)

%.o: %.cpp
	$(CXX) $(CXXFLAGS) -c -o $@ $<

%_counted.o: %.cpp
	$(CXX) $(CXXFLAGS) -DCOUNT_OPS -c -o $@ $<

clean:
	rm -f $(OBJS) $(COUNTED_OBJS)

.PHONY: all clean
