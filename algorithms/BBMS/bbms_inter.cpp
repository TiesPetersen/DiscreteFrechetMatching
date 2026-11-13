#include "bbms_inter.h"
#include "../counters.h"
#include "../parent_trace.h"
#include <algorithm>


namespace {

struct Shortcut {
    long long target;   // -1 = absent
    double value;       // max distance to NCA
};

struct Node {
    double distance = 0.0;      // squared distance from p[i] to q[j]
    long long parent = -2;      // index of parent, -1 = root, -2 = no parent/unattached
    int depth = -1;             // depth in the tree, root has depth 0
    Shortcut low = {-1, 0.0};   // lower shortcut
    Shortcut high = {-1, 0.0};  // upper shortcut
};

// True if the max distance on u's side to NCA(u,v) is at most the max distance on v's side.
// The NCA's own distance is not included. Walks u and v up using shortcuts where available.
bool u_side_at_most_v_side(const std::vector<Node>& G, long long u, long long v) {
    double max_distance_u = -INF, max_distance_v = -INF;

    // Walk the deeper node up the tree, until both nodes meet
    while (u != v) {
        if (G[v].depth > G[u].depth) {
            // Walk v up the tree, using shortcuts if available
            if (G[v].high.target != -1) {
                max_distance_v = std::max(max_distance_v, G[v].high.value);
                v  = G[v].high.target;
                COUNT(nca_shortcut_hops);
            } else {
                max_distance_v = std::max(max_distance_v, G[v].distance);
                v  = G[v].parent;
                COUNT(nca_regular_hops);
            }
        } else {
            // Walk u up the tree, using shortcuts if available
            if (G[u].low.target != -1) {
                max_distance_u = std::max(max_distance_u, G[u].low.value);
                u  = G[u].low.target;
                COUNT(nca_shortcut_hops);
            } else {
                max_distance_u = std::max(max_distance_u, G[u].distance);
                u  = G[u].parent;
                COUNT(nca_regular_hops);
            }
        }
    }

    return max_distance_u <= max_distance_v;
}

// Select parent among A, B, C that has the lowest maximum distance to NCA.
// Break ties by preferring A > B > C. Two NCA queries are enough:
// the first decides between A and B, the second compares the winner with C.
long long select_parent(const std::vector<Node>& G, long long A, long long B, long long C) {
    if (u_side_at_most_v_side(G, A, B)) return u_side_at_most_v_side(G, A, C) ? A : C;
    return u_side_at_most_v_side(G, B, C) ? B : C;
}

// Attach child to parent in g, updating child's depth and parent index.
void attach(std::vector<Node>& G, long long parent, long long child) {
    G[child].parent = parent;
    G[child].depth  = G[parent].depth + 1;
}

// Set a shortcut directly.
void set_shortcut(Shortcut& shortcut, long long target, double value) {
    shortcut = { target, value };
    COUNT(shortcuts_written);
}

// Set x's shortcut (low or high) to continue its parent's shortcut one step further.
// It gets the same target and value a fresh NCA query would give, without the query.
void set_extending_shortcut(std::vector<Node>& G, long long x, bool is_low) {
    const Shortcut& extend = is_low ? G[G[x].parent].low : G[G[x].parent].high;
    set_shortcut(is_low ? G[x].low : G[x].high, extend.target, std::max(G[x].distance, extend.value));
}

// Set shortcuts on A, C, D after attaching D to its parent.
// A's and C's shortcuts are set before D's, because D's may extend them.
void update_shortcuts(std::vector<Node>& G, long long A, long long B, long long C, long long D, long long parent_D) {
    bool AB = (G[A].parent == B);
    bool BC = (G[C].parent == B);

    if (parent_D == A) {
        if (AB && BC) {
            set_shortcut(G[A].low, B, G[A].distance);
            set_shortcut(G[C].high, B, G[C].distance);
            set_shortcut(G[D].low, B, std::max(G[A].distance, G[D].distance));
        } else if (AB) {
            set_extending_shortcut(G, A, true);
            set_extending_shortcut(G, D, true);
        } else if (BC) {
            set_extending_shortcut(G, C, false);
            set_extending_shortcut(G, D, true);
        } else {
            set_extending_shortcut(G, D, true);
        }
    } else if (parent_D == B) {
        if (AB && BC) {
            set_shortcut(G[A].low, B, G[A].distance);
            set_shortcut(G[C].high, B, G[C].distance);
            set_shortcut(G[D].high, B, G[D].distance);
            set_shortcut(G[D].low, B, G[D].distance);
        } else if (AB) {
            set_shortcut(G[A].low, B, G[A].distance);
            set_shortcut(G[D].high, B, G[D].distance);
            set_extending_shortcut(G, D, true);
        } else if (BC) {
            set_shortcut(G[C].high, B, G[C].distance);
            set_extending_shortcut(G, D, false);
            set_shortcut(G[D].low, B, G[D].distance);
        } else {
            set_extending_shortcut(G, D, false);
            set_extending_shortcut(G, D, true);
        }
    } else { // parent_D == C
        if (AB && BC) {
            set_shortcut(G[A].low, B, G[A].distance);
            set_shortcut(G[C].high, B, G[C].distance);
            set_shortcut(G[D].high, B, std::max(G[C].distance, G[D].distance));
        } else if (AB) {
            set_extending_shortcut(G, A, true);
            set_extending_shortcut(G, D, false);
        } else if (BC) {
            set_extending_shortcut(G, C, false);
            set_extending_shortcut(G, D, false);
        } else {
            set_extending_shortcut(G, D, false);
        }
    }
}

} // namespace


MatchingAndFrechetDistance bbms_inter(const Curve& p, const Curve& q) {
    long long m = (long long) p.size(), n = (long long) q.size();

    // Initialize graph G with distances and unattached nodes
    std::vector<Node> G(m * n);
    for (long long i = 0; i < m; ++i)
        for (long long j = 0; j < n; ++j)
            G[i * n + j].distance = squared_dist(p[i], q[j]);

    // Setup root node
    G[0].parent = -1;
    G[0].depth  = 0;

    // Attach bottom row to root
    for (long long i = 1; i < m; ++i) attach(G, (i - 1) * n, i * n);

    // Attach left column to root
    for (long long j = 1; j < n; ++j) attach(G, j - 1, j);

    // Attach interior nodes to parent with lowest max-dist path to NCA, while updating shortcuts
    for (long long i = 1; i < m; ++i) {
        for (long long j = 1; j < n; ++j) {
            long long A = (i - 1) * n + j;        // left
            long long B = (i - 1) * n + (j - 1);  // diagonal
            long long C = i * n + (j - 1);        // below
            long long D = i * n + j;              // current

            // Select parent for D and attach it
            long long parent_D = select_parent(G, A, B, C);
            attach(G, parent_D, D);
            TRACE_PARENT(parent_D);

            // Update shortcuts on A, C, D after attaching D to its parent
            update_shortcuts(G, A, B, C, D, parent_D);
        }
    }

    // Trace path from root to (m-1, n-1) to extract matching and max distance
    auto [ matching, max_distance ] = extract_matching(G, m, n);

    return { matching, max_distance };
}