class Shortcut:
    """ Represents a shortcut from a node in the tree T to one of its ancestors, containing information about the target ancestor node and the maximum distance along the path from the source node to the target ancestor. (Used in BBMS) """

    def __init__(self, target, value):
        self.target = target
        self.value = value