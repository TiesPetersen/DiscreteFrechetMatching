#pragma once
#include "common.h"
#include "../counters.h"
#include <algorithm>
#include <deque>

namespace {

// Enumeration of directions for shortcuts in the tree.
enum class Direction { DOWN, DIAG_UPPER, DIAG_LOWER, LEFT };

struct Shortcut {
    long long target;               // -1 = absent
    double value;                   // max distance to NCA
    Shortcut* next = nullptr;       // next shortcut in the same incoming list of the target, or in the free list
    Direction direction;            // direction of the shortcut
#ifdef LEAN_CHECKS
    long long owner = -1;           // checking build only: the node whose out_low or out_high this is
    bool is_free = false;           // checking build only: true while the shortcut is in the free list
#endif
};

// All shortcuts, plus a free list of dead shortcuts that can be handed out again.
// The free list runs through the next pointers, because a dead shortcut is in no incoming list.
struct ShortcutStore {
    std::deque<Shortcut> pool;      // a deque never moves its elements, so pointers stay valid
    Shortcut* free_list = nullptr;  // dead shortcuts, ready for reuse
};

// Checking build: stop at once if a freed shortcut is used, or a node reads a shortcut that is not its own
#ifdef LEAN_CHECKS
#include <cstdio>
#include <cstdlib>
#define LEAN_CHECK(condition, message) \
    do { if (!(condition)) { std::fprintf(stderr, "LEAN_CHECKS failed: %s (%s:%d)\n", message, __FILE__, __LINE__); std::abort(); } } while (0)
#define LEAN_CHECK_OUT(shortcut, node) \
    do { if ((shortcut) != nullptr) { LEAN_CHECK(!(shortcut)->is_free, "read a freed shortcut"); \
                                      LEAN_CHECK((shortcut)->owner == (node), "read a shortcut of another node"); } } while (0)
#else
#define LEAN_CHECK(condition, message) ((void) 0)
#define LEAN_CHECK_OUT(shortcut, node) ((void) 0)
#endif

// Lean layout: each incoming list is a linked list that runs through the shortcuts themselves.
// A node stores only the first shortcut of each of its four lists, indexed by Direction:
// DOWN = from upper children, DIAG_UPPER and DIAG_LOWER = from diagonal children, LEFT = from right children.
struct Node {
    double distance = 0.0;                  // squared distance from p[i] to q[j]
    long long parent = -2;                  // index of parent, -1 = root, -2 = no parent/unattached
    Shortcut* out_low = nullptr;            // shortcut to the nearest ancestor in the lower direction
    Shortcut* out_high = nullptr;           // shortcut to the nearest ancestor in the upper direction
    Shortcut* incoming[4] = {nullptr, nullptr, nullptr, nullptr};  // first shortcut of each incoming list
    int depth  = -1;                        // depth in the tree, root has depth 0
    bool child_upper = false;               // true if the node has a child in the upper direction
    bool child_diagonal = false;            // true if the node has a child in the diagonal direction
    bool child_right = false;               // true if the node has a child in the right direction
};

// The incoming list of a node for one direction.
Shortcut*& incoming(Node& node, Direction direction) {
    return node.incoming[static_cast<int>(direction)];
}

// Allocate a shortcut and return a pointer to it. A dead shortcut from the free list is reused
// first; only when the free list is empty does the pool grow.
Shortcut* allocate_shortcut(ShortcutStore& store, long long target, double value, Direction direction) {
    COUNT(shortcuts_written);
    Shortcut* shortcut;
    if (store.free_list != nullptr) {
        shortcut = store.free_list;
        store.free_list = shortcut->next;
        LEAN_CHECK(shortcut->is_free, "free list holds a shortcut that is in use");
    } else {
        store.pool.emplace_back();
        shortcut = &store.pool.back();
    }
    *shortcut = Shortcut{};
    shortcut->target = target;
    shortcut->value = value;
    shortcut->direction = direction;
    return shortcut;
}

// Give a dead shortcut back to the store. The caller makes sure nothing will read it again:
// it is in no incoming list, and its owner is dead.
void free_shortcut(ShortcutStore& store, Shortcut* shortcut) {
    if (shortcut == nullptr) return;
    LEAN_CHECK(!shortcut->is_free, "shortcut freed twice");
#ifdef LEAN_CHECKS
    shortcut->is_free = true;
#endif
    shortcut->next = store.free_list;
    store.free_list = shortcut;
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

// True if the max distance on u's side to NCA(u,v) is at most the max distance on v's side.
// The NCA's own distance is not included. Walks u and v up using shortcuts where available.
bool u_side_at_most_v_side(const std::vector<Node>& G, long long u, long long v) {
    double max_distance_u = -INF, max_distance_v = -INF;

    // Walk u and v up the tree until they meet at their NCA, using shortcuts where available
    while (u != v) {
        if (G[v].depth > G[u].depth) {
            // Walk v up the tree, using shortcuts if available
            LEAN_CHECK_OUT(G[v].out_high, v);
            if (G[v].out_high != nullptr) {
                max_distance_v = std::max(max_distance_v, G[v].out_high->value);
                v = G[v].out_high->target;
                COUNT(nca_shortcut_hops);
            } else {
                max_distance_v = std::max(max_distance_v, G[v].distance);
                v = G[v].parent;
                COUNT(nca_regular_hops);
            }
        } else {
            // Walk u up the tree, using shortcuts if available
            LEAN_CHECK_OUT(G[u].out_low, u);
            if (G[u].out_low != nullptr) {
                max_distance_u = std::max(max_distance_u, G[u].out_low->value);
                u = G[u].out_low->target;
                COUNT(nca_shortcut_hops);
            } else {
                max_distance_u = std::max(max_distance_u, G[u].distance);
                u = G[u].parent;
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

// Check if a node has any children.
bool has_children(const std::vector<Node>& G, long long index) {
    return G[index].child_upper || G[index].child_diagonal || G[index].child_right;
}

// Get the deepest shortcut from a node, if any.
Shortcut* get_deepest_shortcut(const std::vector<Node>& G, long long index) {
    Shortcut* best = nullptr;
    int max_depth = -1;

    // Check both the low and high shortcuts for the deepest one
    LEAN_CHECK_OUT(G[index].out_low, index);
    LEAN_CHECK_OUT(G[index].out_high, index);
    for (Shortcut* shortcut : { G[index].out_low, G[index].out_high }) {
        if (shortcut != nullptr && G[shortcut->target].depth > max_depth) {
            best = shortcut;
            max_depth = G[shortcut->target].depth;
        }
    }

    return best;
}

// Remove a shortcut from the incoming list of its target node.
// The newest shortcut is first in the list, and the one to remove is almost always the newest,
// so the search usually stops at the first entry. If the shortcut is not listed, nothing changes.
void remove_from_incoming(std::vector<Node>& G, Shortcut* shortcut) {
    if (shortcut == nullptr) return;
    LEAN_CHECK(!shortcut->is_free, "removing a freed shortcut");

    // Walk the list, keeping the link that points at the current entry
    Shortcut** link = &incoming(G[shortcut->target], shortcut->direction);
    while (*link != nullptr && *link != shortcut) { link = &(*link)->next; COUNT(list_search_steps); }
    if (*link != nullptr) COUNT(list_search_steps);

    // Unlink the shortcut if it was found
    if (*link == shortcut) {
        *link = shortcut->next;
        shortcut->next = nullptr;
    }
}

// Add a shortcut to the front of the incoming list of its target node.
void add_to_incoming(std::vector<Node>& G, Shortcut* shortcut) {
    LEAN_CHECK(!shortcut->is_free, "listing a freed shortcut");
    Shortcut*& first = incoming(G[shortcut->target], shortcut->direction);
    shortcut->next = first;
    first = shortcut;
}

// Add a shortcut from origin to target, either as a low or high shortcut.
void add_shortcut(ShortcutStore& pool, std::vector<Node>& G, long long origin, bool is_low, long long target, double value, Direction direction) {
    Shortcut* shortcut = allocate_shortcut(pool, target, value, direction);
#ifdef LEAN_CHECKS
    shortcut->owner = origin;
#endif

    // Set the shortcut in the origin node
    if (is_low) G[origin].out_low  = shortcut;
    else G[origin].out_high = shortcut;

    // Set the shortcut in the incoming list of the target node
    add_to_incoming(G, shortcut);
}

// Extend all incoming shortcuts to a node to point to a follow-up shortcut, updating their values and directions
void extend_shortcuts_to(std::vector<Node>& G, Shortcut*& list, Shortcut* followup_shortcut) {
    // Take the whole list off the node first; this clears it
    Shortcut* shortcut = list;
    list = nullptr;

    // Reverse it, so the oldest shortcut comes first. Adding them oldest first leaves the newest
    // at the front of the new list, in the same order as the vector version. A removal then finds
    // its shortcut after the same number of steps as before, which is one step in practice.
    Shortcut* reversed = nullptr;
    while (shortcut != nullptr) {
        Shortcut* next = shortcut->next;
        shortcut->next = reversed;
        reversed = shortcut;
        shortcut = next;
    }
    shortcut = reversed;

    // Redirect each shortcut and add it to the list of its new target
    LEAN_CHECK(followup_shortcut == nullptr || !followup_shortcut->is_free, "extending to a freed shortcut");
    while (shortcut != nullptr) {
        Shortcut* next = shortcut->next;
        LEAN_CHECK(!shortcut->is_free, "a freed shortcut is still listed");
        shortcut->value = std::max(shortcut->value, followup_shortcut->value);
        shortcut->direction = followup_shortcut->direction;
        shortcut->target = followup_shortcut->target;
        add_to_incoming(G, shortcut);
        COUNT(shortcuts_extended);
        shortcut = next;
    }
}

// Extend the shortcuts of a dead path base node to point to a new target, based on the final direction of the dead path.
Shortcut* extend_shortcuts(std::vector<Node>& G, long long dead_path_base, Direction final_direction) {
    LEAN_CHECK_OUT(G[dead_path_base].out_low, dead_path_base);
    LEAN_CHECK_OUT(G[dead_path_base].out_high, dead_path_base);
    if (final_direction == Direction::DOWN) {
        if (G[dead_path_base].child_diagonal)
            extend_shortcuts_to(G, incoming(G[dead_path_base], Direction::DIAG_UPPER), G[dead_path_base].out_high);
        else if (G[dead_path_base].child_right)
            extend_shortcuts_to(G, incoming(G[dead_path_base], Direction::LEFT), G[dead_path_base].out_high);
        return G[dead_path_base].out_high;
    } else if (final_direction == Direction::DIAG_UPPER || final_direction == Direction::DIAG_LOWER) {
        if (G[dead_path_base].child_right && !G[dead_path_base].child_upper) {
            extend_shortcuts_to(G, incoming(G[dead_path_base], Direction::LEFT), G[dead_path_base].out_high);
            return G[dead_path_base].out_high;
        } else if (G[dead_path_base].child_upper && !G[dead_path_base].child_right) {
            extend_shortcuts_to(G, incoming(G[dead_path_base], Direction::DOWN), G[dead_path_base].out_low);
            return G[dead_path_base].out_low;
        }
        return nullptr;
    } else {
        // final_direction == Direction::LEFT
        if (G[dead_path_base].child_diagonal)
            extend_shortcuts_to(G, incoming(G[dead_path_base], Direction::DIAG_LOWER), G[dead_path_base].out_low);
        else if (G[dead_path_base].child_upper)
            extend_shortcuts_to(G, incoming(G[dead_path_base], Direction::DOWN), G[dead_path_base].out_low);
        return G[dead_path_base].out_low;
    }
}

// Add a shortcut from origin that continues its parent's shortcut (low or high) one step further.
// It gets the same target and value a fresh NCA query would give, without the query.
void add_extending_shortcut(ShortcutStore& pool, std::vector<Node>& G, long long origin, bool is_low) {
    Shortcut* extend = is_low ? G[G[origin].parent].out_low : G[G[origin].parent].out_high;
    LEAN_CHECK_OUT(extend, G[origin].parent);
    add_shortcut(pool, G, origin, is_low, extend->target, std::max(G[origin].distance, extend->value), extend->direction);
}

// Update shortcuts on A, C, D after attaching D to its parent.
// A's and C's shortcuts are set before D's, because D's may extend them.
void update_shortcuts(ShortcutStore& pool, std::vector<Node>& G, long long A, long long B, long long C, long long D, long long parent_D) {
    bool AB = (G[A].parent == B);
    bool BC = (G[C].parent == B);

    if (parent_D == A) {
        if (AB && BC) {
            add_shortcut(pool, G, A, true, B, G[A].distance, Direction::DOWN);
            add_shortcut(pool, G, C, false, B, G[C].distance, Direction::LEFT);
            add_shortcut(pool, G, D, true, B, std::max(G[A].distance, G[D].distance), Direction::DOWN);
        } else if (AB) {
            add_extending_shortcut(pool, G, A, true);
            add_extending_shortcut(pool, G, D, true);
        } else if (BC) {
            add_extending_shortcut(pool, G, C, false);
            add_extending_shortcut(pool, G, D, true);
        } else {
            add_extending_shortcut(pool, G, D, true);
        }
    } else if (parent_D == B) {
        if (AB && BC) {
            add_shortcut(pool, G, A, true, B, G[A].distance, Direction::DOWN);
            add_shortcut(pool, G, C, false, B, G[C].distance, Direction::LEFT);
            add_shortcut(pool, G, D, false, B, G[D].distance, Direction::DIAG_UPPER);
            add_shortcut(pool, G, D, true, B, G[D].distance, Direction::DIAG_LOWER);
        } else if (AB) {
            add_shortcut(pool, G, A, true, B, G[A].distance, Direction::DOWN);
            add_shortcut(pool, G, D, false, B, G[D].distance, Direction::DIAG_UPPER);
            add_extending_shortcut(pool, G, D, true);
        } else if (BC) {
            add_shortcut(pool, G, C, false, B, G[C].distance, Direction::LEFT);
            add_extending_shortcut(pool, G, D, false);
            add_shortcut(pool, G, D, true, B, G[D].distance, Direction::DIAG_LOWER);
        } else {
            add_extending_shortcut(pool, G, D, false);
            add_extending_shortcut(pool, G, D, true);
        }
    } else { // parent_D == C
        if (AB && BC) {
            add_shortcut(pool, G, A, true, B, G[A].distance, Direction::DOWN);
            add_shortcut(pool, G, C, false, B, G[C].distance, Direction::LEFT);
            add_shortcut(pool, G, D, false, B, std::max(G[C].distance, G[D].distance), Direction::LEFT);
        } else if (AB) {
            add_extending_shortcut(pool, G, A, true);
            add_extending_shortcut(pool, G, D, false);
        } else if (BC) {
            add_extending_shortcut(pool, G, C, false);
            add_extending_shortcut(pool, G, D, false);
        } else {
            add_extending_shortcut(pool, G, D, false);
        }
    }
}

} // namespace
