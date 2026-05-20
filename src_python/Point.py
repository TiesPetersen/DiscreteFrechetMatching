class Point:
    """ Represents a point in 2D space with x and y coordinates. Used to represent the vertices of the curves. """

    def __init__(self, x, y):
        self.x = x
        self.y = y

    def __repr__(self):
        return f"Point({self.x}, {self.y})"