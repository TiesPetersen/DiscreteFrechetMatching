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

struct NCAResult { 
    double max_distance_u;  // max distance on u's side to NCA(u,v)
    double max_distance_v;  // max distance on v's side to NCA(u,v)
    long long nca;          // index of nearest common ancestor of u and v
};

// All pairwise NCA results needed by update_shortcuts.
// e.g. max_A_AB = max dist on A's side to NCA(A,B); max_B_AB = max dist on B's side to NCA(A,B).
struct SelectResult {
    long long parent;                               // selected parent for D
    double max_A_AB, max_B_AB; long long nca_AB;    // pair A, B stats
    double max_B_BC, max_C_BC; long long nca_BC;    // pair B, C stats (only if has_BC)
    double max_A_AC, max_C_AC; long long nca_AC;    // pair A, C stats (only if has_AC)
    bool has_BC, has_AC;                            // which of the two optional pairs were queried
};

// Get maximum distance from u and v to their nearest common ancestor (NCA) in G, and the index of the NCA.
// The NCA's own distance is not included in the max-distance calculation. 
// Walks u and v up to their NCA using shortcuts where available.
NCAResult max_distance_to_nca(const std::vector<Node>& G, long long u, long long v) {
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

    return {max_distance_u, max_distance_v, u};
}

// Select parent among A, B, C that has the lowest maximum distance to NCA.
// Break ties by preferring A > B > C. Two NCA queries are enough:
// the first decides between A and B, the second compares the winner with C.
SelectResult select_parent(const std::vector<Node>& G, long long A, long long B, long long C) {
    SelectResult r{};

    // Check pair A, B
    auto [max_A_AB, max_B_AB, nca_AB] = max_distance_to_nca(G, A, B);
    r.max_A_AB = max_A_AB; r.max_B_AB = max_B_AB; r.nca_AB = nca_AB;

    if (max_A_AB <= max_B_AB) {
        // A beats B, so compare A with C
        auto [max_A_AC, max_C_AC, nca_AC] = max_distance_to_nca(G, A, C);
        r.max_A_AC = max_A_AC; r.max_C_AC = max_C_AC; r.nca_AC = nca_AC; r.has_AC = true;
        r.parent = (max_A_AC <= max_C_AC) ? A : C;
    } else {
        // B beats A, so compare B with C
        auto [max_B_BC, max_C_BC, nca_BC] = max_distance_to_nca(G, B, C);
        r.max_B_BC = max_B_BC; r.max_C_BC = max_C_BC; r.nca_BC = nca_BC; r.has_BC = true;
        r.parent = (max_B_BC <= max_C_BC) ? B : C;
    }
    return r;
}

// Run the third NCA query only when update_shortcuts needs it.
// Without dead path pruning, shortcuts must point to a freshly queried NCA to stay as long as possible.
void complete_for_shortcuts(const std::vector<Node>& G, long long A, long long B, long long C, SelectResult& r) {
    bool AB = (G[A].parent == B);
    bool BC = (G[C].parent == B);

    // Pair A, C is used whenever A or C hangs directly from B
    if (!r.has_AC && (AB || BC)) {
        auto [max_A_AC, max_C_AC, nca_AC] = max_distance_to_nca(G, A, C);
        r.max_A_AC = max_A_AC; r.max_C_AC = max_C_AC; r.nca_AC = nca_AC; r.has_AC = true;
    }

    // Pair B, C is used when D hangs from C and neither A nor C hangs from B
    if (!r.has_BC && r.parent == C && !AB && !BC) {
        auto [max_B_BC, max_C_BC, nca_BC] = max_distance_to_nca(G, B, C);
        r.max_B_BC = max_B_BC; r.max_C_BC = max_C_BC; r.nca_BC = nca_BC; r.has_BC = true;
    }
}

// Attach child to parent in g, updating child's depth and parent index.
void attach(std::vector<Node>& G, long long parent, long long child) {
    G[child].parent = parent;
    G[child].depth  = G[parent].depth + 1;
}

