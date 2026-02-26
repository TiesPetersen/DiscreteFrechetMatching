# Node:
#   val       : float          // G[i][j] = ||p_i - q_j||
#   i, j      : int            // grid coordinates
#   parent    : Node?          // null only for root G[0][0]
#   children  : List<Node>
#   
#   // Each node has up to 2 shortcuts.
#   // In the staircase frontier each growth-node edge (v → parent(v)) touches
#   // at most 2 faces.  The shortcut for a face stores the max G-value on the
#   // path from v up to the face's sink (= NCA of the two growth nodes bounding
#   // that face), EXCLUDING the sink's value.
#   //
#   //  sc_lo : shortcut toward the face with the frontier neighbor of SMALLER
#   //          staircase index (toward G[m][0])
#   //  sc_hi : shortcut toward the face with the frontier neighbor of LARGER
#   //          staircase index (toward G[0][n])

#   sc_lo     : Shortcut?
#   sc_hi     : Shortcut?

#   // Lifecycle flags
#   is_growth : bool   // has at least one grid-neighbor not yet in T
#   is_dead   : bool   // no growth descendant exists anywhere below this node


class Node:
    parent = None
    children = []
    sc_lo = None
    sc_hi = None
    is_growth = True
    is_dead = False

    def __init__(self, i, j, distance):
        self.i = i
        self.j = j
        self.distance = distance
        