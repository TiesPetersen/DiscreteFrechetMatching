#include "bbms_dpp_instant_lean.h"
#include "bbms_dpp_lean_common.h"
#include "../parent_trace.h"

namespace {

// Free every shortcut in a list and empty the list. Only called for lists that hold
// shortcuts of dead nodes: those that enter the dead path base from the dead side.
void free_list_entries(ShortcutStore& pool, ShortcutId& list) {
    ShortcutId id = list;
    list = NONE;
    while (id != NONE) {
        ShortcutId next = pool[id].next;
        free_shortcut(pool, id);
        id = next;
    }
}

// Detach a dead path from the tree, removing all incoming shortcuts to the dead node and clearing the child flags of its parent.
void detach_dead_path(ShortcutStore& pool, std::vector<Node>& G, long long B, long long dead_path_base, Direction final_direction) {
    // Remove all incoming shortcuts starting from B
    remove_from_incoming(G, pool, G[B].out_high);
    remove_from_incoming(G, pool, G[B].out_low);

    // B is dead and its shortcuts are in no list now, so they can be reused
    free_shortcut(pool, G[B].out_high);
    free_shortcut(pool, G[B].out_low);
    G[B].out_high = G[B].out_low = NONE;

    // Clear shortcuts and child flags of the dead path base node based on the final direction
    switch (final_direction) {
        case Direction::DOWN:
            free_list_entries(pool, incoming(G[dead_path_base], Direction::DOWN));
            G[dead_path_base].child_upper = false;
            break;
        case Direction::DIAG_UPPER:
        case Direction::DIAG_LOWER:
            free_list_entries(pool, incoming(G[dead_path_base], Direction::DIAG_UPPER));
            free_list_entries(pool, incoming(G[dead_path_base], Direction::DIAG_LOWER));
            G[dead_path_base].child_diagonal = false;
            break;
        case Direction::LEFT:
            free_list_entries(pool, incoming(G[dead_path_base], Direction::LEFT));
            G[dead_path_base].child_right = false;
            break;
    }
}

} // namespace

MatchingAndFrechetDistance bbms_dpp_instant_lean(const Curve& p, const Curve& q) {
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
    for (long long i = 1; i < m; ++i) attach(G, (i-1)*n, i*n, n);

    // Attach left column to root
    for (long long j = 1; j < n; ++j) attach(G, j-1, j, n);

    ShortcutStore pool;

    // Attach interior nodes to parent with lowest max-dist path to NCA, while updating shortcuts and removing dead paths
    for (long long i = 1; i < m; ++i) {
        for (long long j = 1; j < n; ++j) {
            long long A = (i-1) * n + j;        // left
            long long B = (i-1) * n + (j - 1);  // diagonal
            long long C = i * n + (j - 1);      // below
            long long D = i * n + j;            // current

            // Select parent for D and attach it
            long long parent_D = select_parent(G, pool, A, B, C);
            attach(G, parent_D, D, n);
            TRACE_PARENT(parent_D);

            // If B has no children, detach the dead path ending at B and extend shortcuts
            if (!has_children(G, B)) {
                COUNT(dead_paths_pruned);
                COUNT(dead_path_walk_steps);  // a single O(1) jump to dead_path_base

                // Get the dead path base
                ShortcutId deepest_shortcut = get_deepest_shortcut(G, pool, B);
                long long dead_path_base = pool[deepest_shortcut].target;

                // Detach the dead path ending at B
                Direction final_direction = pool[deepest_shortcut].direction;
                detach_dead_path(pool, G, B, dead_path_base, final_direction);

                // Extend shortcuts from the dead path base to the followup shortcut
                extend_shortcuts(G, pool, dead_path_base, final_direction);
            }

            // Update shortcuts on A, C, D after attaching D to its parent
            update_shortcuts(pool, G, A, B, C, D, parent_D);
        }
    }

    // Trace path from root to (m-1, n-1) to extract matching and max distance
    auto [ matching, frechet ] = extract_matching(G, m, n);

    return {matching, frechet};
}
