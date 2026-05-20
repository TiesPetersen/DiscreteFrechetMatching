#include "bbms_dpp_instant.h"
#include <algorithm>
#include <deque>
#include <limits>
#include <cassert>

namespace {

static constexpr double INF = std::numeric_limits<double>::infinity();

enum class Dir { DOWN, DIAG_UP, DIAG_LOW, LEFT };

struct Shortcut {
    int    target;
    double value;
    Dir    dir;
};

struct Node {
    double    dist   = 0.0;
    int       parent = -2;
    int       depth  = -1;
    bool child_upper    = false;
    bool child_diagonal = false;
    bool child_right    = false;
    Shortcut* out_low   = nullptr;
    Shortcut* out_high  = nullptr;
    std::vector<Shortcut*> in_upper;
    std::vector<Shortcut*> in_diag_up;
    std::vector<Shortcut*> in_diag_low;
    std::vector<Shortcut*> in_right;
};

struct NCAResult { double mu, mv; int nca; Dir dir_u, dir_v; };

struct SelectResult {
    int parent;
    double max_A_AB, max_B_AB; int nca_AB; Dir dir_A_AB, dir_B_AB;
    double max_B_BC, max_C_BC; int nca_BC; Dir dir_B_BC, dir_C_BC;
    double max_A_AC, max_C_AC; int nca_AC; Dir dir_A_AC, dir_C_AC;
};

// child == par+n means i+1 same j (LEFT); child == par+1 means same i j+1 (DOWN).
// Diagonal steps always have shortcuts set, so get_direction is never called for them.
Dir get_direction(int child, int par, int n) {
    if (child == par + n) return Dir::LEFT;
    return Dir::DOWN;
}

Shortcut* alloc_shortcut(std::deque<Shortcut>& pool, int target, double value, Dir dir) {
    pool.push_back({target, value, dir});
    return &pool.back();
}

void attach(std::vector<Node>& g, int par, int child, int n) {
    g[child].parent = par;
    g[child].depth  = g[par].depth + 1;
    int ci = child / n, cj = child % n;
    int pi = par   / n, pj = par   % n;
    if      (ci == pi && cj == pj + 1)     g[par].child_upper    = true;
    else if (ci == pi + 1 && cj == pj + 1) g[par].child_diagonal = true;
    else                                    g[par].child_right    = true;
}

NCAResult max_dist_to_nca(const std::vector<Node>& g, int u, int v, int n) {
    double mu = -INF, mv = -INF;
    Dir dir_u = Dir::DOWN, dir_v = Dir::DOWN;
    while (u != v) {
        if (g[v].depth > g[u].depth) {
            if (g[v].out_high != nullptr) {
                mv    = std::max(mv, g[v].out_high->value);
                dir_v = g[v].out_high->dir;
                v     = g[v].out_high->target;
            } else {
                mv    = std::max(mv, g[v].dist);
                dir_v = get_direction(v, g[v].parent, n);
                v     = g[v].parent;
            }
        } else {
            if (g[u].out_low != nullptr) {
                mu    = std::max(mu, g[u].out_low->value);
                dir_u = g[u].out_low->dir;
                u     = g[u].out_low->target;
            } else {
                mu    = std::max(mu, g[u].dist);
                dir_u = get_direction(u, g[u].parent, n);
                u     = g[u].parent;
            }
        }
    }
    return {mu, mv, u, dir_u, dir_v};
}

SelectResult select_parent(const std::vector<Node>& g, int A, int B, int C, int n) {
    auto [mu_AB, mv_AB, nca_AB, dA_AB, dB_AB] = max_dist_to_nca(g, A, B, n);
    auto [mu_BC, mv_BC, nca_BC, dB_BC, dC_BC] = max_dist_to_nca(g, B, C, n);
    auto [mu_AC, mv_AC, nca_AC, dA_AC, dC_AC] = max_dist_to_nca(g, A, C, n);

    bool A_over_B = (mu_AB <= mv_AB);
    bool B_over_C = (mu_BC <= mv_BC);
    bool A_over_C = (mu_AC <= mv_AC);

    int chosen;
    if      (A_over_B && A_over_C)  chosen = A;
    else if (!A_over_B && B_over_C) chosen = B;
    else                            chosen = C;

    return { chosen,
             mu_AB, mv_AB, nca_AB, dA_AB, dB_AB,
             mu_BC, mv_BC, nca_BC, dB_BC, dC_BC,
             mu_AC, mv_AC, nca_AC, dA_AC, dC_AC };
}

bool has_children(const std::vector<Node>& g, int idx) {
    return g[idx].child_upper || g[idx].child_diagonal || g[idx].child_right;
}

Shortcut* get_deepest_shortcut(const std::vector<Node>& g, int idx) {
    Shortcut* best = nullptr;
    int max_d = -1;
    for (Shortcut* sc : { g[idx].out_low, g[idx].out_high }) {
        if (sc != nullptr && g[sc->target].depth > max_d) {
            best  = sc;
            max_d = g[sc->target].depth;
        }
    }
    return best;
}

void remove_from(std::vector<Shortcut*>& list, Shortcut* sc) {
    auto it = std::find(list.begin(), list.end(), sc);
    if (it != list.end()) list.erase(it);
}

void remove_from_incoming(std::vector<Node>& g, Shortcut* sc) {
    if (sc == nullptr) return;
    int t = sc->target;
    switch (sc->dir) {
        case Dir::DOWN:     remove_from(g[t].in_upper,    sc); break;
        case Dir::DIAG_UP:  remove_from(g[t].in_diag_up,  sc); break;
        case Dir::DIAG_LOW: remove_from(g[t].in_diag_low, sc); break;
        case Dir::LEFT:     remove_from(g[t].in_right,    sc); break;
    }
}

void add_to_incoming(std::vector<Node>& g, Shortcut* sc) {
    int t = sc->target;
    switch (sc->dir) {
        case Dir::DOWN:     g[t].in_upper.push_back(sc);    break;
        case Dir::DIAG_UP:  g[t].in_diag_up.push_back(sc);  break;
        case Dir::DIAG_LOW: g[t].in_diag_low.push_back(sc); break;
        case Dir::LEFT:     g[t].in_right.push_back(sc);    break;
    }
}

void add_shortcut(std::deque<Shortcut>& pool, std::vector<Node>& g,
                  int origin, bool is_low, int target, double value, Dir dir) {
    Shortcut* sc = alloc_shortcut(pool, target, value, dir);
    if (is_low) g[origin].out_low  = sc;
    else        g[origin].out_high = sc;
    add_to_incoming(g, sc);
}

void detach_dead_path(std::vector<Node>& g, int B, int dpb, Dir fdir) {
    remove_from_incoming(g, g[B].out_high);
    remove_from_incoming(g, g[B].out_low);
    switch (fdir) {
        case Dir::DOWN:
            g[dpb].in_upper.clear();
            g[dpb].child_upper = false;
            break;
        case Dir::DIAG_UP:
        case Dir::DIAG_LOW:
            g[dpb].in_diag_up.clear();
            g[dpb].in_diag_low.clear();
            g[dpb].child_diagonal = false;
            break;
        case Dir::LEFT:
            g[dpb].in_right.clear();
            g[dpb].child_right = false;
            break;
    }
}

void extend_shortcuts_to(std::vector<Node>& g,
                          std::vector<Shortcut*>& list, Shortcut* followup) {
    for (Shortcut* sc : list) {
        sc->value  = std::max(sc->value, followup->value);
        sc->dir    = followup->dir;
        sc->target = followup->target;
        add_to_incoming(g, sc);
    }
}

Shortcut* extend_shortcuts(std::vector<Node>& g, int dpb, Dir fdir) {
    if (fdir == Dir::DOWN) {
        if (g[dpb].child_diagonal)
            extend_shortcuts_to(g, g[dpb].in_diag_up, g[dpb].out_high);
        else if (g[dpb].child_right)
            extend_shortcuts_to(g, g[dpb].in_right, g[dpb].out_high);
        return g[dpb].out_high;
    }
    if (fdir == Dir::DIAG_UP || fdir == Dir::DIAG_LOW) {
        if (g[dpb].child_right && !g[dpb].child_upper) {
            extend_shortcuts_to(g, g[dpb].in_right, g[dpb].out_high);
            return g[dpb].out_high;
        } else if (g[dpb].child_upper && !g[dpb].child_right) {
            extend_shortcuts_to(g, g[dpb].in_upper, g[dpb].out_low);
            return g[dpb].out_low;
        }
        return nullptr;
    }
    // fdir == Dir::LEFT
    if (g[dpb].child_diagonal)
        extend_shortcuts_to(g, g[dpb].in_diag_low, g[dpb].out_low);
    else if (g[dpb].child_upper)
        extend_shortcuts_to(g, g[dpb].in_upper, g[dpb].out_low);
    return g[dpb].out_low;
}

void adjust_ncas(SelectResult& sr, int dpb, Shortcut* followup) {
    if (followup == nullptr) return;
    if (sr.nca_AB == dpb) {
        sr.nca_AB   = followup->target;
        sr.max_A_AB = std::max(sr.max_A_AB, followup->value);
        sr.max_B_AB = std::max(sr.max_B_AB, followup->value);
        sr.dir_A_AB = followup->dir;
        sr.dir_B_AB = followup->dir;
    }
    if (sr.nca_BC == dpb) {
        sr.nca_BC   = followup->target;
        sr.max_B_BC = std::max(sr.max_B_BC, followup->value);
        sr.max_C_BC = std::max(sr.max_C_BC, followup->value);
        sr.dir_B_BC = followup->dir;
        sr.dir_C_BC = followup->dir;
    }
    if (sr.nca_AC == dpb) {
        sr.nca_AC   = followup->target;
        sr.max_A_AC = std::max(sr.max_A_AC, followup->value);
        sr.max_C_AC = std::max(sr.max_C_AC, followup->value);
        sr.dir_A_AC = followup->dir;
        sr.dir_C_AC = followup->dir;
    }
}

void update_shortcuts(std::deque<Shortcut>& pool, std::vector<Node>& g,
                      int A, int B, int C, int D, const SelectResult& sr) {
    bool AB = (g[A].parent == B);
    bool BC = (g[C].parent == B);

    if (sr.parent == A) {
        if (AB && BC) {
            add_shortcut(pool, g, A, true,  B,         g[A].dist,                         Dir::DOWN);
            add_shortcut(pool, g, C, false, B,         g[C].dist,                         Dir::LEFT);
            add_shortcut(pool, g, D, true,  B,         std::max(g[A].dist, g[D].dist),    Dir::DOWN);
        } else if (AB) {
            add_shortcut(pool, g, A, true,  sr.nca_AC, sr.max_A_AC,                       sr.dir_A_AC);
            add_shortcut(pool, g, D, true,  sr.nca_AC, std::max(sr.max_A_AC, g[D].dist),  sr.dir_A_AC);
        } else if (BC) {
            add_shortcut(pool, g, C, false, sr.nca_AC, sr.max_C_AC,                       sr.dir_C_AC);
            add_shortcut(pool, g, D, true,  sr.nca_AC, std::max(sr.max_A_AC, g[D].dist),  sr.dir_A_AC);
        } else {
            add_shortcut(pool, g, D, true,  sr.nca_AB, std::max(sr.max_A_AB, g[D].dist),  sr.dir_A_AB);
        }
    } else if (sr.parent == B) {
        if (AB && BC) {
            add_shortcut(pool, g, A, true,  B,         g[A].dist,                         Dir::DOWN);
            add_shortcut(pool, g, C, false, B,         g[C].dist,                         Dir::LEFT);
            add_shortcut(pool, g, D, false, B,         g[D].dist,                         Dir::DIAG_UP);
            add_shortcut(pool, g, D, true,  B,         g[D].dist,                         Dir::DIAG_LOW);
        } else if (AB) {
            add_shortcut(pool, g, A, true,  B,         g[A].dist,                         Dir::DOWN);
            add_shortcut(pool, g, D, false, B,         g[D].dist,                         Dir::DIAG_UP);
            add_shortcut(pool, g, D, true,  sr.nca_AC, std::max(sr.max_B_BC, g[D].dist),  sr.dir_B_BC);
        } else if (BC) {
            add_shortcut(pool, g, C, false, B,         g[C].dist,                         Dir::LEFT);
            add_shortcut(pool, g, D, false, sr.nca_AC, std::max(sr.max_B_AB, g[D].dist),  sr.dir_B_AB);
            add_shortcut(pool, g, D, true,  B,         g[D].dist,                         Dir::DIAG_LOW);
        } else {
            add_shortcut(pool, g, D, false, sr.nca_AB, std::max(sr.max_B_AB, g[D].dist),  sr.dir_B_AB);
            add_shortcut(pool, g, D, true,  sr.nca_BC, std::max(sr.max_B_BC, g[D].dist),  sr.dir_B_BC);
        }
    } else { // sr.parent == C
        if (AB && BC) {
            add_shortcut(pool, g, A, true,  B,         g[A].dist,                         Dir::DOWN);
            add_shortcut(pool, g, C, false, B,         g[C].dist,                         Dir::LEFT);
            add_shortcut(pool, g, D, false, B,         std::max(g[C].dist, g[D].dist),    Dir::LEFT);
        } else if (AB) {
            add_shortcut(pool, g, A, true,  sr.nca_AC, sr.max_A_AC,                       sr.dir_A_AC);
            add_shortcut(pool, g, D, false, sr.nca_AC, std::max(sr.max_C_AC, g[D].dist),  sr.dir_C_AC);
        } else if (BC) {
            add_shortcut(pool, g, C, false, sr.nca_AC, sr.max_C_AC,                       sr.dir_C_AC);
            add_shortcut(pool, g, D, false, sr.nca_AC, std::max(sr.max_C_AC, g[D].dist),  sr.dir_C_AC);
        } else {
            add_shortcut(pool, g, D, false, sr.nca_BC, std::max(sr.max_C_BC, g[D].dist),  sr.dir_C_BC);
        }
    }
}

} // namespace

