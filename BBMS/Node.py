class Node:
    # node information
    distance : float
    i : int
    j : int

    # tree structure information
    parent = None
    children = []
    depth : int

    # node type information (TODO)
    is_growth : bool
    is_dead : bool

    # shortcut information (TODO)
    sc_lo = None
    sc_hi = None

    def __init__(self, i, j, distance):
        self.i = i
        self.j = j
        self.distance = distance