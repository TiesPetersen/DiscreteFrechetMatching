#include "bbms_dpp_stepwise_lists.h"
#include "bbms_dpp_common_lists.h"
#include "../parent_trace.h"

namespace {

// Clear parent's child flag for child, based on their relative grid position (mirrors attach's logic).
void clear_child_flag(std::vector<Node>& G, long long parent, long long child, long long n) {
    long long child_i = child / n, child_j = child % n;
    long long parent_i = parent / n, parent_j = parent % n;
    if (child_i == parent_i && child_j == parent_j + 1) G[parent].child_upper = false;
    else if (child_i == parent_i + 1 && child_j == parent_j + 1) G[parent].child_diagonal = false;
    else G[parent].child_right = false;
}

} // namespace

MatchingAndFrechetDistance bbms_dpp_stepwise_lists(const Curve& p, const Curve& q) {
    long long m = (long long) p.size(), n = (long long) q.size();

    // Initialize graph G with distances and unattached nodes
    std::vector<Node> G(m * n);
    for (long long i = 0; i < m; ++i)
        for (long long j = 0; j < n; ++j) {
            G[i * n + j].distance = dist(p[i], q[j]);
        }

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

            //std::cout << " i = " << i << " ; j = " << j << std::endl;

            long long A = (i-1) * n + j;        // left
            long long B = (i-1) * n + (j - 1);  // diagonal
            long long C = i * n + (j - 1);      // below
            long long D = i * n + j;            // current

            // Select parent for D and get all NCA results needed for updating shortcuts
            SelectResult sr = select_parent(G, A, B, C, n);
            attach(G, sr.parent, D, n);
            TRACE_PARENT(sr.parent);

            // If B has no children, walk the dead path ending at B step by step and remove shortcuts, then extend appropriate shortcuts
            if (!has_children(G, B)) {
                COUNT(dead_paths_pruned);

                // Get the dead path base
                ShortcutHandle deepest_shortcut = get_deepest_shortcut(G, B);
                long long dead_path_base   = deepest_shortcut->target;
                Direction final_direction  = deepest_shortcut->direction;

                // Walk the tree path from B to dead_path_base, removing outgoing shortcuts at each step.
                long long X = B;
                while (X != dead_path_base) {
                    long long parent = G[X].parent;
                    remove_from_incoming(G, G[X].out_low);
                    remove_from_incoming(G, G[X].out_high);
                    clear_child_flag(G, parent, X, n);
                    X = parent;
                    COUNT(dead_path_walk_steps);
                }

                // Extend shortcuts from the dead path base to the followup shortcut
                OptionalShortcutHandle followup = extend_shortcuts(G, dead_path_base, final_direction);

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
