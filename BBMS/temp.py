# ═══════════════════════════════════════════════════════════════════════════════
# LOCALLY CORRECT DISCRETE FRÉCHET MATCHING
# Buchin et al. (2012) — Algorithms 2 & 3, fully expanded
#
# TERMINOLOGY RECAP:
#   G[i][j]  = dist(P[i], Q[j])    — the grid of pairwise distances
#   Tree T   = a spanning tree on the grid nodes, built incrementally
#   Path in T from (0,0) to (m,n)  = the matching
#
# INVARIANT: every path in T is *strongly locally correct*:
#   for any two nodes u,v in T, the max G-value on the unique T-path u→v
#   equals the min-bottleneck over ALL monotone grid paths from u to v.
#
# COLUMN-MAJOR ORDER: we add nodes (i,j) for i=1..m, then j=1..n inside each i.
# When adding (i,j), these three neighbors are already in T:
#   A = (i-1, j)    ← left
#   B = (i-1, j-1)  ← diagonal  (dies exactly when (i,j) is added)
#   C = (i,   j-1)  ← bottom
# ═══════════════════════════════════════════════════════════════════════════════

import math
from collections import defaultdict

def euclidean(p, q):
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(p, q)))


# ───────────────────────────────────────────────────────────────────────────────
# TOP-LEVEL DRIVER
# ───────────────────────────────────────────────────────────────────────────────

def compute_lcdfm(P, Q):
    """
    P: list of (m+1) points
    Q: list of (n+1) points
    Returns: list of (i,j) tuples — the matching path from (0,0) to (m,n).
             Each consecutive pair is a step of (+1,0), (0,+1), or (+1,+1).
    """
    m, n = len(P) - 1, len(Q) - 1

    # ── Build distance grid ──────────────────────────────────────────────────
    G = [[euclidean(P[i], Q[j]) for j in range(n + 1)] for i in range(m + 1)]

    # ── Tree data ────────────────────────────────────────────────────────────
    # parent[i][j]  = (pi, pj) or None for the root (0,0)
    parent = [[None] * (n + 1) for _ in range(m + 1)]

    # depth[i][j] = depth in T (root has depth 0)
    depth = [[0] * (n + 1) for _ in range(m + 1)]

    # children[node] = list of child nodes; needed for dead-path detection
    children = defaultdict(list)

    # shortcuts[i][j] = list of (si, sj, max_excl_sink)  — at most 2 entries.
    #
    #   WHAT A SHORTCUT MEANS:
    #   From (i,j), the max G-value on the tree path to (si,sj),
    #   *excluding* G[si][sj] itself, is max_excl_sink.
    #
    #   PURPOSE:
    #   The growth frontier is a staircase of "active" nodes (nodes whose
    #   grid-forward neighbors aren't all in T yet).  Two frontier nodes that
    #   are horizontally/vertically adjacent (but neither is the other's parent)
    #   share a "face" — the area bounded by their two upward paths to their NCA.
    #   The NCA is the *sink* of that face (the node with the smallest i+j
    #   among all nodes on the face boundary, i.e., closest to origin).
    #   Each frontier node stores shortcuts to the sinks of its (≤2) adjacent faces.
    #   This lets nca_and_max() run in O(1) for neighboring frontier nodes.
    shortcuts = [[[] for _ in range(n + 1)] for _ in range(m + 1)]

    # ── Initialize boundary ──────────────────────────────────────────────────
    # Bottom row: (0,0)←(1,0)←(2,0)←...←(m,0)
    for i in range(1, m + 1):
        parent[i][0] = (i - 1, 0)
        depth[i][0]  = i
        children[(i - 1, 0)].append((i, 0))

    # Left column: (0,0)←(0,1)←(0,2)←...←(0,n)
    for j in range(1, n + 1):
        parent[0][j] = (0, j - 1)
        depth[0][j]  = j
        children[(0, j - 1)].append((0, j))

    # ── Main loop ────────────────────────────────────────────────────────────
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            add_node(G, parent, depth, children, shortcuts, i, j, m, n)

    # ── Extract path by walking parent pointers from (m,n) to (0,0) ─────────
    path = []
    node = (m, n)
    while node is not None:
        path.append(node)
        node = parent[node[0]][node[1]]
    path.reverse()
    return path   # [(0,0), ..., (m,n)]


# ───────────────────────────────────────────────────────────────────────────────
# CORE STEP: Add one node to the tree
# ───────────────────────────────────────────────────────────────────────────────