// Set shortcuts on A, C, D after attaching D to its parent.
void update_shortcuts(std::vector<Node>& G, long long A, long long B, long long C, long long D, const SelectResult& select_results) {
    bool AB = (G[A].parent == B);
    bool BC = (G[C].parent == B);

    if (select_results.parent == A) {
        if (AB && BC) {
            G[A].low  = { B, G[A].distance };                                      COUNT(shortcuts_written);
            G[C].high = { B, G[C].distance };                                      COUNT(shortcuts_written);
            G[D].low  = { B, std::max(G[A].distance, G[D].distance) };             COUNT(shortcuts_written);
        } else if (AB) {
            G[A].low  = { select_results.nca_AC, select_results.max_A_AC };                                COUNT(shortcuts_written);
            G[D].low  = { select_results.nca_AC, std::max(select_results.max_A_AC, G[D].distance) };       COUNT(shortcuts_written);
        } else if (BC) {
            G[C].high = { select_results.nca_AC, select_results.max_C_AC };                                COUNT(shortcuts_written);
            G[D].low  = { select_results.nca_AC, std::max(select_results.max_A_AC, G[D].distance) };       COUNT(shortcuts_written);
        } else {
            G[D].low  = { select_results.nca_AB, std::max(select_results.max_A_AB, G[D].distance) };       COUNT(shortcuts_written);
        }
    } else if (select_results.parent == B) {
        if (AB && BC) {
            G[A].low  = { B, G[A].distance };                                      COUNT(shortcuts_written);
            G[C].high = { B, G[C].distance };                                      COUNT(shortcuts_written);
            G[D].high = { B, G[D].distance };                                      COUNT(shortcuts_written);
            G[D].low  = { B, G[D].distance };                                      COUNT(shortcuts_written);
        } else if (AB) {
            G[A].low  = { B, G[A].distance };                                      COUNT(shortcuts_written);
            G[D].high = { B, G[D].distance };                                      COUNT(shortcuts_written);
            G[D].low  = { select_results.nca_AC, std::max(select_results.max_B_BC, G[D].distance) };       COUNT(shortcuts_written);
        } else if (BC) {
            G[C].high = { B, G[C].distance };                                      COUNT(shortcuts_written);
            G[D].high = { select_results.nca_AC, std::max(select_results.max_B_AB, G[D].distance) };       COUNT(shortcuts_written);
            G[D].low  = { B, G[D].distance };                                      COUNT(shortcuts_written);
        } else {
            G[D].high = { select_results.nca_AB, std::max(select_results.max_B_AB, G[D].distance) };       COUNT(shortcuts_written);
            G[D].low  = { select_results.nca_BC, std::max(select_results.max_B_BC, G[D].distance) };       COUNT(shortcuts_written);
        }
    } else if (select_results.parent == C) {
        if (AB && BC) {
            G[A].low  = { B, G[A].distance };                                      COUNT(shortcuts_written);
            G[C].high = { B, G[C].distance };                                      COUNT(shortcuts_written);
            G[D].high = { B, std::max(G[C].distance, G[D].distance) };             COUNT(shortcuts_written);
        } else if (AB) {
            G[A].low  = { select_results.nca_AC, select_results.max_A_AC };                                COUNT(shortcuts_written);
            G[D].high = { select_results.nca_AC, std::max(select_results.max_C_AC, G[D].distance) };       COUNT(shortcuts_written);
        } else if (BC) {
            G[C].high = { select_results.nca_AC, select_results.max_C_AC };                                COUNT(shortcuts_written);
            G[D].high = { select_results.nca_AC, std::max(select_results.max_C_AC, G[D].distance) };       COUNT(shortcuts_written);
        } else {
            G[D].high = { select_results.nca_BC, std::max(select_results.max_C_BC, G[D].distance) };       COUNT(shortcuts_written);
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

            // Select parent for D and get all NCA results needed for shortcut updates
            SelectResult select_results = select_parent(G, A, B, C);
            complete_for_shortcuts(G, A, B, C, select_results);
            attach(G, select_results.parent, D);
            TRACE_PARENT(select_results.parent);

            // Update shortcuts on A, C, D after attaching D to its parent
            update_shortcuts(G, A, B, C, D, select_results);
        }
    }

    // Trace path from root to (m-1, n-1) to extract matching and max distance
    auto [ matching, max_distance ] = extract_matching(G, m, n);

    return { matching, max_distance };
}