#include "bbms_dpp_instant.h"
#include "bbms_dpp_common.h"

namespace {

// Detach a dead path from the tree, removing all incoming shortcuts to the dead node and clearing the child flags of its parent.
void detach_dead_path(std::vector<Node>& G, long long B, long long dead_path_base, Direction final_direction) {
    // Remove all incoming shortcuts starting from B
    remove_from_incoming(G, G[B].out_high);
    remove_from_incoming(G, G[B].out_low);

    // Clear shortcuts and child flags of the dead path base node based on the final direction
    switch (final_direction) {
        case Direction::DOWN:
            G[dead_path_base].in_upper.clear();
            G[dead_path_base].child_upper = false;
            break;
        case Direction::DIAG_UPPER:
        case Direction::DIAG_LOWER:
            G[dead_path_base].in_diag_upper.clear();
            G[dead_path_base].in_diag_lower.clear();
            G[dead_path_base].child_diagonal = false;
            break;
        case Direction::LEFT:
            G[dead_path_base].in_right.clear();
            G[dead_path_base].child_right = false;
            break;
    }
}

} // namespace

MatchingAndFrechetDistance bbms_dpp_instant(const Curve& p, const Curve& q) {
    long long m = (long long) p.size(), n = (long long) q.size();

    // Initialize graph G with distances and unattached nodes
    std::vector<Node> G(m * n);
    for (long long i = 0; i < m; ++i)
        for (long long j = 0; j < n; ++j)
            G[i * n + j].distance = dist(p[i], q[j]);

    // Setup root node
    G[0].parent = -1;
    G[0].depth  = 0;

    // Attach bottom row to root
    for (long long i = 1; i < m; ++i) attach(G, (i-1)*n, i*n, n);

    // Attach left column to root
    for (long long j = 1; j < n; ++j) attach(G, j-1, j, n);

    std::deque<Shortcut> pool;

    // Attach interior nodes to parent with lowest max-dist path to NCA, while updating shortcuts and removing dead paths
    for (long long i = 1; i < m; ++i) {
        for (long long j = 1; j < n; ++j) {
            long long A = (i-1) * n + j;        // left
            long long B = (i-1) * n + (j - 1);  // diagonal
            long long C = i * n + (j - 1);      // below
            long long D = i * n + j;            // current

            // Select parent for D and get all NCA results needed for updating shortcuts
            SelectResult sr = select_parent(G, A, B, C, n);
            attach(G, sr.parent, D, n);

            // If B has no children, detach the dead path ending at B and extend shortcuts
            if (!has_children(G, B)) {
                // Get the dead path base
                Shortcut* deepest_shortcut  = get_deepest_shortcut(G, B);
                long long dead_path_base = deepest_shortcut->target;

                // Detach the dead path ending at B
                detach_dead_path(G, B, dead_path_base, deepest_shortcut->direction);

                // Extend shortcuts from the dead path base to the followup shortcut
                Shortcut* followup = extend_shortcuts(G, dead_path_base, deepest_shortcut->direction);

                // Change NCA info since NCAs may have changed due to the dead path removal
                adjust_ncas(sr, dead_path_base, followup);
            }

            // Update shortcuts on A, C, D after attaching D to its parent
            update_shortcuts(pool, G, A, B, C, D, sr);
        }
    }

    // Trace path from root to (m-1, n-1) to extract matching and max distance
    auto [ matching, frechet ] = extract_matching(G, m, n);

    return {matching, frechet};
}