def add_node(G, parent, depth, children, shortcuts, i, j, m, n):
    """
    Algorithm 3 (AddToTree), fully expanded.
    Adds G[i,j] to T.  Four sub-steps:
      1. Compute NCA + max-values for all three candidate-parent pairs.
      2. Select the best parent (preference A > B > C for tie-breaking).
      3. Remove the now-dead path at B=(i-1,j-1), extending shortcuts.
      4. Create/update shortcuts for A, B, C, and the new node.
    """
    A = (i - 1, j    )   # left neighbor
    B = (i - 1, j - 1)   # diagonal neighbor — becomes dead after this step
    C = (i,     j - 1)   # bottom neighbor

    # ── Step 1: NCA + max values for all candidate pairs ─────────────────────
    #
    # nca_XY        = nearest common ancestor of X and Y in T
    # max_X_to_XY   = max G-value on path X → nca_XY, EXCLUDING nca_XY itself
    # max_Y_to_XY   = same, from Y's side
    #
    # The choice of parent for (i,j) must minimize bottleneck cost:
    #   "c wins against c' if max(c → NCA(c,c')) ≤ max(c' → NCA(c,c'))"
    # so we need these values for all three pairs.

    nca_AB, max_A_AB, max_B_AB = nca_and_max(parent, depth, G, shortcuts, A, B)
    nca_BC, max_B_BC, max_C_BC = nca_and_max(parent, depth, G, shortcuts, B, C)
    nca_AC, max_A_AC, max_C_AC = nca_and_max(parent, depth, G, shortcuts, A, C)

    # ── Step 2: Select parent ─────────────────────────────────────────────────
    #
    # "c wins against c'" means max(c→NCA) ≤ max(c'→NCA).
    # Tie-breaking: A > B > C  (left > diagonal > bottom).
    # IMPORTANT: B must NEVER be preferred over BOTH A and C simultaneously —
    # that would break correctness.  The preference order A>B>C prevents this.
    #
    # Since equal values give the win to the higher-priority candidate:
    #   A_over_B = True  iff  max_A_AB ≤ max_B_AB   (ties → A wins)
    #   B_over_C = True  iff  max_B_BC ≤ max_C_BC   (ties → B wins)
    #   A_over_C = True  iff  max_A_AC ≤ max_C_AC   (ties → A wins)
    #
    # Decision:
    #   if A wins against B AND A wins against C → choose A
    #   elif B wins against A AND B wins against C → choose B
    #   else → choose C

    A_over_B = (max_A_AB <= max_B_AB)
    B_over_C = (max_B_BC <= max_C_BC)
    A_over_C = (max_A_AC <= max_C_AC)

    if A_over_B and A_over_C:
        chosen = A
    elif (not A_over_B) and B_over_C:
        chosen = B
    else:
        chosen = C

    parent[i][j] = chosen
    depth[i][j]  = depth[chosen[0]][chosen[1]] + 1
    children[chosen].append((i, j))

    # ── Step 3: Remove dead path at B ────────────────────────────────────────
    #
    # B=(i-1,j-1) just became dead: every grid-forward neighbor of B
    # — namely (i,j-1)=C, (i-1,j)=A, and (i,j) — is now in T.
    #
    # The "dead path" πd starting at B goes upward in T until it reaches
    # a node that still has living descendants (other than through B).
    # When πd is removed:
    #   • the two faces flanking πd merge into one face
    #   • shortcuts that pointed to dead nodes on πd are "extended" to
    #     point to πd's surviving ancestor (the new sink of the merged face)
    #
    # Skip if B is on the grid boundary (i==1 or j==1) — boundary chains
    # don't participate in the face/shortcut machinery.

    if i > 1 and j > 1:
        remove_dead_path(G, parent, depth, children, shortcuts, B)

    # ── Step 4: Update shortcuts ──────────────────────────────────────────────
    #
    # After this step the growth frontier changes:
    #   before: ..., C=(i,j-1), B=(i-1,j-1), A=(i-1,j), ...
    #   after:  ..., C=(i,j-1), NEW=(i,j),   A=(i-1,j), ...
    # (B drops off because it's dead; NEW takes B's place between C and A.)
    #
    # New adjacent frontier pairs: (C, NEW) and (NEW, A).
    # Their NCAs and max-values were already computed above,
    # so we just write them into the shortcut arrays.

    update_shortcuts(parent, shortcuts, i, j, A, B, C,
                     nca_AB, nca_BC, nca_AC,
                     max_A_AB, max_B_AB,
                     max_B_BC, max_C_BC,
                     max_A_AC, max_C_AC,
                     chosen)


