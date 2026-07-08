CXX      = g++
CXXFLAGS = -O2 -std=c++17 -Wall -Wextra

COMMON_SRCS = dp_check.cpp dijkstra_prims.cpp bbms_core.cpp bbms_inter.cpp bbms_dpp_instant.cpp bbms_dpp_stepwise.cpp generate_adversarial.cpp
COMMON_OBJS = $(patsubst %.cpp,%.o,$(COMMON_SRCS))

all: verify.exe benchmark.exe

verify.exe: $(COMMON_OBJS) verify.o
	$(CXX) $(CXXFLAGS) -o $@ $^

benchmark.exe: $(COMMON_OBJS) benchmark.o
	$(CXX) $(CXXFLAGS) -o $@ $^

# Kept separate from COMMON_OBJS: only needs bbms_inter, not the other
# algorithms (some of which are still mid-refactor and don't build).
memory_usage.exe: generate_adversarial.o bbms_inter.o memory_usage.o
	$(CXX) $(CXXFLAGS) -o $@ $^

# Kept separate from COMMON_OBJS: doesn't need the dpp variants, which are
# still mid-refactor and don't build.
loglog_scaling.exe: generate_adversarial.o dijkstra_prims.o bbms_core.o bbms_inter.o loglog_scaling.o
	$(CXX) $(CXXFLAGS) -o $@ $^

%.o: %.cpp
	$(CXX) $(CXXFLAGS) -c -o $@ $<

run: verify.exe
	./verify.exe

clean:
	-rm -f $(COMMON_OBJS) verify.o benchmark.o verify.exe benchmark.exe memory_usage.o memory_usage.exe loglog_scaling.o loglog_scaling.exe

.PHONY: all run clean
