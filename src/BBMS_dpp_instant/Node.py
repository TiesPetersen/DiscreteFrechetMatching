class Node:
    """ Represents a node in the grid G and tree T. Contains information about the node's position (i, j), distance, parent and children in the tree T, depth in the tree T, and shortcuts. (Used in BBMS and BBMS_basic)  """

    __slots__ = ('i', 'j', 'distance', 'child_upper', 'child_diagonal', 'child_right',
                 'parent', 'depth', 'out_low', 'out_high',
                 'in_upper', 'in_diagonal_upper', 'in_diagonal_lower', 'in_right')

    def __init__(self, i, j, distance):
        # node information
        self.i = i
        self.j = j
        self.distance = distance

        # tree structure information
        self.child_upper = False
        self.child_diagonal = False
        self.child_right = False
        self.parent = None
        self.depth = None

        # outgoing shortcut information
        self.out_low = None
        self.out_high = None

        # incoming shortcut information
        self.in_upper = set()
        self.in_diagonal_upper = set()
        self.in_diagonal_lower = set()
        self.in_right = set()