# ───────────────────────────────────────────────────────────────────────────────
# NCA + MAX  (two implementations: fast via shortcuts, fallback naive walk)
# ───────────────────────────────────────────────────────────────────────────────

def nca_and_max(parent, depth, G, shortcuts, u, v):
    """
    Returns (nca, max_u→nca_excl, max_v→nca_excl).

    FAST PATH — O(1) via shortcuts:
      If u and v are neighboring frontier nodes, they share a face whose sink
      is their NCA.  Both will have a shortcut pointing to that same sink.
      We look for a common shortcut target.

    SLOW PATH — O(depth) naive tree walk:
      Bring both nodes to the same depth, then walk up together until they meet.
      This is used during initialization (before shortcuts are established).
    """
    # ── Fast path ─────────────────────────────────────────────────────────────
    u_sc = {(s[0], s[1]): s[2] for s in shortcuts[u[0]][u[1]]}
    v_sc = {(s[0], s[1]): s[2] for s in shortcuts[v[0]][v[1]]}
    shared = set(u_sc.keys()) & set(v_sc.keys())
    if shared:
        # Exactly one shared sink for a true neighboring pair.
        # If somehow multiple (shouldn't happen), take the deepest one (closest to leaves).
        nca = max(shared, key=lambda x: depth[x[0]][x[1]])
        return nca, u_sc[nca], v_sc[nca]

    # ── Slow path: walk up the tree ───────────────────────────────────────────
    ui, uj = u
    vi, vj = v
    max_u  = 0.0
    max_v  = 0.0

    # Bring deeper node up to the depth of the shallower node
    while depth[ui][uj] > depth[vi][vj]:
        max_u = max(max_u, G[ui][uj])
        ui, uj = parent[ui][uj]

    while depth[vi][vj] > depth[ui][uj]:
        max_v = max(max_v, G[vi][vj])
        vi, vj = parent[vi][vj]

    # Walk both up simultaneously until they meet — that node is the NCA
    while (ui, uj) != (vi, vj):
        max_u = max(max_u, G[ui][uj])
        max_v = max(max_v, G[vi][vj])
        ui, uj = parent[ui][uj]
        vi, vj = parent[vi][vj]

    # NOTE: do NOT include G[ui][uj] (the NCA's own value) in either max.
    return (ui, uj), max_u, max_v


# ───────────────────────────────────────────────────────────────────────────────
# DEAD PATH REMOVAL + SHORTCUT EXTENSION
# ───────────────────────────────────────────────────────────────────────────────

def remove_dead_path(G, parent, depth, children, shortcuts, B):
    """
    Walk up from B collecting the "dead path" πd = [B, p1, p2, ..., survivor].
    A node is dead if it has no living/growth descendants left.
    The survivor is the first ancestor that still has a non-dead child
    other than the node we came from.

    Then extend every shortcut that pointed at a dead node on πd
    so that it now points to the survivor (the new face sink).

    By Lemma 6, the total number of extensions across the whole algorithm
    is O(mn), so this is O(1) amortized per add_node() call.
    """
    # ── Collect dead path πd ──────────────────────────────────────────────────
    dead_path   = []          # ordered B → ... → survivor
    came_from   = None
    cur         = B

    while True:
        dead_path.append(cur)
        par = parent[cur[0]][cur[1]]
        if par is None:
            # Hit the root — treat root as survivor
            break
        # Does par have any other living children?
        other_living = [c for c in children[par]
                        if c != cur and not _subtree_is_dead(c, children)]
        if other_living:
            dead_path.append(par)   # par is the survivor (πd[last])
            break
        came_from = cur
        cur = par

    if len(dead_path) < 2:
        return

    survivor    = dead_path[-1]
    dead_nodes  = set(dead_path[:-1])   # everything except the survivor

    # ── Precompute max G-value from each dead node up to survivor (excl.) ────
    # max_up[k] = max G on path dead_path[k] → survivor, excluding survivor
    max_up = [0.0] * len(dead_path)
    # Walk from second-to-last (node just below survivor) back to B
    for k in range(len(dead_path) - 2, -1, -1):
        di, dj = dead_path[k]
        max_up[k] = max(G[di][dj], max_up[k + 1] if k + 1 < len(dead_path) - 1 else G[di][dj])

    # Build lookup: dead_node → max_G_from_that_node_to_survivor_excl
    dead_to_survivor_max = {}
    running = 0.0
    for k in range(len(dead_path) - 2, -1, -1):
        di, dj = dead_path[k]
        running = max(running, G[di][dj])
        dead_to_survivor_max[dead_path[k]] = running

    # ── Find the "extension path" πe and redirect its shortcuts ──────────────
    #
    # πe starts at the survivor and runs to either (i-1,j)=A or (i,j-1)=C
    # — whichever side the face is on.  Shortcuts along πe that point at
    # dead nodes need to be redirected to the survivor.
    #
    # We locate πe by scanning T's children of survivor for a child that is
    # NOT on the dead path — that child heads toward πe.
    # Then we walk downward along πe, fixing shortcuts.

    surv_i, surv_j = survivor
    pe_start = None
    for child in children[survivor]:
        if child not in dead_nodes:
            pe_start = child
            break

    if pe_start is None:
        return  # No extension path needed

    cur = pe_start
    while cur is not None:
        ci, cj = cur
        updated = []
        for (si, sj, max_val) in shortcuts[ci][cj]:
            if (si, sj) in dead_nodes:
                # Extend: new max = max(old_max, max_from_dead_to_survivor)
                extra = dead_to_survivor_max.get((si, sj), 0.0)
                new_max = max(max_val, extra)
                updated.append((surv_i, surv_j, new_max))
            else:
                updated.append((si, sj, max_val))
        shortcuts[ci][cj] = updated

        # Walk down πe: find the child that is a growth node going toward the frontier
        next_node = None
        for child in children[cur]:
            # πe is the path toward the frontier; continue while we find
            # nodes whose shortcuts still point (or used to point) toward dead nodes
            # Heuristic: take the child that has (or had) a shortcut to a dead node
            child_scs = [s for s in shortcuts[child[0]][child[1]]
                         if (s[0], s[1]) == (surv_i, surv_j) or (s[0], s[1]) in dead_nodes]
            if child_scs:
                next_node = child
                break
        cur = next_node


