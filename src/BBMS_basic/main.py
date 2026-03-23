from ..helper import distance

from .Node import Node


def BBMS_basic(curve1, curve2):
    """ Computes the discrete Fréchet distance between curve1 and curve2 using the BBMS algorithm. Returns a tuple of (frechet_distance, matching) where frechet_distance is the computed distance and matching is a list of (i, j) pairs representing the matching between nodes in G[m][n] and G[0][0]. """

    m = len(curve1) - 1
    n = len(curve2) - 1
    assert(m > 0 and n > 0)

    # construct grid G for curve1 and curve2
    G = [[Node(x, y, distance(curve1[x], curve2[y])) for y in range(n + 1)] for x in range(m + 1)]
    G[0][0].depth = 0 # root node G[0][0] has depth 0

    # for i <- 1 to m do: Add G[i, 0] to T
    for i in range(1, m + 1):
        attach(G[i - 1][0], G[i][0])

    # for j <- 1 to n do: Add G[0, j] to T
    for j in range(1, n + 1):
        attach(G[0][j - 1], G[0][j])

    # for i <- 1 to m do
    #     for j <- 1 to n do
    #         AddToTree(T, G, i, j)
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            addToTree(G, i, j)

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


def selectParent(A, B, C):
    """ Select the parent among A, B, C that has the lowest maximum distance to NCA in T. Break ties by preferring A > B > C. """

    # pair AB
    max_A_AB, max_B_AB = getMaxDistanceToNCA(A, B)

    # pair BC
    max_B_BC, max_C_BC = getMaxDistanceToNCA(B, C)

    # pair AC
    max_A_AC, max_C_AC = getMaxDistanceToNCA(A, C)

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
    """ Returns the maximum distance from node1 and node2 to their nearest common ancestor in T. The NCA's own distance is NOT included in the maximum calculation. This implementation does not use shortcuts, but instead walks up the tree one step at a time."""

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

    # trace path from node up to root G[0][0], keeping track of maximum distance along the path
    while node is not None:
        path.append((node.i, node.j))
        max_distance = max(max_distance, node.distance)
        node = node.parent

    # reverse the path to get the matching from G[0][0] to G[m][n]
    path.reverse()

    return path, max_distance


def attach(parent, child):
    """ Attaches the child node to the parent node in the tree T, and updates the depth of the child node accordingly. """

    child.parent = parent
    child.depth = parent.depth + 1