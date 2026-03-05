from Point import Point
from Node import Node


# Helper functions for BBMS algorithm implementation


def distance(p: Point, q: Point) -> float:
    return ((p.x - q.x) ** 2 + (p.y - q.y) ** 2) ** 0.5


def attach(parent: Node, child: Node):
    parent.children.append(child)
    child.parent = parent
    child.depth = parent.depth + 1






#  DEV HELPER FUNCTIONS

def printGrid(G):
    for y in reversed(range(len(G[0]))):
        for x in range(len(G)):
            print(f"{G[x][y].distance:6.2f}", end=" ")
        print()



def printGridWithConnections(G, type_to_print="distance"):
    if not G or not G[0]:
        return

    num_x = len(G)      # number of columns (x-axis)
    num_y = len(G[0])    # number of rows (y-axis)
    COL_W = 10  # 6 for value + 4 for gap

    def connected(a, b):
        if a is None or b is None:
            return False
        return a.parent is b or b.parent is a

    for y in reversed(range(num_y)):
        # --- value row ---
        parts = []
        for x in range(num_x):

            if type_to_print == "distance":
                parts.append(f"{G[x][y].distance:6.2f}")
            elif type_to_print == "depth":
                if hasattr(G[x][y], "depth") and G[x][y].depth is not None:
                    parts.append(f"{G[x][y].depth:6.2f}")
                else:
                    parts.append(" " * 3 + "NA" + " " * 3)
            
            if x < num_x - 1:
                if connected(G[x][y], G[x + 1][y]):
                    parts.append(" -- ")
                else:
                    parts.append("    ")
        print("".join(parts))

        # --- connector row between y and y-1 ---
        if y > 0:
            width = num_x * COL_W
            line = list(" " * width)

            for x in range(num_x):
                center = x * COL_W + 2

                # vertical: G[x][y] <-> G[x][y-1]
                if connected(G[x][y], G[x][y - 1]):
                    if center < width:
                        line[center] = "|"

                # diagonal \: G[x][y] down-right to G[x+1][y-1]
                if x + 1 < num_x and connected(G[x][y], G[x + 1][y - 1]):
                    pos = x * COL_W + 7
                    if pos < width:
                        line[pos] = "\\"

                # diagonal /: G[x][y] down-left to G[x-1][y-1]
                if x - 1 >= 0 and connected(G[x][y], G[x - 1][y - 1]):
                    pos = (x - 1) * COL_W + 7
                    if pos < width:
                        if line[pos] == "\\":
                            line[pos] = "X"
                        else:
                            line[pos] = "/"

            print("".join(line).rstrip())