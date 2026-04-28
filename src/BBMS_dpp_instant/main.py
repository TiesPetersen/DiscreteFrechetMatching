from .Shortcut import Shortcut
from .Direction import Direction
from .Node import Node
from ..helper import distance, printGridWithShortcuts, printGridWithConnections


def BBMS_dpp_instant(curve1, curve2):
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

    # printGridWithShortcuts(G, type_to_print="distance")
    # print("\n\n")

    # for i <- 1 to m do
    #     for j <- 1 to n do
    #         AddToTree(T, G, i, j)
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            addToTree(G, i, j)
            # printGridWithConnections(G, type_to_print="distance")
            # printGridWithShortcuts(G, type_to_print="distance")
            # print("\n\n")

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

    if not hasChildren(B):
        s = getDeepestShortcut(B)
        if s is None: 
            raise ValueError("Node B has no children and no shortcuts, which should not be possible.")
        
        dead_path_base = s.target

        extendShortcuts(dead_path_base, s.final_direction)
        detachDeadPath(dead_path_base, s.final_direction)


    # no_children = (G[i - 1][j - 1].child_upper == False) + (G[i - 1][j - 1].child_diagonal == False) + (G[i - 1][j - 1].child_right == False)
    # if no_children:
    #    s <- deepest shortcut from G[i - 1, j - 1] (make function for this: getDeepestShortcut)
    #    n <- target node of shortcut s
    #    extend shortcuts based on: s.direction, n's children (make function for this: extendShortcuts)
    #    delete shortcuts??? you cannot delete all shortcuts starting somewhere in the dead path. not deleted shortcuts will still be extended in the future, which is inefficient.
    #    update children, etc of n

    # if G[i - 1, j - 1] is dead then
    #     Remove the dead path ending at G[i - 1, j - 1] from T and extend shortcuts
    # TODO

    # Make shortcuts for G[i - 1, j], G[i, j - 1], and G[i, j] where necessary
    extra_info['selectedParent'] = selectedParent
    updateShortcuts(G, i, j, extra_info, A, B, C, D)


