from .Shortcut import Shortcut

from .Node import Node
from ..helper import distance, printGridWithShortcuts, printGridWithConnections


def BBMS_inter(curve1, curve2):
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
    D = G[i][j] # current node

    # parent(G[i, j]) <- candidate parent with lowest maximum distance to Nearest Common Ancestor in T
    selectedParent, extra_info = selectParent(A, B, C)
    attach(selectedParent, D)
    
    # Make shortcuts for G[i - 1, j], G[i, j - 1], and G[i, j] where necessary
    extra_info['selectedParent'] = selectedParent
    updateShortcuts(G, i, j, extra_info, A, B, C, D)


def selectParent(A, B, C):
    """ Select the parent among A, B, C that has the lowest maximum distance to NCA in T. Break ties by preferring A > B > C. """

    # pair AB
    max_A_AB, max_B_AB, nca_AB = getMaxDistanceToNCA(A, B)

    # pair BC
    max_B_BC, max_C_BC, nca_BC = getMaxDistanceToNCA(B, C)

    # pair AC
    max_A_AC, max_C_AC, nca_AC = getMaxDistanceToNCA(A, C)

    # select the parent with the lowest maximum distance to NCA, breaking ties by A > B > C
    A_over_B = (max_A_AB <= max_B_AB)
    B_over_C = (max_B_BC <= max_C_BC)
    A_over_C = (max_A_AC <= max_C_AC)

    # store extra info for shortcut updates and dead path handling
    extra_info = {
        'max_A_AB': max_A_AB,
        'max_B_AB': max_B_AB,
        'nca_AB': nca_AB,
        'max_B_BC': max_B_BC,
        'max_C_BC': max_C_BC,
        'nca_BC': nca_BC,
        'max_A_AC': max_A_AC,
        'max_C_AC': max_C_AC,
        'nca_AC': nca_AC
    }

    if A_over_B and A_over_C:
        return A, extra_info
    elif not A_over_B and B_over_C:
        return B, extra_info
    else:
        return C, extra_info


def getMaxDistanceToNCA(u, v):
    """ Returns the maximum distance from u and v to their nearest common ancestor in T. The NCA's own distance is NOT included in the maximum calculation. """

    # Note: u should always take the low shortcut if it exists, and v should always take the high shortcut if it exists
    # TODO: proof that this is correct

    max_distance_u = float('-inf')
    max_distance_v = float('-inf')

    while u != v:
        if v.depth > u.depth:
            # v should take high shortcut if it exists
            if v.high is not None:
                max_distance_v = max(max_distance_v, v.high.value)
                v = v.high.target
            else:
                max_distance_v = max(max_distance_v, v.distance)
                v = v.parent
        else:
            # u should take low shortcut if it exists
            if u.low is not None:
                max_distance_u = max(max_distance_u, u.low.value)
                u = u.low.target
            else:
                max_distance_u = max(max_distance_u, u.distance)
                u = u.parent

    return max_distance_u, max_distance_v, u


def updateShortcuts(G, i, j, extra_info, A, B, C, D):
    """ Updates shortcuts for G[i - 1, j], G[i, j - 1], and G[i, j] """

    # G[i - 1, j] or G[i, j - 1] need a shortcut only if its parent is G[i - 1, j - 1]
    # G[i , j] needs two shortcuts if G[i - 1, j - 1] is its parent, only one shortcut otherwise

    # check for neighbors
    AB = A.parent == B # A is child of B
    BC = C.parent == B # C is child of B

    # 12 different cases
    # TODO: make this cleaner
    if extra_info['selectedParent'] == A:
        # chosen parent is A 
        if AB and BC:
            A.low = Shortcut(B, A.distance)
            C.high = Shortcut(B, C.distance)
            D.low = Shortcut(B, max(A.distance, D.distance))
        elif AB:
            A.low = Shortcut(extra_info['nca_AC'], extra_info['max_A_AC'])
            D.low = Shortcut(extra_info['nca_AC'], max(extra_info['max_A_AC'], D.distance))
        elif BC:
            C.high = Shortcut(extra_info['nca_AC'], extra_info['max_C_AC'])
            D.low = Shortcut(extra_info['nca_AC'], max(extra_info['max_A_AC'], D.distance))
        else:
            D.low = Shortcut(extra_info['nca_AB'], max(extra_info['max_A_AB'], D.distance))
    elif extra_info['selectedParent'] == B:
        # chosen parent is B
        if AB and BC:
            A.low = Shortcut(B, A.distance)
            C.high = Shortcut(B, C.distance)
            D.high = Shortcut(B, D.distance)
            D.low = Shortcut(B, D.distance)
        elif AB:
            A.low = Shortcut(B, A.distance)
            D.high = Shortcut(B, D.distance)
            D.low = Shortcut(extra_info['nca_AC'], max(extra_info['max_B_BC'], D.distance))
        elif BC:
            C.high = Shortcut(B, C.distance)
            D.high = Shortcut(extra_info['nca_AC'], max(extra_info['max_B_AB'], D.distance))
            D.low = Shortcut(B, D.distance)
        else:
            D.high = Shortcut(extra_info['nca_AB'], max(extra_info['max_B_AB'], D.distance))
            D.low = Shortcut(extra_info['nca_BC'], max(extra_info['max_B_BC'], D.distance))
    elif extra_info['selectedParent'] == C:
        # chosen parent is C
        if AB and BC:
            A.low = Shortcut(B, A.distance)
            C.high = Shortcut(B, C.distance)
            D.high = Shortcut(B, max(C.distance, D.distance))
        elif AB:
            A.low = Shortcut(extra_info['nca_AC'], extra_info['max_A_AC'])
            D.high = Shortcut(extra_info['nca_AC'], max(extra_info['max_C_AC'], D.distance))
        elif BC:
            C.high = Shortcut(extra_info['nca_AC'], extra_info['max_C_AC'])
            D.high = Shortcut(extra_info['nca_AC'], max(extra_info['max_C_AC'], D.distance))
        else:
            D.high = Shortcut(extra_info['nca_BC'], max(extra_info['max_C_BC'], D.distance))
    

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