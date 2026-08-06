#include "bbms_dpp_stepwise.h"
#include "bbms_dpp_stepwise_improved.h"
#include "bbms_dpp_stepwise_lists.h"
#include "dijkstra_prims.h"

#include <iostream>
#include <string>
#include <fstream>
#include <chrono>

static void load_sample(const std::string& path, int sample_index, Curve& p, Curve& q) {
    std::ifstream in(path);
    if (!in) {
        std::cerr << "cannot open dataset file: " << path << "\n";
        std::exit(1);
    }

    int sample_count;
    in >> sample_count;
    if (sample_index < 0 || sample_index >= sample_count) {
        std::cerr << "sample index " << sample_index << " out of range (file has "
            << sample_count << " samples)\n";
        std::exit(1);
    }

    for (int s = 0; s <= sample_index; ++s) {
        int m;
        in >> m;
        p.resize(m);
        for (int i = 0; i < m; ++i) in >> p[i].x >> p[i].y;

        int n;
        in >> n;
        q.resize(n);
        for (int i = 0; i < n; ++i) in >> q[i].x >> q[i].y;
    }
}

void run(const Curve& p, const Curve& q, int its, MatchingAndFrechetDistance(*alg)(const Curve&, const Curve&)) {
    MatchingAndFrechetDistance res;

    auto t0 = std::chrono::steady_clock::now();
    while (its > 0) {
        res = alg(p, q);
        --its;
    }
    auto t1 = std::chrono::steady_clock::now();
    auto runtime_s = std::chrono::duration<double>(t1 - t0).count();

    std::cout << "   DFD: " << res.frechet_distance << std::endl;
    std::cout << "   " << runtime_s << " s" << std::endl;
}

void run_dataset(std::string dataset, int num, int iterations) {
    std::cout << "Running " << dataset << ", index = " << num << std::endl;
    std::cout << "   total times over " << iterations << " iterations" << std::endl;
    Curve p, q;
    load_sample("../../../datasets/" + dataset + ".txt", num, p, q);

    std::cout << " : dijkstra_prims" << std::endl;
    run(p, q, iterations, dijkstra_prims);

    //std::cout << " : dijkstra_prims (rev)" << std::endl;
    //run(q, p, iterations, dijkstra_prims);

    //std::cout << " : bbms_dpp_stepwise" << std::endl;
    //run(p, q, iterations, bbms_dpp_stepwise);

    //std::cout << " : bbms_dpp_stepwise (rev)" << std::endl;
    //run(q, p, iterations, bbms_dpp_stepwise);

    std::cout << " : bbms_dpp_stepwise_improved" << std::endl;
    run(p, q, iterations, bbms_dpp_stepwise_improved);

    //std::cout << " : bbms_dpp_stepwise_improved (rev)" << std::endl;
    //run(q, p, iterations, bbms_dpp_stepwise_improved);

    //std::cout << "bbms_dpp_stepwise_lists" << std::endl;
    //run(p, q, iterations, bbms_dpp_stepwise_lists);

    std::cout << std::endl;
}

int main(int argc, char* argv[]) {

    int iterations = 3;

    run_dataset("random/N_2300", 0, iterations);
    run_dataset("identical/N_2300", 0, iterations);
    run_dataset("outlier/N_2300", 0, iterations);
    run_dataset("alternating/N_2300", 0, iterations);

    return 0;
}