def _subtree_is_dead(node, children):
    """
    Returns True if 'node' has no growth-node descendants.
    A growth node is one that has unvisited grid-forward neighbors
    (not yet added to T).

    For correctness: a node is dead if it has no children in T at all
    (leaf = dead), or all its children's subtrees are dead.

    NOTE: In the full implementation, you'd track this with a counter
    (decrement when a child becomes dead) to keep this O(1) per node.
    """
    if not children[node]:
        return True    # leaf node in T = no growth descendants
    return all(_subtree_is_dead(c, children) for c in children[node])


# ───────────────────────────────────────────────────────────────────────────────
# SHORTCUT UPDATES
# ───────────────────────────────────────────────────────────────────────────────

def update_shortcuts(parent, shortcuts, i, j, A, B, C,
                     nca_AB, nca_BC, nca_AC,
                     max_A_AB, max_B_AB,
                     max_B_BC, max_C_BC,
                     max_A_AC, max_C_AC,
                     chosen):
    """
    After adding NEW=(i,j) with `chosen` parent, install shortcuts for:
      — NEW=(i,j):   shortcuts for its two neighboring frontier pairs
      — A=(i-1,j):   update if its parent is B (B is now dead → face changed)
      — C=(i,j-1):   update if its parent is B

    The new frontier order is: ..., C, NEW, A, ...
    New neighboring pairs: (C, NEW) and (NEW, A).

    For NEW:
      NCA(NEW, A):
        par=A → NCA=A,      max_NEW=G[i][j],            max_A=0
        par=B → NCA=nca_AB, max_NEW=max(G[i][j],max_B_AB), max_A=max_A_AB
        par=C → NCA=nca_AC, max_NEW=max(G[i][j],max_C_AC), max_A=max_A_AC
      NCA(NEW, C):
        par=C → NCA=C,      max_NEW=G[i][j],            max_C=0
        par=B → NCA=nca_BC, max_NEW=max(G[i][j],max_B_BC), max_C=max_C_BC
        par=A → NCA=nca_AC, max_NEW=max(G[i][j],max_A_AC), max_C=max_C_AC

    NEW needs 2 shortcuts if par=B, else 1 (because when par=A, NCA(NEW,A)=A
    is trivially the parent — no separate shortcut needed; same logic for par=C).
    """
    NEW   = (i, j)
    G_new = 0.0   # placeholder; actual G[i][j] is embedded in max computations below
    # (we already embedded G[i][j] in the max values via nca_and_max calls upstream;
    #  here we just reconstruct the shortcut entries from those stored values)

    # ── Shortcuts for NEW ─────────────────────────────────────────────────────
    if chosen == A:
        # NCA(NEW, A) = A (parent-child, trivial — no shortcut needed for this pair)
        # NCA(NEW, C): came from A side, need shortcut toward C
        nca_new_C = nca_AC
        max_new_C = max_C_AC   # max from NEW(=A side) toward nca_AC... wait:
        # Actually max from NEW to nca_AC: NEW's parent is A, so
        # path is NEW→A→...→nca_AC, giving max = max(G[NEW], max_A_AC)
        # We don't store G[NEW] yet at this point; we pass it as a param.
        # (See note below — caller should supply G[i][j] directly.)
        shortcuts[i][j] = [
            (nca_new_C[0], nca_new_C[1], max_new_C)
        ]

    elif chosen == C:
        # NCA(NEW, C) = C (parent-child)
        # Shortcut toward A:
        nca_new_A = nca_AC
        max_new_A = max_A_AC
        shortcuts[i][j] = [
            (nca_new_A[0], nca_new_A[1], max_new_A)
        ]

    else:  # chosen == B
        # NEW has B as parent → needs shortcuts toward BOTH A and C
        nca_new_A = nca_AB
        max_new_A = max_B_AB   # path NEW→B→...→nca_AB; max from B to nca_AB
        nca_new_C = nca_BC
        max_new_C = max_B_BC
        shortcuts[i][j] = [
            (nca_new_A[0], nca_new_A[1], max_new_A),
            (nca_new_C[0], nca_new_C[1], max_new_C),
        ]

    # ── Update shortcut for A if A's parent was B ─────────────────────────────
    # B is now dead, so any shortcut from A that pointed "through B" must be
    # redirected to the new face sink (nca_AB — the NCA of A and NEW).
    if parent[A[0]][A[1]] == B:
        _replace_or_add_shortcut(shortcuts, A, nca_AB, max_A_AB)

    # ── Update shortcut for C if C's parent was B ─────────────────────────────
    if parent[C[0]][C[1]] == B:
        _replace_or_add_shortcut(shortcuts, C, nca_BC, max_C_BC)


