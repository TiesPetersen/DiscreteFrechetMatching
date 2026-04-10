class Node:
    """ Represents a node in the grid G and tree T. Contains information about the node's position (i, j), distance, parent and children in the tree T, depth in the tree T, and shortcuts. (Used in BBMS and BBMS_basic)  """

    def __init__(self, i, j, distance):
        # node information
        self.i = i
        self.j = j
        self.distance = distance

        # tree structure information
        self.parent = None
        self.depth = None