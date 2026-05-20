#include "bbms_inter.h"
#include <algorithm>
#include <limits>
#include <cassert>

namespace {

struct Shortcut {
    int    target;  // flat index; -1 = absent
    double value;
};

struct Node {
    double   dist;
    int      parent;  // flat index; -1 = root, -2 = unattached
    int      depth;
    Shortcut low;
    Shortcut high;
};

struct NCAResult { double mu, mv; int nca; };

// Walk u and v up to their NCA using shortcuts where available.
// u uses its low shortcut (u is shallower / equal depth).
// v uses its high shortcut (v is deeper).
// Returns (max dist on u's side, max dist on v's side, NCA flat index).
// NCA's own distance is NOT included, matching the Python implementation.
NCAResult max_dist_to_nca(const std::vector<Node>& g, int u, int v) {
    double mu = -std::numeric_limits<double>::infinity();
    double mv = -std::numeric_limits<double>::infinity();
    while (u != v) {
        if (g[v].depth > g[u].depth) {
            if (g[v].high.target != -1) {
                mv = std::max(mv, g[v].high.value);
                v  = g[v].high.target;
            } else {
                mv = std::max(mv, g[v].dist);
                v  = g[v].parent;
            }
        } else {
            if (g[u].low.target != -1) {
                mu = std::max(mu, g[u].low.value);
                u  = g[u].low.target;
            } else {
                mu = std::max(mu, g[u].dist);
                u  = g[u].parent;
            }
        }
    }
    return {mu, mv, u};
}

// All pairwise NCA results needed by update_shortcuts.
// mu_XY = max dist on X's side to NCA(X,Y); mv_XY = max dist on Y's side.
struct SelectResult {
    int    parent;
    double max_A_AB, max_B_AB; int nca_AB;
    double max_B_BC, max_C_BC; int nca_BC;
    double max_A_AC, max_C_AC; int nca_AC;
};

SelectResult select_parent(const std::vector<Node>& g, int A, int B, int C) {
    auto [mu_AB, mv_AB, nca_AB] = max_dist_to_nca(g, A, B);
    auto [mu_BC, mv_BC, nca_BC] = max_dist_to_nca(g, B, C);
    auto [mu_AC, mv_AC, nca_AC] = max_dist_to_nca(g, A, C);

    bool A_over_B = (mu_AB <= mv_AB);
    bool B_over_C = (mu_BC <= mv_BC);
    bool A_over_C = (mu_AC <= mv_AC);

    int chosen;
    if      (A_over_B && A_over_C)  chosen = A;
    else if (!A_over_B && B_over_C) chosen = B;
    else                            chosen = C;

    return { chosen,
             mu_AB, mv_AB, nca_AB,
             mu_BC, mv_BC, nca_BC,
             mu_AC, mv_AC, nca_AC };
}

void attach(std::vector<Node>& g, int parent, int child) {
    g[child].parent = parent;
    g[child].depth  = g[parent].depth + 1;
}

// Set shortcuts on A, C, D after attaching D to its parent.
// Mirrors the 12-case updateShortcuts from src/BBMS_inter/main.py exactly.
void update_shortcuts(std::vector<Node>& g, int A, int B, int C, int D,
                      const SelectResult& sr) {
    bool AB = (g[A].parent == B);
    bool BC = (g[C].parent == B);

    if (sr.parent == A) {
        if (AB && BC) {
            g[A].low  = { B,         g[A].dist };
            g[C].high = { B,         g[C].dist };
            g[D].low  = { B,         std::max(g[A].dist, g[D].dist) };
        } else if (AB) {
            g[A].low  = { sr.nca_AC, sr.max_A_AC };
            g[D].low  = { sr.nca_AC, std::max(sr.max_A_AC, g[D].dist) };
        } else if (BC) {
            g[C].high = { sr.nca_AC, sr.max_C_AC };
            g[D].low  = { sr.nca_AC, std::max(sr.max_A_AC, g[D].dist) };
        } else {
            g[D].low  = { sr.nca_AB, std::max(sr.max_A_AB, g[D].dist) };
        }
    } else if (sr.parent == B) {
        if (AB && BC) {
            g[A].low  = { B, g[A].dist };
            g[C].high = { B, g[C].dist };
            g[D].high = { B, g[D].dist };
            g[D].low  = { B, g[D].dist };
        } else if (AB) {
            g[A].low  = { B,         g[A].dist };
            g[D].high = { B,         g[D].dist };
            g[D].low  = { sr.nca_AC, std::max(sr.max_B_BC, g[D].dist) };
        } else if (BC) {
            g[C].high = { B,         g[C].dist };
            g[D].high = { sr.nca_AC, std::max(sr.max_B_AB, g[D].dist) };
            g[D].low  = { B,         g[D].dist };
        } else {
            g[D].high = { sr.nca_AB, std::max(sr.max_B_AB, g[D].dist) };
            g[D].low  = { sr.nca_BC, std::max(sr.max_B_BC, g[D].dist) };
        }
    } else {  // sr.parent == C
        if (AB && BC) {
            g[A].low  = { B,         g[A].dist };
            g[C].high = { B,         g[C].dist };
            g[D].high = { B,         std::max(g[C].dist, g[D].dist) };
        } else if (AB) {
            g[A].low  = { sr.nca_AC, sr.max_A_AC };
            g[D].high = { sr.nca_AC, std::max(sr.max_C_AC, g[D].dist) };
        } else if (BC) {
            g[C].high = { sr.nca_AC, sr.max_C_AC };
            g[D].high = { sr.nca_AC, std::max(sr.max_C_AC, g[D].dist) };
        } else {
            g[D].high = { sr.nca_BC, std::max(sr.max_C_BC, g[D].dist) };
        }
    }
}

} // namespace

BBMSInterResult bbms_inter(const Curve& p, const Curve& q) {
    int m = (int)p.size(), n = (int)q.size();
    assert(m > 0 && n > 0);

    std::vector<Node> g((size_t)m * n);
    for (int i = 0; i < m; ++i)
        for (int j = 0; j < n; ++j)
            g[i*n+j] = { dist(p[i], q[j]), -2, -1, {-1, 0.0}, {-1, 0.0} };

    g[0].parent = -1;
    g[0].depth  = 0;

    for (int i = 1; i < m; ++i) attach(g, (i-1)*n, i*n);
    for (int j = 1; j < n; ++j) attach(g, j-1,     j  );

    for (int i = 1; i < m; ++i) {
        for (int j = 1; j < n; ++j) {
            int A = (i-1)*n + j;
            int B = (i-1)*n + (j-1);
            int C =  i   *n + (j-1);
            int D =  i   *n + j;
            SelectResult sr = select_parent(g, A, B, C);
            attach(g, sr.parent, D);
            update_shortcuts(g, A, B, C, D, sr);
        }
    }

    std::vector<std::pair<int,int>> matching;
    double frechet = -std::numeric_limits<double>::infinity();
    for (int cur = (m-1)*n + (n-1); cur != -1; cur = g[cur].parent) {
        matching.push_back({cur/n, cur%n});
        frechet = std::max(frechet, g[cur].dist);
    }
    std::reverse(matching.begin(), matching.end());

    return {matching, frechet};
}
