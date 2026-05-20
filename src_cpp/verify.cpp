#include <iostream>
#include <string>
#include <cmath>
#include <cassert>
#include <random>
#include "common.h"
#include "dp_check.h"
#include "dijkstra_prims.h"
#include "bbms_core.h"
#include "bbms_inter.h"
#include "bbms_dpp_instant.h"
#include "bbms_dpp_stepwise.h"

static bool valid_matching(const std::vector<std::pair<int,int>>& m,
                           int last_i, int last_j,
                           const Curve& p, const Curve& q,
                           double reported_fd) {
    if (m.empty()) return false;
    if (m.front().first != 0 || m.front().second != 0) return false;
    if (m.back().first  != last_i || m.back().second != last_j) return false;
    for (int k = 1; k < (int)m.size(); ++k) {
        int di = m[k].first  - m[k-1].first;
        int dj = m[k].second - m[k-1].second;
        if (di < 0 || dj < 0 || di > 1 || dj > 1 || (di == 0 && dj == 0))
            return false;
    }
    double max_d = 0.0;
    for (auto [i, j] : m)
        max_d = std::max(max_d, dist(p[i], q[j]));
    return std::abs(max_d - reported_fd) < 1e-9;
}

// Simple LCG for deterministic test curves
static Curve make_curve(int n, double scale, unsigned seed) {
    Curve c;
    unsigned s = seed;
    for (int i = 0; i < n; ++i) {
        s = s * 1664525u + 1013904223u;
        double x = (s >> 16) / 65535.0 * scale;
        s = s * 1664525u + 1013904223u;
        double y = (s >> 16) / 65535.0 * scale;
        c.push_back({x, y});
    }
    return c;
}

static int passed = 0, failed = 0;

