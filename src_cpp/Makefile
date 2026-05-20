CXX      = g++
CXXFLAGS = -O2 -std=c++17 -Wall -Wextra

COMMON_SRCS = dp_check.cpp dijkstra_prims.cpp bbms_core.cpp bbms_inter.cpp bbms_dpp_instant.cpp bbms_dpp_stepwise.cpp generate_adversarial.cpp
COMMON_OBJS = $(patsubst %.cpp,%.o,$(COMMON_SRCS))

all: verify.exe benchmark.exe

verify.exe: $(COMMON_OBJS) verify.o
	$(CXX) $(CXXFLAGS) -o $@ $^

benchmark.exe: $(COMMON_OBJS) benchmark.o
	$(CXX) $(CXXFLAGS) -o $@ $^

%.o: %.cpp
	$(CXX) $(CXXFLAGS) -c -o $@ $<

run: verify.exe
	./verify.exe

clean:
	-rm -f $(COMMON_OBJS) verify.o benchmark.o verify.exe benchmark.exe

.PHONY: all run clean
