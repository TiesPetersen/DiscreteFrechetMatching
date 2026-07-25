#pragma once
#include "common.h"
#include <algorithm>
#include <deque>

namespace {

// Enumeration of directions for shortcuts in the tree.
enum class Direction { DOWN, DIAG_UPPER, DIAG_LOWER, LEFT };

struct Shortcut {
    long long target;       // -1 = absent
    double value;           // max distance to NCA
    Direction direction;    // direction of the shortcut
};

struct Node {
    double distance = 0.0;                  // distance from p[i] to q[j]
    long long parent = -2;                  // index of parent, -1 = root, -2 = no parent/unattached
    int depth  = -1;                        // depth in the tree, root has depth 0
    bool child_upper = false;               // true if the node has a child in the upper direction
    bool child_diagonal = false;            // true if the node has a child in the diagonal direction
    bool child_right = false;               // true if the node has a child in the right direction
    Shortcut* out_low = nullptr;            // shortcut to the nearest ancestor in the lower direction
    Shortcut* out_high = nullptr;           // shortcut to the nearest ancestor in the upper direction
    std::vector<Shortcut*> in_upper;        // incoming shortcuts from upper children
    std::vector<Shortcut*> in_diag_upper;   // incoming shortcuts from diagonal-up children
    std::vector<Shortcut*> in_diag_lower;   // incoming shortcuts from diagonal-down children
    std::vector<Shortcut*> in_right;        // incoming shortcuts from right children
};

struct NCAResult {
    double max_distance_u;  // max distance on u's side to NCA(u,v)
    double max_distance_v;  // max distance on v's side to NCA(u,v)
    long long nca;          // index of nearest common ancestor of u and v
    Direction direction_u;  // direction of last step in the shortcut from u to NCA(u,v)
    Direction direction_v;  // direction of last step in the shortcut from v to NCA(u,v)
};

// All pairwise NCA results needed by update_shortcuts, including directions.
// e.g. max_A_AB = max dist on A's side to NCA(A,B); max_B_AB = max dist on B's side to NCA(A,B).
struct SelectResult {
    long long parent;
    double max_A_AB, max_B_AB; long long nca_AB; Direction dir_A_AB, dir_B_AB;
    double max_B_BC, max_C_BC; long long nca_BC; Direction dir_B_BC, dir_C_BC;
    double max_A_AC, max_C_AC; long long nca_AC; Direction dir_A_AC, dir_C_AC;
};

// Get direction of the step from child to parent in the tree.
// Diagonal steps always have shortcuts set, so get_direction is never called for them.
Direction get_direction(long long child, long long parent, long long n) {
    if (child == parent + n) return Direction::LEFT;
    return Direction::DOWN;
}

// Allocate a new shortcut from the pool and return a pointer to it.
// The pool is a deque, so pointers remain valid even if the deque is resized.
Shortcut* allocate_shortcut(std::deque<Shortcut>& pool, long long target, double value, Direction direction) {
    pool.push_back({target, value, direction});
    return &pool.back();
}

// Attach child to parent in G, updating child's depth, parent index and flags.
void attach(std::vector<Node>& G, long long parent, long long child, long long n) {
    // Set child's parent and depth
    G[child].parent = parent;
    G[child].depth  = G[parent].depth + 1;

    // Update parent's child flags based on the relative position of child to parent
    long long child_i = child / n, child_j = child % n;
    long long parent_i = parent / n, parent_j = parent % n;
    if (child_i == parent_i && child_j == parent_j + 1) G[parent].child_upper = true;
    else if (child_i == parent_i + 1 && child_j == parent_j + 1) G[parent].child_diagonal = true;
    else G[parent].child_right = true;
}

NCAResult max_dist_to_nca(const std::vector<Node>& G, long long u, long long v, long long n) {
    double max_distance_u = -INF, max_distance_v = -INF;
    Direction final_direction_u = Direction::DOWN, final_direction_v = Direction::DOWN;

    // Walk u and v up the tree until they meet at their NCA, using shortcuts where available
    while (u != v) {
        if (G[v].depth > G[u].depth) {
            // Walk v up the tree, using shortcuts if available
            if (G[v].out_high != nullptr) {
                max_distance_v = std::max(max_distance_v, G[v].out_high->value);
                final_direction_v = G[v].out_high->direction;
                v = G[v].out_high->target;
            } else {
                max_distance_v = std::max(max_distance_v, G[v].distance);
                final_direction_v = get_direction(v, G[v].parent, n);
                v = G[v].parent;
            }
        } else {
            // Walk u up the tree, using shortcuts if available
            if (G[u].out_low != nullptr) {
                max_distance_u = std::max(max_distance_u, G[u].out_low->value);
                final_direction_u = G[u].out_low->direction;
                u = G[u].out_low->target;
            } else {
                max_distance_u = std::max(max_distance_u, G[u].distance);
                final_direction_u = get_direction(u, G[u].parent, n);
                u = G[u].parent;
            }
        }
    }

    return {max_distance_u, max_distance_v, u, final_direction_u, final_direction_v};
}

// Select parent among A, B, C that has the lowest maximum distance to NCA.
// Break ties by preferring A > B > C.
SelectResult select_parent(const std::vector<Node>& G, long long A, long long B, long long C, long long n) {
    // Check pair A, B
    auto [max_A_AB, max_B_AB, nca_AB, dir_A_AB, dir_B_AB] = max_dist_to_nca(G, A, B, n);

    // Check pair B, C
    auto [max_B_BC, max_C_BC, nca_BC, dir_B_BC, dir_C_BC] = max_dist_to_nca(G, B, C, n);

    // Check pair A, C
    auto [max_A_AC, max_C_AC, nca_AC, dir_A_AC, dir_C_AC] = max_dist_to_nca(G, A, C, n);

    // Select parent with lowest maximum distance to NCA, breaking ties by A > B > C
    bool A_over_B = (max_A_AB <= max_B_AB);
    bool B_over_C = (max_B_BC <= max_C_BC);
    bool A_over_C = (max_A_AC <= max_C_AC);
    long long chosen;
    if (A_over_B && A_over_C) chosen = A;
    else if (!A_over_B && B_over_C) chosen = B;
    else chosen = C;

    return { chosen,
             max_A_AB, max_B_AB, nca_AB, dir_A_AB, dir_B_AB,
             max_B_BC, max_C_BC, nca_BC, dir_B_BC, dir_C_BC,
             max_A_AC, max_C_AC, nca_AC, dir_A_AC, dir_C_AC };
}

// Check if a node has any children.
bool has_children(const std::vector<Node>& G, long long index) {
    return G[index].child_upper || G[index].child_diagonal || G[index].child_right;
}

// Get the deepest shortcut from a node, if any.
Shortcut* get_deepest_shortcut(const std::vector<Node>& G, long long index) {
    Shortcut* best = nullptr;
    int max_depth = -1;

    // Check both the low and high shortcuts for the deepest one
    for (Shortcut* shortcut : { G[index].out_low, G[index].out_high }) {
        if (shortcut != nullptr && G[shortcut->target].depth > max_depth) {
            best = shortcut;
            max_depth = G[shortcut->target].depth;
        }
    }

    return best;
}

// Remove a shortcut from a list of shortcuts.
void remove_from(std::vector<Shortcut*>& list, Shortcut* shortcut) {
    auto it = std::find(list.begin(), list.end(), shortcut);
    if (it != list.end()) list.erase(it);
}

// Remove a shortcut from the incoming lists of its target node.
void remove_from_incoming(std::vector<Node>& G, Shortcut* shortcut) {
    if (shortcut == nullptr) return;

    long long target = shortcut->target;
    switch (shortcut->direction) {
        case Direction::DOWN:       remove_from(G[target].in_upper, shortcut);      break;
        case Direction::DIAG_UPPER: remove_from(G[target].in_diag_upper, shortcut); break;
        case Direction::DIAG_LOWER: remove_from(G[target].in_diag_lower, shortcut); break;
        case Direction::LEFT:       remove_from(G[target].in_right, shortcut);      break;
    }
}

// Add a shortcut to the incoming list of its target node.
void add_to_incoming(std::vector<Node>& G, Shortcut* shortcut) {
    long long target = shortcut->target;

    switch (shortcut->direction) {
        case Direction::DOWN:       G[target].in_upper.push_back(shortcut);      break;
        case Direction::DIAG_UPPER: G[target].in_diag_upper.push_back(shortcut); break;
        case Direction::DIAG_LOWER: G[target].in_diag_lower.push_back(shortcut); break;
        case Direction::LEFT:       G[target].in_right.push_back(shortcut);      break;
    }
}

// Add a shortcut from origin to target, either as a low or high shortcut.
void add_shortcut(std::deque<Shortcut>& pool, std::vector<Node>& G, long long origin, bool is_low, long long target, double value, Direction direction) {
    Shortcut* shortcut = allocate_shortcut(pool, target, value, direction);

    // Set the shortcut in the origin node
    if (is_low) G[origin].out_low  = shortcut;
    else G[origin].out_high = shortcut;

    // Set the shortcut in the incoming list of the target node
    add_to_incoming(G, shortcut);
}

// Extend all incoming shortcuts to a node to point to a follow-up shortcut, updating their values and directions.
void extend_shortcuts_to(std::vector<Node>& G, std::vector<Shortcut*>& list, Shortcut* followup_shortcut) {
    for (Shortcut* shortcut : list) {
        shortcut->value = std::max(shortcut->value, followup_shortcut->value);
        shortcut->direction = followup_shortcut->direction;
        shortcut->target = followup_shortcut->target;
        add_to_incoming(G, shortcut);
    }
}

// Extend the shortcuts of a dead path base node to point to a new target, based on the final direction of the dead path.
Shortcut* extend_shortcuts(std::vector<Node>& G, long long dead_path_base, Direction final_direction) {
    if (final_direction == Direction::DOWN) {
        if (G[dead_path_base].child_diagonal)
            extend_shortcuts_to(G, G[dead_path_base].in_diag_upper, G[dead_path_base].out_high);
        else if (G[dead_path_base].child_right)
            extend_shortcuts_to(G, G[dead_path_base].in_right, G[dead_path_base].out_high);
        return G[dead_path_base].out_high;
    } else if (final_direction == Direction::DIAG_UPPER || final_direction == Direction::DIAG_LOWER) {
        if (G[dead_path_base].child_right && !G[dead_path_base].child_upper) {
            extend_shortcuts_to(G, G[dead_path_base].in_right, G[dead_path_base].out_high);
            return G[dead_path_base].out_high;
        } else if (G[dead_path_base].child_upper && !G[dead_path_base].child_right) {
            extend_shortcuts_to(G, G[dead_path_base].in_upper, G[dead_path_base].out_low);
            return G[dead_path_base].out_low;
        }
        return nullptr;
    } else {
        // final_direction == Direction::LEFT
        if (G[dead_path_base].child_diagonal)
            extend_shortcuts_to(G, G[dead_path_base].in_diag_lower, G[dead_path_base].out_low);
        else if (G[dead_path_base].child_upper)
            extend_shortcuts_to(G, G[dead_path_base].in_upper, G[dead_path_base].out_low);
        return G[dead_path_base].out_low;
    }
}

// Adjust the NCA results in SelectResult if the dead path base node was one of the NCAs, updating it to point to the follow-up shortcut.
void adjust_ncas(SelectResult& select_results, long long dead_path_base, Shortcut* followup_shortcut) {
    if (followup_shortcut == nullptr) return;
    if (select_results.nca_AB == dead_path_base) {
        select_results.nca_AB   = followup_shortcut->target;
        select_results.max_A_AB = std::max(select_results.max_A_AB, followup_shortcut->value);
        select_results.max_B_AB = std::max(select_results.max_B_AB, followup_shortcut->value);
        select_results.dir_A_AB = followup_shortcut->direction;
        select_results.dir_B_AB = followup_shortcut->direction;
    }
    if (select_results.nca_BC == dead_path_base) {
        select_results.nca_BC   = followup_shortcut->target;
        select_results.max_B_BC = std::max(select_results.max_B_BC, followup_shortcut->value);
        select_results.max_C_BC = std::max(select_results.max_C_BC, followup_shortcut->value);
        select_results.dir_B_BC = followup_shortcut->direction;
        select_results.dir_C_BC = followup_shortcut->direction;
    }
    if (select_results.nca_AC == dead_path_base) {
        select_results.nca_AC   = followup_shortcut->target;
        select_results.max_A_AC = std::max(select_results.max_A_AC, followup_shortcut->value);
        select_results.max_C_AC = std::max(select_results.max_C_AC, followup_shortcut->value);
        select_results.dir_A_AC = followup_shortcut->direction;
        select_results.dir_C_AC = followup_shortcut->direction;
    }
}

// Update shortcuts on A, C, D after attaching D to its parent, based on the selected parent and NCA results.
void update_shortcuts(std::deque<Shortcut>& pool, std::vector<Node>& G, long long A, long long B, long long C, long long D, const SelectResult& select_results) {
    bool AB = (G[A].parent == B);
    bool BC = (G[C].parent == B);

    if (select_results.parent == A) {
        if (AB && BC) {
            add_shortcut(pool, G, A, true, B, G[A].distance, Direction::DOWN);
            add_shortcut(pool, G, C, false, B, G[C].distance, Direction::LEFT);
            add_shortcut(pool, G, D, true, B, std::max(G[A].distance, G[D].distance), Direction::DOWN);
        } else if (AB) {
            add_shortcut(pool, G, A, true, select_results.nca_AC, select_results.max_A_AC, select_results.dir_A_AC);
            add_shortcut(pool, G, D, true, select_results.nca_AC, std::max(select_results.max_A_AC, G[D].distance), select_results.dir_A_AC);
        } else if (BC) {
            add_shortcut(pool, G, C, false, select_results.nca_AC, select_results.max_C_AC, select_results.dir_C_AC);
            add_shortcut(pool, G, D, true, select_results.nca_AC, std::max(select_results.max_A_AC, G[D].distance), select_results.dir_A_AC);
        } else {
            add_shortcut(pool, G, D, true, select_results.nca_AB, std::max(select_results.max_A_AB, G[D].distance), select_results.dir_A_AB);
        }
    } else if (select_results.parent == B) {
        if (AB && BC) {
            add_shortcut(pool, G, A, true, B, G[A].distance, Direction::DOWN);
            add_shortcut(pool, G, C, false, B, G[C].distance, Direction::LEFT);
            add_shortcut(pool, G, D, false, B, G[D].distance, Direction::DIAG_UPPER);
            add_shortcut(pool, G, D, true, B, G[D].distance, Direction::DIAG_LOWER);
        } else if (AB) {
            add_shortcut(pool, G, A, true, B, G[A].distance, Direction::DOWN);
            add_shortcut(pool, G, D, false, B, G[D].distance, Direction::DIAG_UPPER);
            add_shortcut(pool, G, D, true, select_results.nca_AC, std::max(select_results.max_B_BC, G[D].distance), select_results.dir_B_BC);
        } else if (BC) {
            add_shortcut(pool, G, C, false, B, G[C].distance, Direction::LEFT);
            add_shortcut(pool, G, D, false, select_results.nca_AC, std::max(select_results.max_B_AB, G[D].distance), select_results.dir_B_AB);
            add_shortcut(pool, G, D, true, B, G[D].distance, Direction::DIAG_LOWER);
        } else {
            add_shortcut(pool, G, D, false, select_results.nca_AB, std::max(select_results.max_B_AB, G[D].distance), select_results.dir_B_AB);
            add_shortcut(pool, G, D, true, select_results.nca_BC, std::max(select_results.max_B_BC, G[D].distance), select_results.dir_B_BC);
        }
    } else { // select_results.parent == C
        if (AB && BC) {
            add_shortcut(pool, G, A, true, B, G[A].distance, Direction::DOWN);
            add_shortcut(pool, G, C, false, B, G[C].distance, Direction::LEFT);
            add_shortcut(pool, G, D, false, B, std::max(G[C].distance, G[D].distance), Direction::LEFT);
        } else if (AB) {
            add_shortcut(pool, G, A, true, select_results.nca_AC, select_results.max_A_AC, select_results.dir_A_AC);
            add_shortcut(pool, G, D, false, select_results.nca_AC, std::max(select_results.max_C_AC, G[D].distance), select_results.dir_C_AC);
        } else if (BC) {
            add_shortcut(pool, G, C, false, select_results.nca_AC, select_results.max_C_AC, select_results.dir_C_AC);
            add_shortcut(pool, G, D, false, select_results.nca_AC, std::max(select_results.max_C_AC, G[D].distance), select_results.dir_C_AC);
        } else {
            add_shortcut(pool, G, D, false, select_results.nca_BC, std::max(select_results.max_C_BC, G[D].distance), select_results.dir_C_BC);
        }
    }
}

} // namespace
