from Point import Point
from Node import Node
from helper import *


def BBMS(curve1: list[Point], curve2: list[Point]) -> tuple[float, list[list[float]]]:
    """ Computes the discrete Fréchet distance between curve1 and curve2 using the BBMS algorithm. Returns a tuple of (frechet_distance, matching) where frechet_distance is the computed distance and matching is a list of (i, j) pairs representing the matching between nodes in G[m][n] and G[0][0]. """

    m = len(curve1) - 1
    print(f"Curve 1 (P) has m = {m} edges, and thus m+1 = {m + 1} nodes.")
    n = len(curve2) - 1
    print(f"Curve 2 (Q) has n = {n} edges, and thus n+1 = {n + 1} nodes.")
    assert(m > 0 and n > 0)

    # construct grid G for curve1 and curve2
    G = [[Node(x, y, distance(curve1[x], curve2[y])) for y in range(n + 1)] for x in range(m + 1)]
    
    G[0][0].depth = 0 # root node G[0][0] has depth 0

    printGridWithConnections(G, type_to_print="depth")

    # for i <- 1 to m do: Add G[i, 0] to T
    for i in range(1, m + 1):
        print(f"Attaching G[{i}][0] to G[{i - 1}][0]")
        attach(G[i - 1][0], G[i][0])

    # for j <- 1 to n do: Add G[0, j] to T
    for j in range(1, n + 1):
        print(f"Attaching G[0][{j}] to G[0][{j - 1}]")
        attach(G[0][j - 1], G[0][j])

    printGridWithConnections(G, type_to_print="depth")

    # for i <- 1 to m do
    #     for j <- 1 to n do
    #         AddToTree(T, G, i, j)
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            addToTree(G, i, j)
            printGridWithConnections(G, type_to_print="distance")
            print("\n\n")

    # return path in T between G[0, 0] and G[m, n], and return Frechet distance
    return extractMatchingAndFrechetDistance(G[m][n])


def addToTree(G, i, j):
    """ Adds G[i][j] to the tree T by attaching it to the candidate parent with lowest maximum distance to NCA in T. Also handles dead paths and shortcut updates as necessary. """

    A = G[i - 1][j    ] # left neighbor
    B = G[i - 1][j - 1] # diagonal neighbor
    C = G[i    ][j - 1] # bottom neighbor

    # parent(G[i, j]) <- candidate parent with lowest maximum distance to Nearest Common Ancestor in T
    selectedParent = selectParent(A, B, C)
    attach(selectedParent, G[i][j])
    
    # if G[i - 1, j - 1] is dead then
    #     Remove the dead path ending at G[i - 1, j - 1] from T and extend shortcuts

    # Make shortcuts for G[i - 1, j], G[i, j - 1], and G[i, j] where necessary


def selectParent(A, B, C):
    """ Select the parent among A, B, C that has the lowest maximum distance to NCA in T. Break ties by preferring A > B > C. """

    # pair AB
    max_A_AB, max_B_AB = getMaxDistanceToNCA(A, B)
    print(f"max_A_AB: {max_A_AB}, max_B_AB: {max_B_AB}")

    # pair BC
    max_B_BC, max_C_BC = getMaxDistanceToNCA(B, C)
    print(f"max_B_BC: {max_B_BC}, max_C_BC: {max_C_BC}")

    # pair AC
    max_A_AC, max_C_AC = getMaxDistanceToNCA(A, C)
    print(f"max_A_AC: {max_A_AC}, max_C_AC: {max_C_AC}")

    # select the parent with the lowest maximum distance to NCA, breaking ties by A > B > C
    A_over_B = (max_A_AB <= max_B_AB)
    B_over_C = (max_B_BC <= max_C_BC)
    A_over_C = (max_A_AC <= max_C_AC)
    if A_over_B and A_over_C:
        return A
    elif not A_over_B and B_over_C:
        return B
    else:
        return C


def getMaxDistanceToNCA(node1, node2):
    """ Returns the maximum distance from node1 and node2 to their nearest common ancestor in T. The NCA's own distance is NOT included in the maximum calculation. """

    # TODO: using shortcuts

    u = node1
    v = node2
    max_distance_u = float('-inf')
    max_distance_v = float('-inf')

    # walk deeper node up until both nodes are at the same depth
    while u.depth > v.depth:
        max_distance_u = max(max_distance_u, u.distance)
        u = u.parent
    
    while v.depth > u.depth:
        max_distance_v = max(max_distance_v, v.distance)
        v = v.parent

    # now walk both nodes up together until they meet at NCA
    while u != v:
        max_distance_u = max(max_distance_u, u.distance)
        max_distance_v = max(max_distance_v, v.distance)
        u = u.parent
        v = v.parent

    return max_distance_u, max_distance_v


def extractMatchingAndFrechetDistance(node):
    """ Traces the path from the given node up to the root G[0][0], returning matching as a list of (i, j) pairs and the maximum distance along the path. """
    
    path = []
    max_distance = float('-inf')
    while node is not None:
        path.append((node.i, node.j))
        max_distance = max(max_distance, node.distance)
        node = node.parent

    path.reverse()

    return path, max_distance


def main():
    curve1 = [Point(1, 0), Point(1, 1), Point(0, 2), Point(2,3), Point(1, 4), Point(2, 4), Point(0, 5)]
    curve2 = [Point(3, 0), Point(3, 1), Point(1, 2), Point(2, 2), Point(1, 3), Point(3, 4), Point(3, 4), Point(3, 3), Point(4, 4), Point(1, 5)]

    # curve1 = [Point(0, 0), Point(1, 1), Point(0, 2), Point(1, 3)]
    # curve2 = [Point(1, 0), Point(0, 1), Point(1, 2), Point(0, 3)]

    # curve1 = [Point(2, 0), Point(3, 1), Point(2, 2), Point(2, 4)]
    # curve2 = [Point(1, 0), Point(2, 1), Point(3, 3), Point(2, 4), Point(2, 5)]

    frechet_distance, matching = BBMS(curve1, curve2)
    print(f"Discrete Fréchet Distance: {frechet_distance}")
    print(f"Matching: {matching}")


if __name__ == "__main__":
    main()