def selectParent(A, B, C):
    """ Select the parent among A, B, C that has the lowest maximum distance to NCA in T. Break ties by preferring A > B > C. """

    # pair AB
    max_A_AB, max_B_AB, nca_AB, dir_A_AB, dir_B_AB = getMaxDistanceToNCA(A, B)

    # pair BC
    max_B_BC, max_C_BC, nca_BC, dir_B_BC, dir_C_BC = getMaxDistanceToNCA(B, C)

    # pair AC
    max_A_AC, max_C_AC, nca_AC, dir_A_AC, dir_C_AC = getMaxDistanceToNCA(A, C)

    # select the parent with the lowest maximum distance to NCA, breaking ties by A > B > C
    A_over_B = (max_A_AB <= max_B_AB)
    B_over_C = (max_B_BC <= max_C_BC)
    A_over_C = (max_A_AC <= max_C_AC)

    # store extra info for shortcut updates and dead path handling
    extra_info = {
        'max_A_AB': max_A_AB,
        'max_B_AB': max_B_AB,
        'nca_AB': nca_AB,
        'dir_A_AB': dir_A_AB,
        'dir_B_AB': dir_B_AB,
        'max_B_BC': max_B_BC,
        'max_C_BC': max_C_BC,
        'nca_BC': nca_BC,
        'dir_B_BC': dir_B_BC,
        'dir_C_BC': dir_C_BC,
        'max_A_AC': max_A_AC,
        'max_C_AC': max_C_AC,
        'nca_AC': nca_AC,
        'dir_A_AC': dir_A_AC,
        'dir_C_AC': dir_C_AC
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

    final_dir_u = None
    final_dir_v = None

    while u != v:
        if v.depth > u.depth:
            # v should take high shortcut if it exists
            if v.out_high is not None:
                max_distance_v = max(max_distance_v, v.out_high.value)
                final_dir_v = v.out_high.final_direction
                v = v.out_high.target
            else:
                max_distance_v = max(max_distance_v, v.distance)
                final_dir_v = getDirection(v, v.parent)
                v = v.parent
        else:
            # u should take low shortcut if it exists
            if u.out_low is not None:
                max_distance_u = max(max_distance_u, u.out_low.value)
                final_dir_u = u.out_low.final_direction
                u = u.out_low.target
            else:
                max_distance_u = max(max_distance_u, u.distance)
                final_dir_u = getDirection(u, u.parent)
                u = u.parent

    return max_distance_u, max_distance_v, u, final_dir_u, final_dir_v


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
            addShortcut(A, "out_low", B, A.distance, Direction.DOWN, None)
            addShortcut(C, "out_high", B, C.distance, Direction.LEFT, None)
            addShortcut(D, "out_low", B, max(A.distance, D.distance), Direction.DOWN, None)
        elif AB:
            addShortcut(A, "out_low", extra_info['nca_AC'], extra_info['max_A_AC'], extra_info['dir_A_AC'], "lower")
            addShortcut(D, "out_low", extra_info['nca_AC'], max(extra_info['max_A_AC'], D.distance), extra_info['dir_A_AC'], "lower")
        elif BC:
            addShortcut(C, "out_high", extra_info['nca_AC'], extra_info['max_C_AC'], extra_info['dir_C_AC'], "upper")
            addShortcut(D, "out_low", extra_info['nca_AC'], max(extra_info['max_C_AC'], D.distance), extra_info['dir_C_AC'], "upper")
        else:
            addShortcut(D, "out_low", extra_info['nca_AB'], max(extra_info['max_A_AB'], D.distance), extra_info['dir_A_AB'], "upper")
    elif extra_info['selectedParent'] == B:
        # chosen parent is B
        if AB and BC:
            addShortcut(A, "out_low", B, A.distance, Direction.DOWN, None)
            addShortcut(C, "out_high", B, C.distance, Direction.LEFT, None)
            addShortcut(D, "out_high", B, D.distance, Direction.DIAGONAL, None)
            addShortcut(D, "out_low", B, D.distance, Direction.DIAGONAL, None)
        elif AB:
            addShortcut(A, "out_low", B, A.distance, Direction.DOWN, None)
            addShortcut(D, "out_high", B, D.distance, Direction.DIAGONAL, None)
            addShortcut(D, "out_low", extra_info['nca_AC'], max(extra_info['max_B_BC'], D.distance), extra_info['dir_B_BC'], "lower")
        elif BC:
            addShortcut(C, "out_high", B, C.distance, Direction.LEFT, None)
            addShortcut(D, "out_high", extra_info['nca_AC'], max(extra_info['max_B_AB'], D.distance), extra_info['dir_B_AB'], "upper")
            addShortcut(D, "out_low", B, D.distance, Direction.DIAGONAL, None)
        else:
            addShortcut(D, "out_high", extra_info['nca_AB'], max(extra_info['max_B_AB'], D.distance), extra_info['dir_B_AB'], "upper")
            addShortcut(D, "out_low", extra_info['nca_BC'], max(extra_info['max_B_BC'], D.distance), extra_info['dir_B_BC'], "lower")
    elif extra_info['selectedParent'] == C:
        # chosen parent is C
        if AB and BC:
            addShortcut(A, "out_low", B, A.distance, Direction.DOWN, None)
            addShortcut(C, "out_high", B, C.distance, Direction.LEFT, None)
            addShortcut(D, "out_high", B, max(C.distance, D.distance), Direction.LEFT, None)
        elif AB:
            addShortcut(A, "out_low", extra_info['nca_AC'], extra_info['max_A_AC'], extra_info['dir_A_AC'], "lower")
            addShortcut(D, "out_high", extra_info['nca_AC'], max(extra_info['max_C_AC'], D.distance), extra_info['dir_C_AC'], "lower")
        elif BC:
            addShortcut(C, "out_high", extra_info['nca_AC'], extra_info['max_C_AC'], extra_info['dir_C_AC'], "upper")
            addShortcut(D, "out_high", extra_info['nca_AC'], max(extra_info['max_C_AC'], D.distance), extra_info['dir_C_AC'], "upper")
        else:
            addShortcut(D, "out_high", extra_info['nca_BC'], max(extra_info['max_C_BC'], D.distance), extra_info['dir_C_BC'], "lower")
    

def addShortcut(origin_node, out_attr, target, value, final_direction, bias):
    """ Helper function to add a shortcut from origin_node.out_attr to target with the given value and final direction, and to update the incoming shortcut lists of the target node accordingly. Bias is used to determine whether a diagonal shortcut should be added to the upper or lower diagonal incoming shortcuts of the target node. """

    shortcut = Shortcut(target, value, final_direction)

    # write back to the actual node attribute
    setattr(origin_node, out_attr, shortcut)

    # update target's incoming shortcut information based on final direction of the shortcut
    if final_direction == Direction.DOWN:
        target.in_upper.append(shortcut)
    elif final_direction == Direction.DIAGONAL:
        if bias == "upper":
            target.in_diagonal_upper.append(shortcut)
        elif bias == "lower":
            target.in_diagonal_lower.append(shortcut)
    elif final_direction == Direction.LEFT:
        target.in_right.append(shortcut)




def extendShortcuts(dead_path_base, final_direction):
    """ Extends shortcuts that need to be extended when a dead path is removed, based on the final direction of the shortcut that led to the dead path. """

    if final_direction == Direction.DOWN:
        if dead_path_base.child_diagonal:
            # extend diagonal upper incoming shortcuts to dead_path_base.out_high
            extendShortcutsTo(dead_path_base.in_diagonal_upper, dead_path_base.out_high)
        elif dead_path_base.child_right:
            # extend right upper incoming shortcuts to dead_path_base.out_high
            extendShortcutsTo(dead_path_base.in_right, dead_path_base.out_high)
    elif final_direction == Direction.DIAGONAL:
        if dead_path_base.child_right and not dead_path_base.child_upper:
            # extend right upper incoming shortcuts to dead_path_base.out_high
            extendShortcutsTo(dead_path_base.in_right, dead_path_base.out_high)
            pass
        elif dead_path_base.child_upper and not dead_path_base.child_right:
            # extend upper right incoming shortcuts to dead_path_base.out_low
            extendShortcutsTo(dead_path_base.in_upper, dead_path_base.out_low)
    elif final_direction == Direction.LEFT:
        if dead_path_base.child_diagonal:
            # extend diagonal lower incoming shortcuts to dead_path_base.out_low
            extendShortcutsTo(dead_path_base.in_diagonal_lower, dead_path_base.out_low)
        elif dead_path_base.child_upper:
            # extend upper right incoming shortcuts to dead_path_base.out_low
            extendShortcutsTo(dead_path_base.in_upper, dead_path_base.out_low)


def extendShortcutsTo(shortcuts, followup_shortcut):
    """ Helper function for extendShortcuts that extends the given list of shortcuts to the target of the followup_shortcut. """

    for shortcut in shortcuts:
        shortcut.target = followup_shortcut.target
        shortcut.value = max(shortcut.value, followup_shortcut.value)
        shortcut.final_direction = followup_shortcut.final_direction


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

    # update parent's child information
    if child.i == parent.i and child.j == parent.j + 1:
        parent.child_upper = True
    elif child.i == parent.i + 1 and child.j == parent.j + 1:
        parent.child_diagonal = True
    elif child.i == parent.i + 1 and child.j == parent.j:
        parent.child_right = True
    else:
        raise ValueError("Invalid child-parent relationship: child ({}, {}) and parent ({}, {})".format(child.i, child.j, parent.i, parent.j))


def detachDeadPath(dead_path_base, final_direction):
    if final_direction == Direction.DOWN:
        dead_path_base.child_upper = False
    elif final_direction == Direction.DIAGONAL:
        dead_path_base.child_diagonal = False
    elif final_direction == Direction.LEFT:
        dead_path_base.child_right = False


def hasChildren(node):
    """ Returns True if the given node has any children in T, and False otherwise. """

    return node.child_upper or node.child_diagonal or node.child_right


def getDirection(child, parent):
    """ Returns the direction from child to parent as a Direction enum value. Assumes child is directly connected to parent in T. """

    if child.i == parent.i + 1 and child.j == parent.j:
        return Direction.DOWN
    elif child.i == parent.i + 1 and child.j == parent.j + 1:
        return Direction.DIAGONAL
    elif child.i == parent.i and child.j == parent.j + 1:
        return Direction.LEFT
    else:
        raise ValueError("Invalid child-parent relationship: child ({}, {}) and parent ({}, {})".format(child.i, child.j, parent.i, parent.j))


def getDeepestShortcut(node):
    """ Returns the deepest shortcut from the given node, defined as the shortcut that leads to the ancestor with the greatest depth. If there are multiple such shortcuts, returns one of them arbitrarily. """

    deepest_shortcut = None
    max_depth = float('-inf')

    for shortcut in [node.out_low, node.out_high]:
        if shortcut is not None and shortcut.target.depth > max_depth:
            deepest_shortcut = shortcut
            max_depth = shortcut.target.depth

    return deepest_shortcut