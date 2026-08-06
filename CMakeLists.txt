# CMakeList.txt : CMake project for DiscreteFrechetMatching, include source and define
# project specific logic here.
#
cmake_minimum_required (VERSION 3.10)

project ("DiscreteFrechetMatching")

include_directories(algorithms)
include_directories(algorithms/BBMS)
include_directories(algorithms/DP)

set(SOURCES 
    algorithms/BBMS/bbms_core.cpp
    algorithms/BBMS/bbms_dpp_instant.cpp
    algorithms/BBMS/bbms_dpp_stepwise.cpp
    algorithms/BBMS/bbms_dpp_stepwise_improved.cpp
    algorithms/BBMS/bbms_dpp_stepwise_lists.cpp
    algorithms/BBMS/bbms_inter.cpp
    algorithms/DP/dijkstra_prims.cpp
    algorithms/counters.cpp
    algorithms/parent_trace.cpp
    
)

set(HEADERS 
    algorithms/BBMS/bbms_core.h
    algorithms/BBMS/bbms_dpp_common.h
    algorithms/BBMS/bbms_dpp_instant.h
    algorithms/BBMS/bbms_dpp_stepwise.h
    algorithms/BBMS/bbms_dpp_common_improved.h
    algorithms/BBMS/bbms_dpp_stepwise_improved.h
    algorithms/BBMS/bbms_dpp_common_lists.h
    algorithms/BBMS/bbms_dpp_stepwise_lists.h
    algorithms/BBMS/bbms_inter.h
    algorithms/DP/dijkstra_prims.h
    algorithms/common.h
    algorithms/counters.h
    algorithms/parent_trace.h
)

# Add source to this project's executable.
add_executable (DFMExperiments "experiment/runner.cpp" ${SOURCES} ${HEADERS})
add_executable (DFMTestRun "algorithms/test_run.cpp" ${SOURCES} ${HEADERS})

set_property(TARGET DFMExperiments PROPERTY CXX_STANDARD 20)
set_property(TARGET DFMTestRun PROPERTY CXX_STANDARD 20)