static void run_test(const std::string& name, const Curve& p, const Curve& q) {
    int last_i = (int)p.size() - 1;
    int last_j = (int)q.size() - 1;

    double           fd_dp   = dp_frechet(p, q);
    auto [match_dp,  fd_dpp] = dijkstra_prims(p, q);
    auto [match_bb,  fd_bb]  = bbms_core(p, q);
    auto [match_bi,  fd_bi]  = bbms_inter(p, q);
    auto [match_dpp, fd_dpi] = bbms_dpp_instant(p, q);
    auto [match_dps, fd_dps] = bbms_dpp_stepwise(p, q);

    bool ok = true;

    // Fréchet distance checks
    if (std::abs(fd_dp - fd_dpp) > 1e-9) {
        std::cout << "  FAIL " << name << ": dp=" << fd_dp << " dijkstra_prims=" << fd_dpp << "\n";
        ok = false;
    }
    if (std::abs(fd_dp - fd_bb) > 1e-9) {
        std::cout << "  FAIL " << name << ": dp=" << fd_dp << " bbms_core=" << fd_bb << "\n";
        ok = false;
    }
    if (std::abs(fd_bb - fd_bi) > 1e-9) {
        std::cout << "  FAIL " << name << ": bbms_core=" << fd_bb << " bbms_inter=" << fd_bi << "\n";
        ok = false;
    }
    if (std::abs(fd_bi - fd_dpi) > 1e-9) {
        std::cout << "  FAIL " << name << ": bbms_inter=" << fd_bi << " bbms_dpp_instant=" << fd_dpi << "\n";
        ok = false;
    }
    if (std::abs(fd_bi - fd_dps) > 1e-9) {
        std::cout << "  FAIL " << name << ": bbms_inter=" << fd_bi << " bbms_dpp_stepwise=" << fd_dps << "\n";
        ok = false;
    }

    // Matching validity checks
    if (!valid_matching(match_dp, last_i, last_j, p, q, fd_dpp)) {
        std::cout << "  FAIL " << name << ": dijkstra_prims matching invalid\n";
        ok = false;
    }
    if (!valid_matching(match_bb, last_i, last_j, p, q, fd_bb)) {
        std::cout << "  FAIL " << name << ": bbms_core matching invalid\n";
        ok = false;
    }
    if (!valid_matching(match_bi, last_i, last_j, p, q, fd_bi)) {
        std::cout << "  FAIL " << name << ": bbms_inter matching invalid\n";
        ok = false;
    }
    if (!valid_matching(match_dpp, last_i, last_j, p, q, fd_dpi)) {
        std::cout << "  FAIL " << name << ": bbms_dpp_instant matching invalid\n";
        ok = false;
    }

    // BBMSCore and BBMSInter must produce the identical matching (same tree)
    if (match_bb != match_bi) {
        std::cout << "  FAIL " << name << ": bbms_core and bbms_inter matchings differ"
                  << " (core len=" << match_bb.size() << " inter len=" << match_bi.size() << ")\n";
        int lim = (int)std::min(match_bb.size(), match_bi.size());
        for (int k = 0; k < lim; ++k) {
            if (match_bb[k] != match_bi[k]) {
                std::cout << "    first diff at step " << k
                          << ": core=(" << match_bb[k].first << "," << match_bb[k].second << ")"
                          << " inter=(" << match_bi[k].first << "," << match_bi[k].second << ")\n";
                break;
            }
        }
        ok = false;
    }

    // BBMSDppStepwise must produce the identical matching as BBMSInter
    if (match_dps != match_bi) {
        std::cout << "  FAIL " << name << ": bbms_dpp_stepwise and bbms_inter matchings differ"
                  << " (dps len=" << match_dps.size() << " inter len=" << match_bi.size() << ")\n";
        int lim = (int)std::min(match_dps.size(), match_bi.size());
        for (int k = 0; k < lim; ++k) {
            if (match_dps[k] != match_bi[k]) {
                std::cout << "    first diff at step " << k
                          << ": dps=(" << match_dps[k].first << "," << match_dps[k].second << ")"
                          << " inter=(" << match_bi[k].first << "," << match_bi[k].second << ")\n";
                break;
            }
        }
        ok = false;
    }

    // BBMSDppInstant must produce the identical matching as BBMSInter (same tree, just faster shortcuts)
    if (match_dpp != match_bi) {
        std::cout << "  FAIL " << name << ": bbms_dpp_instant and bbms_inter matchings differ"
                  << " (dpp len=" << match_dpp.size() << " inter len=" << match_bi.size() << ")\n";
        int lim = (int)std::min(match_dpp.size(), match_bi.size());
        for (int k = 0; k < lim; ++k) {
            if (match_dpp[k] != match_bi[k]) {
                std::cout << "    first diff at step " << k
                          << ": dpp=(" << match_dpp[k].first << "," << match_dpp[k].second << ")"
                          << " inter=(" << match_bi[k].first << "," << match_bi[k].second << ")\n";
                break;
            }
        }
        ok = false;
    }

    if (ok) {
        std::cout << "  PASS  " << name << "  fd=" << fd_dp << "\n";
        ++passed;
    } else {
        ++failed;
    }
}

