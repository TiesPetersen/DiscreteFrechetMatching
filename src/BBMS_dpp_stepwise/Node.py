class Node:
    """ Represents a node in the grid G and tree T. Contains information about the node's position (i, j), distance, parent and children in the tree T, depth in the tree T, and shortcuts. (Used in BBMS and BBMS_basic)  """

    __slots__ = ('i', 'j', 'distance', 'child_upper', 'child_diagonal', 'child_right',
                 'parent', 'depth', 'low', 'high',
                 'upper_right', 'diagonal_upper', 'diagonal_lower', 'right_upper')

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
        self.low = None
        self.high = None

        # incoming shortcut information
        self.upper_right = None
        self.diagonal_upper = None
        self.diagonal_lower = None
        self.right_upper = None