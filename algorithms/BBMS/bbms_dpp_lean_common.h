#pragma once
#include "common.h"
#include "../counters.h"
#include <algorithm>
#include <cstdint>
#include <memory>
#include <stdexcept>
#include <vector>

namespace {

// Enumeration of directions for shortcuts in the tree. One byte is enough.
enum class Direction : unsigned char { DOWN, DIAG_UPPER, DIAG_LOWER, LEFT };

// Lean layout: shortcuts are referred to by their 32-bit position in the shortcut store, not by
// an 8-byte pointer. NONE marks "no shortcut". The store checks that it never runs out of positions.
using ShortcutId = std::uint32_t;
constexpr ShortcutId NONE = UINT32_MAX;

struct Shortcut {
    long long target;               // -1 = absent
    double value;                   // max distance to NCA
    ShortcutId next = NONE;         // next shortcut in the same incoming list of the target, or in the free list
    Direction direction;            // direction of the shortcut
#ifdef LEAN_CHECKS
    long long owner = -1;           // checking build only: the node whose out_low or out_high this is
    bool is_free = false;           // checking build only: true while the shortcut is in the free list
#endif
};

// Each incoming list is a linked list that runs through the shortcuts themselves.
// A node stores only the first shortcut of each of its four lists, indexed by Direction:
// DOWN = from upper children, DIAG_UPPER and DIAG_LOWER = from diagonal children, LEFT = from right children.
struct Node {
    double distance = 0.0;                  // squared distance from p[i] to q[j]
    long long parent = -2;                  // index of parent, -1 = root, -2 = no parent/unattached
    ShortcutId out_low = NONE;              // shortcut to the nearest ancestor in the lower direction
    ShortcutId out_high = NONE;             // shortcut to the nearest ancestor in the upper direction
    ShortcutId incoming[4] = {NONE, NONE, NONE, NONE};  // first shortcut of each incoming list
    int depth  = -1;                        // depth in the tree, root has depth 0
    bool child_upper = false;               // true if the node has a child in the upper direction
    bool child_diagonal = false;            // true if the node has a child in the diagonal direction
    bool child_right = false;               // true if the node has a child in the right direction
};

// The lean sizes, checked when compiling (the checking build adds fields, so it is excluded)
#ifndef LEAN_CHECKS
static_assert(sizeof(Shortcut) == 24, "a lean shortcut should take 24 bytes");
static_assert(sizeof(Node) == 48, "a lean node should take 48 bytes");
#endif

// Shortcuts per block, as a power of two: 2^16 = 65,536 shortcuts (1.5 MB) per block.
// The equivalence test sets it much smaller, so it crosses block boundaries all the time.
#ifndef LEAN_BLOCK_BITS
#define LEAN_BLOCK_BITS 16
#endif

// All shortcuts, kept in fixed-size blocks so a shortcut never moves once it exists, plus a free
// list of dead shortcuts that can be handed out again. The free list runs through the next fields,
// because a dead shortcut is in no incoming list.
class ShortcutStore {
public:
    Shortcut& operator[](ShortcutId id) { return blocks[id >> BLOCK_BITS][id & BLOCK_MASK]; }
    const Shortcut& operator[](ShortcutId id) const { return blocks[id >> BLOCK_BITS][id & BLOCK_MASK]; }

    // Hand out a shortcut: a dead one from the free list first, otherwise a new slot
    ShortcutId allocate() {
        if (free_list != NONE) {
            ShortcutId id = free_list;
            free_list = (*this)[id].next;
            return id;
        }

        // A new slot; stop with an error rather than ever wrapping around the 32-bit positions
        if (size == NONE) throw std::length_error("shortcut store full: more than 2^32 - 1 live shortcuts");
        if ((size & BLOCK_MASK) == 0) blocks.emplace_back(new Shortcut[BLOCK_SIZE]);
        return size++;
    }

    // Put a dead shortcut on the free list
    void release(ShortcutId id) {
        (*this)[id].next = free_list;
        free_list = id;
    }

private:
    static constexpr int BLOCK_BITS = LEAN_BLOCK_BITS;
    static constexpr ShortcutId BLOCK_SIZE = ShortcutId(1) << BLOCK_BITS;
    static constexpr ShortcutId BLOCK_MASK = BLOCK_SIZE - 1;