int main() {
    std::cout << "=== Correctness verification ===\n\n";

    // --- Original 13 test cases ---
    run_test("2x2_trivial",      {{0,0},{1,0}}, {{0,0},{0,1}});
    run_test("equal_3pt",        {{0,0},{1,1},{2,0}}, {{0,0},{1,1},{2,0}});
    run_test("1x1",              {{3,4}}, {{0,0}});
    run_test("single_p",         {{5,5}}, {{0,0},{1,0},{2,0},{5,5}});
    run_test("single_q",         {{0,0},{1,0},{2,0},{5,5}}, {{5,5}});
    run_test("collinear",        {{0,0},{1,0},{2,0},{3,0}}, {{0,0},{1,0},{2,0},{3,0}});

    run_test("random_5x5",       make_curve( 5, 10, 42),  make_curve( 5, 10, 43));
    run_test("random_5x7",       make_curve( 5, 10, 77),  make_curve( 7, 10, 78));
    run_test("random_10x10",     make_curve(10, 10, 99),  make_curve(10, 10,100));
    run_test("random_20x15",     make_curve(20, 10,  7),  make_curve(15, 10,  8));
    run_test("random_asym_2x10", make_curve( 2,  5,300),  make_curve(10,  5,301));
    run_test("random_asym_10x2", make_curve(10,  5,400),  make_curve( 2,  5,401));

    {
        Curve p = make_curve(10, 1.0, 200);
        Curve q = make_curve(10, 1.0, 201);
        q.back() = {1000.0, 0.0};
        run_test("adversarial_outlier_end", p, q);
    }

    // --- Additional test cases ---

    // Larger random grids
    run_test("random_3x3",       make_curve( 3, 10, 500),  make_curve( 3, 10, 501));
    run_test("random_7x7",       make_curve( 7, 10, 502),  make_curve( 7, 10, 503));
    run_test("random_15x20",     make_curve(15, 10, 504),  make_curve(20, 10, 505));
    run_test("random_30x30",     make_curve(30, 10, 506),  make_curve(30, 10, 507));
    run_test("random_50x40",     make_curve(50, 10, 508),  make_curve(40, 10, 509));
    run_test("random_100x100",   make_curve(100,10, 510),  make_curve(100,10, 511));

    // Highly asymmetric
    run_test("random_asym_3x50", make_curve(  3, 10, 512),  make_curve( 50, 10, 513));
    run_test("random_asym_50x3", make_curve( 50, 10, 514),  make_curve(  3, 10, 515));
    run_test("random_asym_1x100",make_curve(  1, 10, 516),  make_curve(100, 10, 517));
    run_test("random_asym_100x1",make_curve(100, 10, 518),  make_curve(  1, 10, 519));

    // Adversarial variants
    {
        Curve p = make_curve(10, 1.0, 520);
        Curve q = make_curve(10, 1.0, 521);
        q.front() = {1000.0, 0.0};
        run_test("adversarial_outlier_start", p, q);
    }
    {
        Curve p = make_curve(11, 1.0, 522);
        Curve q = make_curve(11, 1.0, 523);
        q[5] = {1000.0, 0.0};
        run_test("adversarial_outlier_middle", p, q);
    }
    {
        Curve p = make_curve(10, 1.0, 524);
        Curve q = make_curve(10, 1.0, 525);
        q.front() = {800.0,  0.0};
        q.back()  = {1000.0, 0.0};
        run_test("adversarial_both_ends", p, q);
    }

    // Identical curves (fd must be 0)
    {
        Curve same = make_curve(5, 10, 530);
        run_test("identical_5pt", same, same);
    }
    {
        Curve same = make_curve(20, 10, 531);
        run_test("identical_20pt", same, same);
    }

    // Two parallel horizontal lines
    {
        Curve p, q;
        for (int i = 0; i < 10; ++i) { p.push_back({(double)i, 0.0}); }
        for (int i = 0; i < 10; ++i) { q.push_back({(double)i, 1.0}); }
        run_test("parallel_lines_10pt", p, q);
    }

    // --- 1000 random fuzz cases (lengths uniform in [10, 1000]) ---
    std::cout << "\n=== Fuzz tests (1000 random pairs, N in [10, 1000]) ===\n\n";
    {
        std::mt19937 rng(777777u);
        std::uniform_int_distribution<int> len_dist(10, 1000);
        for (int i = 0; i < 1000; ++i) {
            int      m      = len_dist(rng);
            int      n      = len_dist(rng);
            unsigned seed_p = rng();
            unsigned seed_q = rng();
            run_test("fuzz_" + std::to_string(i) + "_" + std::to_string(m) + "x" + std::to_string(n),
                     make_curve(m, 10.0, seed_p),
                     make_curve(n, 10.0, seed_q));
        }
    }

    std::cout << "\n" << passed << " passed, " << failed << " failed\n";
    return failed > 0 ? 1 : 0;
}