BBMSDppInstantResult bbms_dpp_instant(const Curve& p, const Curve& q) {
    int m = (int)p.size(), n = (int)q.size();
    assert(m > 0 && n > 0);

    std::vector<Node> g((size_t)m * n);
    for (int i = 0; i < m; ++i)
        for (int j = 0; j < n; ++j)
            g[i*n+j].dist = dist(p[i], q[j]);

    g[0].parent = -1;
    g[0].depth  = 0;
    for (int i = 1; i < m; ++i) attach(g, (i-1)*n, i*n, n);
    for (int j = 1; j < n; ++j) attach(g, j-1, j, n);

    std::deque<Shortcut> pool;

    for (int i = 1; i < m; ++i) {
        for (int j = 1; j < n; ++j) {
            int A = (i-1)*n + j;
            int B = (i-1)*n + (j-1);
            int C =  i   *n + (j-1);
            int D =  i   *n + j;

            SelectResult sr = select_parent(g, A, B, C, n);
            attach(g, sr.parent, D, n);

            if (!has_children(g, B)) {
                Shortcut* s  = get_deepest_shortcut(g, B);
                int dpb      = s->target;
                detach_dead_path(g, B, dpb, s->dir);
                Shortcut* followup = extend_shortcuts(g, dpb, s->dir);
                adjust_ncas(sr, dpb, followup);
            }

            update_shortcuts(pool, g, A, B, C, D, sr);
        }
    }

    std::vector<std::pair<int,int>> matching;
    double frechet = -INF;
    for (int cur = (m-1)*n + (n-1); cur != -1; cur = g[cur].parent) {
        matching.push_back({cur/n, cur%n});
        frechet = std::max(frechet, g[cur].dist);
    }
    std::reverse(matching.begin(), matching.end());
    return {matching, frechet};
}
