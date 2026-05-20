#include "bbms_core.h"
#include <algorithm>
#include <limits>
#include <cassert>

namespace {

struct Node {
    double dist;
    int parent; // flat index; -1 = root, -2 = unattached
    int depth;
};

// Returns (max dist on u's path to NCA, max dist on v's path to NCA).
// NCA's own distance is NOT included, matching the Python implementation.
std::pair<double,double> max_dist_to_nca(const std::vector<Node>& g, int u, int v) {
    double mu = -std::numeric_limits<double>::infinity();
    double mv = -std::numeric_limits<double>::infinity();

    while (g[u].depth > g[v].depth) { mu = std::max(mu, g[u].dist); u = g[u].parent; }
    while (g[v].depth > g[u].depth) { mv = std::max(mv, g[v].dist); v = g[v].parent; }
    while (u != v) {
        mu = std::max(mu, g[u].dist); u = g[u].parent;
        mv = std::max(mv, g[v].dist); v = g[v].parent;
    }
    return {mu, mv};
}

// Select parent among A, B, C: lowest max-dist path to NCA; tie-break A > B > C.
int select_parent(const std::vector<Node>& g, int A, int B, int C) {
    auto [mA_AB, mB_AB] = max_dist_to_nca(g, A, B);
    auto [mB_BC, mC_BC] = max_dist_to_nca(g, B, C);
    auto [mA_AC, mC_AC] = max_dist_to_nca(g, A, C);

    bool A_over_B = (mA_AB <= mB_AB);
    bool B_over_C = (mB_BC <= mC_BC);
    bool A_over_C = (mA_AC <= mC_AC);

    if (A_over_B && A_over_C) return A;
    if (!A_over_B && B_over_C) return B;
    return C;
}

void attach(std::vector<Node>& g, int parent, int child) {
    g[child].parent = parent;
    g[child].depth  = g[parent].depth + 1;
}

} // namespace

BBMSCoreResult bbms_core(const Curve& p, const Curve& q) {
    int m = (int)p.size(), n = (int)q.size();
    assert(m > 0 && n > 0);

    std::vector<Node> g((size_t)m * n);
    for (int i = 0; i < m; ++i)
        for (int j = 0; j < n; ++j)
            g[i*n+j] = { dist(p[i], q[j]), -2, -1 };

    // Root
    g[0].parent = -1;
    g[0].depth  = 0;

    // First column and first row
    for (int i = 1; i < m; ++i) attach(g, (i-1)*n, i*n);
    for (int j = 1; j < n; ++j) attach(g, j-1,     j  );

    // Inner cells: row-major order so all three candidates are already attached
    for (int i = 1; i < m; ++i)
        for (int j = 1; j < n; ++j) {
            int A = (i-1)*n + j;     // left
            int B = (i-1)*n + (j-1); // diagonal
            int C =  i   *n + (j-1); // below
            attach(g, select_parent(g, A, B, C), i*n+j);
        }

    // Trace path from (m-1, n-1) to root
    std::vector<std::pair<int,int>> matching;
    double frechet = -std::numeric_limits<double>::infinity();
    for (int cur = (m-1)*n + (n-1); cur != -1; cur = g[cur].parent) {
        matching.push_back({cur/n, cur%n});
        frechet = std::max(frechet, g[cur].dist);
    }
    std::reverse(matching.begin(), matching.end());

    return {matching, frechet};
}