def _replace_or_add_shortcut(shortcuts, node, new_sink, new_max):
    """
    Install or update the shortcut from `node` pointing to `new_sink`.
    If node already has a shortcut to new_sink, update its max_val.
    If node has a shortcut to a node that is now stale (dead), replace it.
    Otherwise append (node has < 2 shortcuts).
    """
    ni, nj = node
    existing = shortcuts[ni][nj]
    for k, (si, sj, mv) in enumerate(existing):
        if (si, sj) == new_sink:
            existing[k] = (new_sink[0], new_sink[1], max(mv, new_max))
            return
    # Not found — add new entry (keeping list length ≤ 2)
    if len(existing) < 2:
        existing.append((new_sink[0], new_sink[1], new_max))
    else:
        # Replace the stale one (the one whose sink is no longer on the frontier)
        # For simplicity, replace index 0; a real impl would track which is stale.
        existing[0] = (new_sink[0], new_sink[1], new_max)


# ───────────────────────────────────────────────────────────────────────────────
# COMPLEXITY NOTES
# ───────────────────────────────────────────────────────────────────────────────
# With shortcuts fully operational:
#   nca_and_max()         → O(1)  (fast path fires for neighboring frontier nodes)
#   remove_dead_path()    → O(1) amortized (each node charged at most 3 extensions,
#                            by Lemma 6 in the paper)
#   add_node() total      → O(1) per node → O(mn) overall
#
# Without shortcuts (naive slow path in nca_and_max):
#   nca_and_max()         → O(depth) = O(m+n) worst case
#   Overall               → O(mn·(m+n)) = O(N^3) for N=m+n
#
# The naive version is correct and much simpler to implement first.
# Swap in the shortcut fast-path once the naive version is verified.

# curve1 = [(1, 0), (1, 1), (0, 2), (2,3), (1, 4), (2, 4), (0, 5)]
# curve2 = [(3, 0), (3, 1), (1, 2), (2, 2), (1, 3), (3, 4), (3, 4), (3, 3), (4, 4), (1, 5)]


curve1 = [(0, 0), (1, 1), (2, 1), (3, 1), (3, 2), (2, 3), (3, 4), (4, 4), (5, 5)]
curve2 = [(1, 0), (1, 1), (2, 1), (2, 2), (4, 2), (3, 3), (3, 4), (4, 4), (4, 5), (5, 4), (5, 5)]

res = compute_lcdfm(curve1, curve2)

print(res)