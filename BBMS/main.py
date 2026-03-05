from Point import Point
from Node import Node
from helper import *


def BBMS(curve1: list[Point], curve2: list[Point]) -> tuple[float, list[list[float]]]:
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

    # get path in T between G[0, 0] and G[m, n]
    matching = extractPath(G[m][n])

    # get maximum distance along the path
    frechet_distance = max(G[i][j].distance for (i, j) in matching)

    return frechet_distance, matching



def addToTree(G, i, j):
    A = G[i - 1][j] # left neighbor
    B = G[i-1][j - 1] # diagonal neighbor
    C = G[i][j - 1] # bottom neighbor
    g = G[i][j] # candidate node to add to T

    # parent(G[i, j]) <- candidate parent with lowest maximum distance to Nearest Common Ancestor in T
    selectedParent = selectParent(A, B, C)
    attach(selectedParent, g)
    
    g.is_growth = True # g is a growth node because it has grid neighbors (G[i + 1][j] and G[i][j + 1]) that are not yet in T
    
    A.is_growth = False # A is not a growth node because all its grid neighbors are now in T

    
    # if G[i - 1, j - 1] is dead then
    #     Remove the dead path ending at G[i - 1, j - 1] from T and extend shortcuts

    # Make shortcuts for G[i - 1, j], G[i, j - 1], and G[i, j] where necessary

    pass


def extractPath(node):
    """ Traces the path from the given node up to the root G[0][0], returning matching as a list of (i, j) pairs and the maximum distance along the path. """
    
    # e.g. return [(1, 4), (2, 4), (3, 4)]

    #TODO: implement


def main():
    # curve1 = [Point(1, 0), Point(1, 1), Point(0, 2), Point(2,3), Point(1, 4), Point(2, 4), Point(0, 5)]
    # curve2 = [Point(3, 0), Point(3, 1), Point(1, 2), Point(2, 2), Point(1, 3), Point(3, 4), Point(3, 4), Point(3, 3), Point(4, 4), Point(1, 5)]

    # curve1 = [Point(0, 0), Point(1, 1), Point(0, 2), Point(1, 3)]
    # curve2 = [Point(1, 0), Point(0, 1), Point(1, 2), Point(0, 3)]

    curve1 = [Point(2, 0), Point(3, 1), Point(2, 2), Point(2, 4)]
    curve2 = [Point(1, 0), Point(2, 1), Point(3, 3), Point(2, 4), Point(2, 5)]

    frechet_distance, matching = BBMS(curve1, curve2)
    print(f"Discrete Fréchet Distance: {frechet_distance}")
    print(f"Matching: {matching}")


if __name__ == "__main__":
    main()