    std::vector<std::unique_ptr<Shortcut[]>> blocks;   // block k holds positions k * BLOCK_SIZE onwards
    ShortcutId size = 0;                               // positions handed out so far
    ShortcutId free_list = NONE;                       // dead shortcuts, ready for reuse
};

// Checking build: stop at once if a freed shortcut is used, or a node reads a shortcut that is not its own
#ifdef LEAN_CHECKS
#include <cstdio>
#include <cstdlib>
#define LEAN_CHECK(condition, message) \
    do { if (!(condition)) { std::fprintf(stderr, "LEAN_CHECKS failed: %s (%s:%d)\n", message, __FILE__, __LINE__); std::abort(); } } while (0)
#define LEAN_CHECK_OUT(pool, id, node) \
    do { if ((id) != NONE) { LEAN_CHECK(!(pool)[id].is_free, "read a freed shortcut"); \
                             LEAN_CHECK((pool)[id].owner == (node), "read a shortcut of another node"); } } while (0)
#else
#define LEAN_CHECK(condition, message) ((void) 0)
#define LEAN_CHECK_OUT(pool, id, node) ((void) 0)
#endif

// The incoming list of a node for one direction.
ShortcutId& incoming(Node& node, Direction direction) {
    return node.incoming[static_cast<int>(direction)];
}

// Allocate a shortcut and return its position. A dead shortcut from the free list is reused
// first; only when the free list is empty does the store grow.
ShortcutId allocate_shortcut(ShortcutStore& pool, long long target, double value, Direction direction) {
    COUNT(shortcuts_written);
    ShortcutId id = pool.allocate();
    LEAN_CHECK(pool[id].is_free || pool[id].owner == -1, "free list holds a shortcut that is in use");
    pool[id] = Shortcut{};
    pool[id].target = target;
    pool[id].value = value;
    pool[id].direction = direction;
    return id;
}

// Give a dead shortcut back to the store. The caller makes sure nothing will read it again:
// it is in no incoming list, and its owner is dead.
void free_shortcut(ShortcutStore& pool, ShortcutId id) {
    if (id == NONE) return;
    LEAN_CHECK(!pool[id].is_free, "shortcut freed twice");
#ifdef LEAN_CHECKS
    pool[id].is_free = true;
#endif
    pool.release(id);
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
bool u_side_at_most_v_side(const std::vector<Node>& G, const ShortcutStore& pool, long long u, long long v) {
    double max_distance_u = -INF, max_distance_v = -INF;

    // Walk u and v up the tree until they meet at their NCA, using shortcuts where available
    while (u != v) {
        if (G[v].depth > G[u].depth) {
            // Walk v up the tree, using shortcuts if available
            LEAN_CHECK_OUT(pool, G[v].out_high, v);
            if (G[v].out_high != NONE) {
                const Shortcut& shortcut = pool[G[v].out_high];
                max_distance_v = std::max(max_distance_v, shortcut.value);
                v = shortcut.target;
                COUNT(nca_shortcut_hops);
            } else {
                max_distance_v = std::max(max_distance_v, G[v].distance);
                v = G[v].parent;
                COUNT(nca_regular_hops);
            }
        } else {
            // Walk u up the tree, using shortcuts if available
            LEAN_CHECK_OUT(pool, G[u].out_low, u);
            if (G[u].out_low != NONE) {
                const Shortcut& shortcut = pool[G[u].out_low];
                max_distance_u = std::max(max_distance_u, shortcut.value);
                u = shortcut.target;
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
long long select_parent(const std::vector<Node>& G, const ShortcutStore& pool, long long A, long long B, long long C) {
    if (u_side_at_most_v_side(G, pool, A, B)) return u_side_at_most_v_side(G, pool, A, C) ? A : C;
    return u_side_at_most_v_side(G, pool, B, C) ? B : C;
}

// Check if a node has any children.
bool has_children(const std::vector<Node>& G, long long index) {
    return G[index].child_upper || G[index].child_diagonal || G[index].child_right;
}

// Get the deepest shortcut from a node, if any.
ShortcutId get_deepest_shortcut(const std::vector<Node>& G, const ShortcutStore& pool, long long index) {
    ShortcutId best = NONE;
    int max_depth = -1;

    // Check both the low and high shortcuts for the deepest one
    LEAN_CHECK_OUT(pool, G[index].out_low, index);
    LEAN_CHECK_OUT(pool, G[index].out_high, index);
    for (ShortcutId id : { G[index].out_low, G[index].out_high }) {
        if (id != NONE && G[pool[id].target].depth > max_depth) {
            best = id;
            max_depth = G[pool[id].target].depth;
        }
    }

    return best;
}

// Remove a shortcut from the incoming list of its target node.
// The newest shortcut is first in the list, and the one to remove is almost always the newest,
// so the search usually stops at the first entry. If the shortcut is not listed, nothing changes.
void remove_from_incoming(std::vector<Node>& G, ShortcutStore& pool, ShortcutId id) {
    if (id == NONE) return;
    LEAN_CHECK(!pool[id].is_free, "removing a freed shortcut");

    // Walk the list, keeping the link that holds the current entry
    ShortcutId* link = &incoming(G[pool[id].target], pool[id].direction);
    while (*link != NONE && *link != id) { link = &pool[*link].next; COUNT(list_search_steps); }
    if (*link != NONE) COUNT(list_search_steps);

    // Unlink the shortcut if it was found
    if (*link == id) {
        *link = pool[id].next;
        pool[id].next = NONE;
    }
}

// Add a shortcut to the front of the incoming list of its target node.
void add_to_incoming(std::vector<Node>& G, ShortcutStore& pool, ShortcutId id) {
    LEAN_CHECK(!pool[id].is_free, "listing a freed shortcut");
    ShortcutId& first = incoming(G[pool[id].target], pool[id].direction);
    pool[id].next = first;
    first = id;
}

// Add a shortcut from origin to target, either as a low or high shortcut.
void add_shortcut(ShortcutStore& pool, std::vector<Node>& G, long long origin, bool is_low, long long target, double value, Direction direction) {
    ShortcutId id = allocate_shortcut(pool, target, value, direction);
#ifdef LEAN_CHECKS
    pool[id].owner = origin;
#endif

    // Set the shortcut in the origin node
    if (is_low) G[origin].out_low  = id;
    else G[origin].out_high = id;

    // Set the shortcut in the incoming list of the target node
    add_to_incoming(G, pool, id);
}

// Extend all incoming shortcuts to a node to point to a follow-up shortcut, updating their values and directions
void extend_shortcuts_to(std::vector<Node>& G, ShortcutStore& pool, ShortcutId& list, ShortcutId followup) {
    // Take the whole list off the node first; this clears it
    ShortcutId id = list;
    list = NONE;

    // Reverse it, so the oldest shortcut comes first. Adding them oldest first leaves the newest
    // at the front of the new list, in the same order as the vector version. A removal then finds
    // its shortcut after the same number of steps as before, which is one step in practice.
    ShortcutId reversed = NONE;
    while (id != NONE) {
        ShortcutId next = pool[id].next;
        pool[id].next = reversed;
        reversed = id;
        id = next;
    }
    id = reversed;

    // Redirect each shortcut and add it to the list of its new target
    LEAN_CHECK(id == NONE || followup != NONE, "extending to a missing shortcut");
    LEAN_CHECK(followup == NONE || !pool[followup].is_free, "extending to a freed shortcut");
    while (id != NONE) {
        ShortcutId next = pool[id].next;
        LEAN_CHECK(!pool[id].is_free, "a freed shortcut is still listed");
        pool[id].value = std::max(pool[id].value, pool[followup].value);
        pool[id].direction = pool[followup].direction;
        pool[id].target = pool[followup].target;
        add_to_incoming(G, pool, id);
        COUNT(shortcuts_extended);
        id = next;
    }
}

// Extend the shortcuts of a dead path base node to point to a new target, based on the final direction of the dead path.
ShortcutId extend_shortcuts(std::vector<Node>& G, ShortcutStore& pool, long long dead_path_base, Direction final_direction) {
    LEAN_CHECK_OUT(pool, G[dead_path_base].out_low, dead_path_base);
    LEAN_CHECK_OUT(pool, G[dead_path_base].out_high, dead_path_base);
    if (final_direction == Direction::DOWN) {
        if (G[dead_path_base].child_diagonal)
            extend_shortcuts_to(G, pool, incoming(G[dead_path_base], Direction::DIAG_UPPER), G[dead_path_base].out_high);
        else if (G[dead_path_base].child_right)
            extend_shortcuts_to(G, pool, incoming(G[dead_path_base], Direction::LEFT), G[dead_path_base].out_high);
        return G[dead_path_base].out_high;
    } else if (final_direction == Direction::DIAG_UPPER || final_direction == Direction::DIAG_LOWER) {
        if (G[dead_path_base].child_right && !G[dead_path_base].child_upper) {
            extend_shortcuts_to(G, pool, incoming(G[dead_path_base], Direction::LEFT), G[dead_path_base].out_high);
            return G[dead_path_base].out_high;
        } else if (G[dead_path_base].child_upper && !G[dead_path_base].child_right) {
            extend_shortcuts_to(G, pool, incoming(G[dead_path_base], Direction::DOWN), G[dead_path_base].out_low);
            return G[dead_path_base].out_low;
        }
        return NONE;
    } else {
        // final_direction == Direction::LEFT
        if (G[dead_path_base].child_diagonal)
            extend_shortcuts_to(G, pool, incoming(G[dead_path_base], Direction::DIAG_LOWER), G[dead_path_base].out_low);
        else if (G[dead_path_base].child_upper)
            extend_shortcuts_to(G, pool, incoming(G[dead_path_base], Direction::DOWN), G[dead_path_base].out_low);
        return G[dead_path_base].out_low;
    }
}

// Add a shortcut from origin that continues its parent's shortcut (low or high) one step further.
// It gets the same target and value a fresh NCA query would give, without the query.
void add_extending_shortcut(ShortcutStore& pool, std::vector<Node>& G, long long origin, bool is_low) {
    ShortcutId extend = is_low ? G[G[origin].parent].out_low : G[G[origin].parent].out_high;
    LEAN_CHECK_OUT(pool, extend, G[origin].parent);
    LEAN_CHECK(extend != NONE, "parent has no shortcut to extend");
    Shortcut parent_shortcut = pool[extend];
    add_shortcut(pool, G, origin, is_low, parent_shortcut.target, std::max(G[origin].distance, parent_shortcut.value), parent_shortcut.direction);
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
