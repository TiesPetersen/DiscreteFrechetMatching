// Usage: ./hand_counted_check.exe [cases_dir]

#include "common.h"
#include "bbms_core.h"
#include "bbms_inter.h"
#include "bbms_dpp_instant.h"
#include "bbms_dpp_stepwise.h"
#include "dijkstra_prims.h"
#include "counters.h"

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <map>
#include <sstream>
#include <string>
#include <vector>

namespace fs = std::filesystem;

namespace {

constexpr double EPS = 1e-9;

struct TestCase {
    std::string name;
    std::string algorithm;
    Curve p, q;
    std::map<std::string, long long> expected_counts;
    bool has_expected_distance = false;
    double expected_distance = 0.0;
};

// Parses one case file. See tests/hand_counted/case_01_bbms_core_2x2.txt for the format.
TestCase parse_case(const fs::path& path) {
    TestCase tc;
    tc.name = path.filename().string();

    std::ifstream in(path);
    std::string line;
    while (std::getline(in, line)) {
        std::istringstream iss(line);
        std::string keyword;
        iss >> keyword;
        if (keyword.empty() || keyword[0] == '#') continue;

        if (keyword == "algorithm") {
            iss >> tc.algorithm;
        } else if (keyword == "p" || keyword == "q") {
            int count;
            iss >> count;
            Curve curve(count);
            for (auto& point : curve) in >> point.x >> point.y;
            (keyword == "p" ? tc.p : tc.q) = curve;
        } else if (keyword == "expect") {
            std::string field;
            iss >> field;
            if (field == "frechet_distance") {
                iss >> tc.expected_distance;
                tc.has_expected_distance = true;
            } else {
                long long value;
                iss >> value;
                tc.expected_counts[field] = value;
            }
        }
    }
    return tc;
}

MatchingAndFrechetDistance run_algorithm(const std::string& algorithm, const Curve& p, const Curve& q) {
    if (algorithm == "BBMSCore")        return bbms_core(p, q);
    if (algorithm == "BBMSInter")       return bbms_inter(p, q);
    if (algorithm == "BBMSDppInstant")  return bbms_dpp_instant(p, q);
    if (algorithm == "BBMSDppStepwise") return bbms_dpp_stepwise(p, q);
    if (algorithm == "DijkstraPrims")   return dijkstra_prims(p, q);
    std::fprintf(stderr, "unknown algorithm: %s\n", algorithm.c_str());
    std::exit(1);
}

// Looks up one field of g_counters by name -- C++ has no runtime reflection, so this
// is just a manual mapping from the field names used in case files.
long long counter_value(const std::string& field) {
    if (field == "nca_regular_hops")     return g_counters.nca_regular_hops;
    if (field == "nca_shortcut_hops")    return g_counters.nca_shortcut_hops;
    if (field == "shortcuts_written")    return g_counters.shortcuts_written;
    if (field == "dead_paths_pruned")    return g_counters.dead_paths_pruned;
    if (field == "shortcuts_extended")   return g_counters.shortcuts_extended;
    if (field == "dead_path_walk_steps") return g_counters.dead_path_walk_steps;
    if (field == "heap_pushes")          return g_counters.heap_pushes;
    if (field == "heap_pops")            return g_counters.heap_pops;
    std::fprintf(stderr, "unknown counter field: %s\n", field.c_str());
    std::exit(1);
}

bool check_case(const TestCase& tc) {
    g_counters = Counters{};
    MatchingAndFrechetDistance result = run_algorithm(tc.algorithm, tc.p, tc.q);

    bool ok = true;

    if (tc.has_expected_distance && std::fabs(result.frechet_distance - tc.expected_distance) > EPS) {
        std::printf("FAIL  %-30s  %-16s  frechet_distance %.9f != expected %.9f\n",
                     tc.name.c_str(), tc.algorithm.c_str(), result.frechet_distance, tc.expected_distance);
        ok = false;
    }

    for (const auto& [field, expected] : tc.expected_counts) {
        long long actual = counter_value(field);
        if (actual != expected) {
            std::printf("FAIL  %-30s  %-16s  %s = %lld != expected %lld\n",
                         tc.name.c_str(), tc.algorithm.c_str(), field.c_str(), actual, expected);
            ok = false;
        }
    }

    return ok;
}

} // namespace

int main(int argc, char* argv[]) {
    fs::path cases_dir = (argc > 1) ? argv[1] : "hand_counted";

    std::vector<fs::path> case_files;
    for (const auto& entry : fs::directory_iterator(cases_dir)) {
        if (entry.path().extension() == ".txt") case_files.push_back(entry.path());
    }
    std::sort(case_files.begin(), case_files.end());

    long long passed = 0, failed = 0;
    for (const auto& path : case_files) {
        TestCase tc = parse_case(path);
        if (check_case(tc)) {
            std::printf("PASS  %-30s  %s\n", tc.name.c_str(), tc.algorithm.c_str());
            ++passed;
        } else {
            ++failed;
        }
    }

    std::printf("%zu case(s), %lld passed, %lld failed\n", case_files.size(), passed, failed);
    return failed == 0 ? 0 : 1;
}
