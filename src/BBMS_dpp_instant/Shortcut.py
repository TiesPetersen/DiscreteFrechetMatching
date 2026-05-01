class Shortcut:
    """ Represents a shortcut from a node in the tree T to one of its ancestors, containing information about the target ancestor node, the maximum distance along the path from the source node to the target ancestor and the direction of the shortcut."""

    __slots__ = ('target', 'value', 'final_direction')

    def __init__(self, target, value, final_direction):
        self.target = target
        self.value = value
        self.final_direction = final_direction