#include "bbms_core.h"
#include <algorithm>


namespace {

struct Node {
    double distance;    // distance from p[i] to q[j]
    long long parent;   // index of parent, -1 = root, -2 = no parent/unattached
    int depth;          // depth in the tree, root has depth 0
};

// Get maximum distance from u and v to their nearest common ancestor (NCA) in G. 
// The NCA's own distance is not included in the max-distance calculation. 
std::pair<double,double> max_distance_to_nca(const std::vector<Node>& G, long long u, long long v) {
    double max_distance_u = -INF;
    double max_distance_v = -INF;

    // Walk the deeper node up the tree, until both nodes are at the same depth
    while (G[u].depth > G[v].depth) { max_distance_u = std::max(max_distance_u, G[u].distance); u = G[u].parent; }
    while (G[v].depth > G[u].depth) { max_distance_v = std::max(max_distance_v, G[v].distance); v = G[v].parent; }

    // Now walk both nodes up the tree until they meet at the NCA
    while (u != v) {
        max_distance_u = std::max(max_distance_u, G[u].distance); u = G[u].parent;
        max_distance_v = std::max(max_distance_v, G[v].distance); v = G[v].parent;
    }

    return {max_distance_u, max_distance_v};
}

// Select parent among A, B, C that has the lowest maximum distance to NCA.
// Break ties by preferring A > B > C.
long long select_parent(const std::vector<Node>& G, long long A, long long B, long long C) {
    // Check pair A, B
    auto [max_A_AB, max_B_AB] = max_distance_to_nca(G, A, B);

    // Check pair B, C
    auto [max_B_BC, max_C_BC] = max_distance_to_nca(G, B, C);

    // Check pair A, C
    auto [max_A_AC, max_C_AC] = max_distance_to_nca(G, A, C);

    // Select parent with lowest maximum distance to NCA, breaking ties by A > B > C
    bool A_over_B = (max_A_AB <= max_B_AB);
    bool B_over_C = (max_B_BC <= max_C_BC);
    bool A_over_C = (max_A_AC <= max_C_AC);
    if (A_over_B && A_over_C) return A;
    if (!A_over_B && B_over_C) return B;
    return C;
}

// Attach child to parent in G, updating child's depth and parent index.
void attach(std::vector<Node>& G, long long parent, long long child) {
    G[child].parent = parent;
    G[child].depth  = G[parent].depth + 1;
}

} // namespace


MatchingAndFrechetDistance bbms_core(const Curve& p, const Curve& q) {
    long long m = (long long) p.size(), n = (long long) q.size();

    // Initialize graph G with distances and unattached nodes
    std::vector<Node> G((size_t) m * n);
    for (long long i = 0; i < m; ++i)
        for (long long j = 0; j < n; ++j)
            G[i * n + j] = { dist(p[i], q[j]), -2, -1 };

    // Setup root node
    G[0].parent = -1;
    G[0].depth  = 0;

    // Attach bottom row to root
    for (long long i = 1; i < m; ++i) attach(G, (i - 1) * n, i * n);

    // Attach left column to root
    for (long long j = 1; j < n; ++j) attach(G, j - 1, j);

    // Attach interior nodes to parent with lowest max-dist path to NCA
    for (long long i = 1; i < m; ++i) {
        for (long long j = 1; j < n; ++j) {
            long long A = (i - 1) * n + j;        // left
            long long B = (i - 1) * n + (j - 1);  // diagonal
            long long C = i * n + (j - 1);        // below

            // Select parent and attach it
            long long parent = select_parent(G, A, B, C);
            attach(G, parent, i * n + j);
        }
    }

    // Trace path from root to (m-1, n-1) to extract matching and max distance
    auto [ matching, max_distance ] = extract_matching(G, m, n);

    return { matching, max_distance };
}
