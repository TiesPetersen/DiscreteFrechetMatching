#include <iostream>
#include <string>
#include <chrono>
#include <new>
#include "common.h"
#include "generate_adversarial.h"
#include "dijkstra_prims.h"
#include "bbms_core.h"
#include "bbms_inter.h"
#include "bbms_dpp_instant.h"
#include "bbms_dpp_stepwise.h"

int main(int argc, char* argv[]) {
    if (argc != 4) {
        std::cerr << "usage: benchmark.exe <DijkstraPrims|BBMSCore|BBMSInter|BBMSDppInstant> <N> <sample>\n";
        return 1;
    }

    std::string algo  = argv[1];
    int         N      = std::stoi(argv[2]);
    int         sample = std::stoi(argv[3]);

    if (algo != "DijkstraPrims" && algo != "BBMSCore" && algo != "BBMSInter" &&
        algo != "BBMSDppInstant" && algo != "BBMSDppStepwise") {
        std::cerr << "unknown algorithm: " << algo << "\n";
        return 1;
    }

    // Same seed formula as Python experiment: seed = sample * 9999 + N
    unsigned seed = (unsigned)(sample * 9999 + N);
    auto [p, q] = generate_adversarial_pair(N, 1.0, 1000.0, seed);

    double runtime_s = -1.0, fd = -1.0;
    bool ok = false;

    try {
        auto t0 = std::chrono::high_resolution_clock::now();
        if (algo == "DijkstraPrims") {
            auto [match, frechet] = dijkstra_prims(p, q);
            fd = frechet;
        } else if (algo == "BBMSCore") {
            auto [match, frechet] = bbms_core(p, q);
            fd = frechet;
        } else if (algo == "BBMSInter") {
            auto [match, frechet] = bbms_inter(p, q);
            fd = frechet;
        } else if (algo == "BBMSDppInstant") {
            auto [match, frechet] = bbms_dpp_instant(p, q);
            fd = frechet;
        } else {
            auto [match, frechet] = bbms_dpp_stepwise(p, q);
            fd = frechet;
        }
        auto t1 = std::chrono::high_resolution_clock::now();
        runtime_s = std::chrono::duration<double>(t1 - t0).count();
        ok = true;
    } catch (const std::bad_alloc&) {
        // OOM — fall through with ok=false
    } catch (...) {
        // any other error
    }

    std::cout << algo << "," << N << "," << sample << ","
              << runtime_s << "," << fd << ","
              << (ok ? "True" : "False") << "\n";
    return 0;
}
