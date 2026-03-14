class Node:
    # node information
    distance : float
    i : int
    j : int

    # tree structure information
    parent = None
    children = []
    depth : int

    # shortcut information
    low = None
    high = None

    def __init__(self, i, j, distance):
        self.i = i
        self.j = j
        self.distance = distance