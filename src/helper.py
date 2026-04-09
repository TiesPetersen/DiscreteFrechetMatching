#  HELPER FUNCTIONS


def distance(p1, p2):
    """ Computes the Euclidean distance between two points p1 and p2. Each point is a Point object. """
    return ((p1.x - p2.x) ** 2 + (p1.y - p2.y) ** 2) ** 0.5


#  DEVELOPMENT HELPER FUNCTIONS

def printGrid(G):
    """ Prints the grid G with distances. """
    for y in reversed(range(len(G[0]))):
        for x in range(len(G)):
            print(f"{G[x][y].distance:6.2f}", end=" ")
        print()


def printGridWithConnections(G, type_to_print="distance"):
    """ Prints the grid G with distances and connections in the tree T. type_to_print can be 'distance' or 'depth' to specify which value to print for each node. """

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


def printGridWithShortcuts(G, type_to_print="distance"):
    """ Prints the grid G with tree connections and shortcut information.
        Each node shows its (i,j) coordinates and value. Below each node, any
        low/high shortcuts are printed showing where they point and their max value.
        type_to_print can be 'distance' or 'depth'. """

    if not G or not G[0]:
        return

    num_x = len(G)
    num_y = len(G[0])

    VAL_W = 12   # width of the node value cell  (e.g. " (3,2)=8.06 ")
    H_GAP = 10   # width of the horizontal gap/connector between columns
    COL_W = VAL_W + H_GAP  # total width per column = 22

    def connected(a, b):
        if a is None or b is None:
            return False
        return a.parent is b or b.parent is a

    def format_val(node):
        if type_to_print == "distance":
            s = f"{node.distance:.2f}"
        elif type_to_print == "depth":
            if hasattr(node, "depth") and node.depth is not None:
                s = f"{node.depth:.2f}"
            else:
                s = "NA"
        else:
            s = "?"
        return f"({node.i},{node.j})={s}".center(VAL_W)

    for y in reversed(range(num_y)):
        # --- value row ---
        parts = []
        for x in range(num_x):
            parts.append(format_val(G[x][y]))
            if x < num_x - 1:
                if connected(G[x][y], G[x + 1][y]):
                    parts.append("----".center(H_GAP))
                else:
                    parts.append(" " * H_GAP)
        print("".join(parts))

        # --- shortcut rows ---
        any_low  = any(getattr(G[x][y], "low",  None) is not None for x in range(num_x))
        any_high = any(getattr(G[x][y], "high", None) is not None for x in range(num_x))

        if any_low:
            parts = []
            for x in range(num_x):
                sc = getattr(G[x][y], "low", None)
                s = f"lo->({sc.target.i},{sc.target.j})={sc.value:.2f}" if sc else ""
                parts.append(f"{s:<{COL_W}}")
            print("".join(parts).rstrip())

        if any_high:
            parts = []
            for x in range(num_x):
                sc = getattr(G[x][y], "high", None)
                s = f"hi->({sc.target.i},{sc.target.j})={sc.value:.2f}" if sc else ""
                parts.append(f"{s:<{COL_W}}")
            print("".join(parts).rstrip())

        # --- connector row between y and y-1 ---
        if y > 0:
            total_width = num_x * COL_W
            line = list(" " * total_width)

            for x in range(num_x):
                center = x * COL_W + VAL_W // 2

                # vertical: G[x][y] <-> G[x][y-1]
                if connected(G[x][y], G[x][y - 1]):
                    if center < total_width:
                        line[center] = "|"

                # diagonal \: G[x][y] down-right to G[x+1][y-1]
                if x + 1 < num_x and connected(G[x][y], G[x + 1][y - 1]):
                    pos = x * COL_W + VAL_W + H_GAP // 2
                    if pos < total_width:
                        line[pos] = "\\"

                # diagonal /: G[x][y] down-left to G[x-1][y-1]
                if x - 1 >= 0 and connected(G[x][y], G[x - 1][y - 1]):
                    pos = (x - 1) * COL_W + VAL_W + H_GAP // 2
                    if pos < total_width:
                        if line[pos] == "\\":
                            line[pos] = "X"
                        else:
                            line[pos] = "/"

            print("".join(line).rstrip())