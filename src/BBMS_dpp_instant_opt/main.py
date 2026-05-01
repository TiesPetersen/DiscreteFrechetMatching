import dataclasses

import numpy as np

from .Direction import Direction

_NONE = -1  # sentinel for "no parent" / "no shortcut"


# ---------------------------------------------------------------------------
# Grid container — replaces the (m+1)×(n+1) grid of Node objects
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class _Grid:
    dist:              np.ndarray   # float64 (m+1, n+1) — pairwise Euclidean distances
    depth:             np.ndarray   # int32   (m+1, n+1) — tree depth, -1 = unset
    parent_i:          np.ndarray   # int32   (m+1, n+1) — parent row index, -1 = no parent
    parent_j:          np.ndarray   # int32   (m+1, n+1) — parent col index
    child_upper:       np.ndarray   # bool    (m+1, n+1)
    child_diagonal:    np.ndarray   # bool    (m+1, n+1)
    child_right:       np.ndarray   # bool    (m+1, n+1)
    # Outgoing shortcut "low" — _NONE in _ti means no shortcut
    out_low_ti:        np.ndarray   # int32   target row
    out_low_tj:        np.ndarray   # int32   target col
    out_low_val:       np.ndarray   # float64 max distance along shortcut path
    out_low_dir:       np.ndarray   # int8    Direction.value of final edge
    # Outgoing shortcut "high"
    out_high_ti:       np.ndarray   # int32
    out_high_tj:       np.ndarray   # int32
    out_high_val:      np.ndarray   # float64
    out_high_dir:      np.ndarray   # int8
    # Incoming shortcut reverse index — variable-length, kept as Python lists.
    # Each cell holds a list of (src_i: int, src_j: int, is_high: bool) triples
    # identifying which node's out_low/out_high shortcut points here.
    in_upper:          list
    in_diagonal_upper: list
    in_diagonal_lower: list
    in_right:          list


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def BBMS_dpp_instant_opt(curve1, curve2):
    """Compute the discrete Fréchet distance using the BBMS algorithm with numpy arrays.

    Returns (matching, frechet_distance) where matching is a list of (i, j) pairs.
    Drop-in replacement for BBMS_dpp_instant with lower memory usage.
    """
    m = len(curve1) - 1
    n = len(curve2) - 1
    assert m > 0 and n > 0

    shape = (m + 1, n + 1)
    g = _Grid(
        dist=_compute_dist(curve1, curve2),
        depth=np.full(shape, _NONE, dtype=np.int32),
        parent_i=np.full(shape, _NONE, dtype=np.int32),
        parent_j=np.full(shape, _NONE, dtype=np.int32),
        child_upper=np.zeros(shape, dtype=np.bool_),
        child_diagonal=np.zeros(shape, dtype=np.bool_),
        child_right=np.zeros(shape, dtype=np.bool_),
        out_low_ti=np.full(shape, _NONE, dtype=np.int32),
        out_low_tj=np.full(shape, _NONE, dtype=np.int32),
        out_low_val=np.full(shape, np.nan, dtype=np.float64),
        out_low_dir=np.full(shape, _NONE, dtype=np.int8),
        out_high_ti=np.full(shape, _NONE, dtype=np.int32),
        out_high_tj=np.full(shape, _NONE, dtype=np.int32),
        out_high_val=np.full(shape, np.nan, dtype=np.float64),
        out_high_dir=np.full(shape, _NONE, dtype=np.int8),
        in_upper=[[[] for _ in range(n + 1)] for _ in range(m + 1)],
        in_diagonal_upper=[[[] for _ in range(n + 1)] for _ in range(m + 1)],
        in_diagonal_lower=[[[] for _ in range(n + 1)] for _ in range(m + 1)],
        in_right=[[[] for _ in range(n + 1)] for _ in range(m + 1)],
    )
    g.depth[0, 0] = 0

    for i in range(1, m + 1):
        _attach(g, i - 1, 0, i, 0)
    for j in range(1, n + 1):
        _attach(g, 0, j - 1, 0, j)

    for i in range(1, m + 1):
        for j in range(1, n + 1):
            _add_to_tree(g, i, j)

    return _extract_matching(g, m, n)


# ---------------------------------------------------------------------------
# Vectorised distance matrix (the one bulk numpy win)
# ---------------------------------------------------------------------------

def _compute_dist(curve1, curve2):
    c1x = np.array([p.x for p in curve1], dtype=np.float64)
    c1y = np.array([p.y for p in curve1], dtype=np.float64)
    c2x = np.array([p.x for p in curve2], dtype=np.float64)
    c2y = np.array([p.y for p in curve2], dtype=np.float64)
    dx = c1x[:, np.newaxis] - c2x[np.newaxis, :]
    dy = c1y[:, np.newaxis] - c2y[np.newaxis, :]
    return np.sqrt(dx * dx + dy * dy)


# ---------------------------------------------------------------------------
# Tree construction
# ---------------------------------------------------------------------------

def _add_to_tree(g, i, j):
    ai, aj = i - 1, j        # A: upper neighbour
    bi, bj = i - 1, j - 1   # B: diagonal neighbour
    ci, cj = i,     j - 1   # C: right neighbour
    di, dj = i,     j        # D: current node

    (pi, pj), extra_info = _select_parent(g, ai, aj, bi, bj, ci, cj)
    _attach(g, pi, pj, di, dj)

    if not (g.child_upper[bi, bj] or g.child_diagonal[bi, bj] or g.child_right[bi, bj]):
        is_high = _get_deepest_shortcut(g, bi, bj)
        if is_high:
            dpb_i = int(g.out_high_ti[bi, bj])
            dpb_j = int(g.out_high_tj[bi, bj])
            s_dir = Direction(int(g.out_high_dir[bi, bj]))
        else:
            dpb_i = int(g.out_low_ti[bi, bj])
            dpb_j = int(g.out_low_tj[bi, bj])
            s_dir = Direction(int(g.out_low_dir[bi, bj]))

        _detach_dead_path(g, bi, bj, dpb_i, dpb_j, s_dir)
        followup = _extend_shortcuts(g, dpb_i, dpb_j, s_dir)
        _adjust_ncas(extra_info, dpb_i, dpb_j, followup)

    extra_info['selectedParent'] = (pi, pj)
    _update_shortcuts(g, i, j, extra_info, ai, aj, bi, bj, ci, cj, di, dj)


def _attach(g, pi, pj, ci, cj):
    g.parent_i[ci, cj] = pi
    g.parent_j[ci, cj] = pj
    g.depth[ci, cj] = g.depth[pi, pj] + 1

    if ci == pi and cj == pj + 1:
        g.child_upper[pi, pj] = True
    elif ci == pi + 1 and cj == pj + 1:
        g.child_diagonal[pi, pj] = True
    elif ci == pi + 1 and cj == pj:
        g.child_right[pi, pj] = True
    else:
        raise ValueError(f"Invalid child-parent: child ({ci},{cj}), parent ({pi},{pj})")


# ---------------------------------------------------------------------------
# Parent selection
# ---------------------------------------------------------------------------

def _select_parent(g, ai, aj, bi, bj, ci, cj):
    max_A_AB, max_B_AB, nca_AB, dir_A_AB, dir_B_AB = _get_max_dist_to_nca(g, ai, aj, bi, bj)
    max_B_BC, max_C_BC, nca_BC, dir_B_BC, dir_C_BC = _get_max_dist_to_nca(g, bi, bj, ci, cj)
    max_A_AC, max_C_AC, nca_AC, dir_A_AC, dir_C_AC = _get_max_dist_to_nca(g, ai, aj, ci, cj)

    A_over_B = max_A_AB <= max_B_AB
    B_over_C = max_B_BC <= max_C_BC
    A_over_C = max_A_AC <= max_C_AC

    extra_info = {
        'max_A_AB': max_A_AB, 'max_B_AB': max_B_AB, 'nca_AB': nca_AB,
        'dir_A_AB': dir_A_AB, 'dir_B_AB': dir_B_AB,
        'max_B_BC': max_B_BC, 'max_C_BC': max_C_BC, 'nca_BC': nca_BC,
        'dir_B_BC': dir_B_BC, 'dir_C_BC': dir_C_BC,
        'max_A_AC': max_A_AC, 'max_C_AC': max_C_AC, 'nca_AC': nca_AC,
        'dir_A_AC': dir_A_AC, 'dir_C_AC': dir_C_AC,
    }

    if A_over_B and A_over_C:
        return (ai, aj), extra_info
    elif not A_over_B and B_over_C:
        return (bi, bj), extra_info
    else:
        return (ci, cj), extra_info


def _get_max_dist_to_nca(g, ui, uj, vi, vj):
    """Return (max_u, max_v, nca, final_dir_u, final_dir_v) for nodes u and v."""
    max_u = float('-inf')
    max_v = float('-inf')
    final_dir_u = None
    final_dir_v = None

    while (ui, uj) != (vi, vj):
        if int(g.depth[vi, vj]) > int(g.depth[ui, uj]):
            if int(g.out_high_ti[vi, vj]) != _NONE:
                max_v = max(max_v, float(g.out_high_val[vi, vj]))
                final_dir_v = Direction(int(g.out_high_dir[vi, vj]))
                vi, vj = int(g.out_high_ti[vi, vj]), int(g.out_high_tj[vi, vj])
            else:
                max_v = max(max_v, float(g.dist[vi, vj]))
                final_dir_v = _get_direction(vi, vj, int(g.parent_i[vi, vj]), int(g.parent_j[vi, vj]))
                vi, vj = int(g.parent_i[vi, vj]), int(g.parent_j[vi, vj])
        else:
            if int(g.out_low_ti[ui, uj]) != _NONE:
                max_u = max(max_u, float(g.out_low_val[ui, uj]))
                final_dir_u = Direction(int(g.out_low_dir[ui, uj]))
                ui, uj = int(g.out_low_ti[ui, uj]), int(g.out_low_tj[ui, uj])
            else:
                max_u = max(max_u, float(g.dist[ui, uj]))
                final_dir_u = _get_direction(ui, uj, int(g.parent_i[ui, uj]), int(g.parent_j[ui, uj]))
                ui, uj = int(g.parent_i[ui, uj]), int(g.parent_j[ui, uj])

    return max_u, max_v, (ui, uj), final_dir_u, final_dir_v


# ---------------------------------------------------------------------------
# Shortcut management
# ---------------------------------------------------------------------------

def _update_shortcuts(g, i, j, extra_info, ai, aj, bi, bj, ci, cj, di, dj):
    AB = int(g.parent_i[ai, aj]) == bi and int(g.parent_j[ai, aj]) == bj
    BC = int(g.parent_i[ci, cj]) == bi and int(g.parent_j[ci, cj]) == bj

    sp = extra_info['selectedParent']

    if sp == (ai, aj):
        if AB and BC:
            _add_shortcut(g, ai, aj, False, bi, bj, float(g.dist[ai, aj]), Direction.DOWN)
            _add_shortcut(g, ci, cj, True,  bi, bj, float(g.dist[ci, cj]), Direction.LEFT)
            _add_shortcut(g, di, dj, False, bi, bj, max(float(g.dist[ai, aj]), float(g.dist[di, dj])), Direction.DOWN)
        elif AB:
            _add_shortcut(g, ai, aj, False, *extra_info['nca_AC'], extra_info['max_A_AC'], extra_info['dir_A_AC'])
            _add_shortcut(g, di, dj, False, *extra_info['nca_AC'], max(extra_info['max_A_AC'], float(g.dist[di, dj])), extra_info['dir_A_AC'])
        elif BC:
            _add_shortcut(g, ci, cj, True,  *extra_info['nca_AC'], extra_info['max_C_AC'], extra_info['dir_C_AC'])
            _add_shortcut(g, di, dj, False, *extra_info['nca_AC'], max(extra_info['max_A_AC'], float(g.dist[di, dj])), extra_info['dir_A_AC'])
        else:
            _add_shortcut(g, di, dj, False, *extra_info['nca_AB'], max(extra_info['max_A_AB'], float(g.dist[di, dj])), extra_info['dir_A_AB'])

    elif sp == (bi, bj):
        if AB and BC:
            _add_shortcut(g, ai, aj, False, bi, bj, float(g.dist[ai, aj]), Direction.DOWN)
            _add_shortcut(g, ci, cj, True,  bi, bj, float(g.dist[ci, cj]), Direction.LEFT)
            _add_shortcut(g, di, dj, True,  bi, bj, float(g.dist[di, dj]), Direction.DIAGONAL_UPPER)
            _add_shortcut(g, di, dj, False, bi, bj, float(g.dist[di, dj]), Direction.DIAGONAL_LOWER)
        elif AB:
            _add_shortcut(g, ai, aj, False, bi, bj, float(g.dist[ai, aj]), Direction.DOWN)
            _add_shortcut(g, di, dj, True,  bi, bj, float(g.dist[di, dj]), Direction.DIAGONAL_UPPER)
            _add_shortcut(g, di, dj, False, *extra_info['nca_AC'], max(extra_info['max_B_BC'], float(g.dist[di, dj])), extra_info['dir_B_BC'])
        elif BC:
            _add_shortcut(g, ci, cj, True,  bi, bj, float(g.dist[ci, cj]), Direction.LEFT)
            _add_shortcut(g, di, dj, True,  *extra_info['nca_AC'], max(extra_info['max_B_AB'], float(g.dist[di, dj])), extra_info['dir_B_AB'])
            _add_shortcut(g, di, dj, False, bi, bj, float(g.dist[di, dj]), Direction.DIAGONAL_LOWER)
        else:
            _add_shortcut(g, di, dj, True,  *extra_info['nca_AB'], max(extra_info['max_B_AB'], float(g.dist[di, dj])), extra_info['dir_B_AB'])
            _add_shortcut(g, di, dj, False, *extra_info['nca_BC'], max(extra_info['max_B_BC'], float(g.dist[di, dj])), extra_info['dir_B_BC'])

    elif sp == (ci, cj):
        if AB and BC:
            _add_shortcut(g, ai, aj, False, bi, bj, float(g.dist[ai, aj]), Direction.DOWN)
            _add_shortcut(g, ci, cj, True,  bi, bj, float(g.dist[ci, cj]), Direction.LEFT)
            _add_shortcut(g, di, dj, True,  bi, bj, max(float(g.dist[ci, cj]), float(g.dist[di, dj])), Direction.LEFT)
        elif AB:
            _add_shortcut(g, ai, aj, False, *extra_info['nca_AC'], extra_info['max_A_AC'], extra_info['dir_A_AC'])
            _add_shortcut(g, di, dj, True,  *extra_info['nca_AC'], max(extra_info['max_C_AC'], float(g.dist[di, dj])), extra_info['dir_C_AC'])
        elif BC:
            _add_shortcut(g, ci, cj, True,  *extra_info['nca_AC'], extra_info['max_C_AC'], extra_info['dir_C_AC'])
            _add_shortcut(g, di, dj, True,  *extra_info['nca_AC'], max(extra_info['max_C_AC'], float(g.dist[di, dj])), extra_info['dir_C_AC'])
        else:
            _add_shortcut(g, di, dj, True,  *extra_info['nca_BC'], max(extra_info['max_C_BC'], float(g.dist[di, dj])), extra_info['dir_C_BC'])


def _add_shortcut(g, si, sj, is_high, ti, tj, val, dir_enum):
    dir_val = dir_enum.value
    if is_high:
        g.out_high_ti[si, sj] = ti
        g.out_high_tj[si, sj] = tj
        g.out_high_val[si, sj] = val
        g.out_high_dir[si, sj] = dir_val
    else:
        g.out_low_ti[si, sj] = ti
        g.out_low_tj[si, sj] = tj
        g.out_low_val[si, sj] = val
        g.out_low_dir[si, sj] = dir_val

    entry = (si, sj, is_high)
    if dir_enum == Direction.DOWN:
        g.in_upper[ti][tj].append(entry)
    elif dir_enum == Direction.DIAGONAL_UPPER:
        g.in_diagonal_upper[ti][tj].append(entry)
    elif dir_enum == Direction.DIAGONAL_LOWER:
        g.in_diagonal_lower[ti][tj].append(entry)
    elif dir_enum == Direction.LEFT:
        g.in_right[ti][tj].append(entry)


# ---------------------------------------------------------------------------
# Dead path handling
# ---------------------------------------------------------------------------

def _detach_dead_path(g, bi, bj, dpb_i, dpb_j, final_direction):
    if int(g.out_high_ti[bi, bj]) != _NONE:
        ti = int(g.out_high_ti[bi, bj])
        tj = int(g.out_high_tj[bi, bj])
        _remove_from_in_list(g, ti, tj, Direction(int(g.out_high_dir[bi, bj])), (bi, bj, True))

    if int(g.out_low_ti[bi, bj]) != _NONE:
        ti = int(g.out_low_ti[bi, bj])
        tj = int(g.out_low_tj[bi, bj])
        _remove_from_in_list(g, ti, tj, Direction(int(g.out_low_dir[bi, bj])), (bi, bj, False))

    if final_direction == Direction.DOWN:
        g.in_upper[dpb_i][dpb_j] = []
        g.child_upper[dpb_i, dpb_j] = False
    elif final_direction in (Direction.DIAGONAL_UPPER, Direction.DIAGONAL_LOWER):
        g.in_diagonal_upper[dpb_i][dpb_j] = []
        g.in_diagonal_lower[dpb_i][dpb_j] = []
        g.child_diagonal[dpb_i, dpb_j] = False
    elif final_direction == Direction.LEFT:
        g.in_right[dpb_i][dpb_j] = []
        g.child_right[dpb_i, dpb_j] = False


def _remove_from_in_list(g, ti, tj, direction, entry):
    if direction == Direction.DOWN:
        g.in_upper[ti][tj].remove(entry)
    elif direction == Direction.DIAGONAL_UPPER:
        g.in_diagonal_upper[ti][tj].remove(entry)
    elif direction == Direction.DIAGONAL_LOWER:
        g.in_diagonal_lower[ti][tj].remove(entry)
    elif direction == Direction.LEFT:
        g.in_right[ti][tj].remove(entry)


def _extend_shortcuts(g, dpb_i, dpb_j, final_direction):
    """Extend shortcuts that pass through the dead path base after it is detached.

    Returns a dict {ti, tj, val, dir} describing the followup shortcut, or None.
    """
    if final_direction == Direction.DOWN:
        if g.child_diagonal[dpb_i, dpb_j]:
            _extend_shortcuts_to(
                g, g.in_diagonal_upper[dpb_i][dpb_j],
                int(g.out_high_ti[dpb_i, dpb_j]), int(g.out_high_tj[dpb_i, dpb_j]),
                float(g.out_high_val[dpb_i, dpb_j]), int(g.out_high_dir[dpb_i, dpb_j]),
            )
        elif g.child_right[dpb_i, dpb_j]:
            _extend_shortcuts_to(
                g, g.in_right[dpb_i][dpb_j],
                int(g.out_high_ti[dpb_i, dpb_j]), int(g.out_high_tj[dpb_i, dpb_j]),
                float(g.out_high_val[dpb_i, dpb_j]), int(g.out_high_dir[dpb_i, dpb_j]),
            )
        if int(g.out_high_ti[dpb_i, dpb_j]) != _NONE:
            return {'ti': int(g.out_high_ti[dpb_i, dpb_j]), 'tj': int(g.out_high_tj[dpb_i, dpb_j]),
                    'val': float(g.out_high_val[dpb_i, dpb_j]), 'dir': int(g.out_high_dir[dpb_i, dpb_j])}
        return None

    if final_direction in (Direction.DIAGONAL_UPPER, Direction.DIAGONAL_LOWER):
        if g.child_right[dpb_i, dpb_j] and not g.child_upper[dpb_i, dpb_j]:
            _extend_shortcuts_to(
                g, g.in_right[dpb_i][dpb_j],
                int(g.out_high_ti[dpb_i, dpb_j]), int(g.out_high_tj[dpb_i, dpb_j]),
                float(g.out_high_val[dpb_i, dpb_j]), int(g.out_high_dir[dpb_i, dpb_j]),
            )
            return {'ti': int(g.out_high_ti[dpb_i, dpb_j]), 'tj': int(g.out_high_tj[dpb_i, dpb_j]),
                    'val': float(g.out_high_val[dpb_i, dpb_j]), 'dir': int(g.out_high_dir[dpb_i, dpb_j])}
        elif g.child_upper[dpb_i, dpb_j] and not g.child_right[dpb_i, dpb_j]:
            _extend_shortcuts_to(
                g, g.in_upper[dpb_i][dpb_j],
                int(g.out_low_ti[dpb_i, dpb_j]), int(g.out_low_tj[dpb_i, dpb_j]),
                float(g.out_low_val[dpb_i, dpb_j]), int(g.out_low_dir[dpb_i, dpb_j]),
            )
            return {'ti': int(g.out_low_ti[dpb_i, dpb_j]), 'tj': int(g.out_low_tj[dpb_i, dpb_j]),
                    'val': float(g.out_low_val[dpb_i, dpb_j]), 'dir': int(g.out_low_dir[dpb_i, dpb_j])}
        return None

    if final_direction == Direction.LEFT:
        if g.child_diagonal[dpb_i, dpb_j]:
            _extend_shortcuts_to(
                g, g.in_diagonal_lower[dpb_i][dpb_j],
                int(g.out_low_ti[dpb_i, dpb_j]), int(g.out_low_tj[dpb_i, dpb_j]),
                float(g.out_low_val[dpb_i, dpb_j]), int(g.out_low_dir[dpb_i, dpb_j]),
            )
        elif g.child_upper[dpb_i, dpb_j]:
            _extend_shortcuts_to(
                g, g.in_upper[dpb_i][dpb_j],
                int(g.out_low_ti[dpb_i, dpb_j]), int(g.out_low_tj[dpb_i, dpb_j]),
                float(g.out_low_val[dpb_i, dpb_j]), int(g.out_low_dir[dpb_i, dpb_j]),
            )
        if int(g.out_low_ti[dpb_i, dpb_j]) != _NONE:
            return {'ti': int(g.out_low_ti[dpb_i, dpb_j]), 'tj': int(g.out_low_tj[dpb_i, dpb_j]),
                    'val': float(g.out_low_val[dpb_i, dpb_j]), 'dir': int(g.out_low_dir[dpb_i, dpb_j])}
        return None

    return None


def _extend_shortcuts_to(g, entries, fup_ti, fup_tj, fup_val, fup_dir):
    dir_enum = Direction(fup_dir)
    for (si, sj, is_high) in list(entries):
        if is_high:
            new_val = max(float(g.out_high_val[si, sj]), fup_val)
            g.out_high_ti[si, sj] = fup_ti
            g.out_high_tj[si, sj] = fup_tj
            g.out_high_val[si, sj] = new_val
            g.out_high_dir[si, sj] = fup_dir
        else:
            new_val = max(float(g.out_low_val[si, sj]), fup_val)
            g.out_low_ti[si, sj] = fup_ti
            g.out_low_tj[si, sj] = fup_tj
            g.out_low_val[si, sj] = new_val
            g.out_low_dir[si, sj] = fup_dir

        entry = (si, sj, is_high)
        if dir_enum == Direction.DOWN:
            g.in_upper[fup_ti][fup_tj].append(entry)
        elif dir_enum == Direction.DIAGONAL_UPPER:
            g.in_diagonal_upper[fup_ti][fup_tj].append(entry)
        elif dir_enum == Direction.DIAGONAL_LOWER:
            g.in_diagonal_lower[fup_ti][fup_tj].append(entry)
        elif dir_enum == Direction.LEFT:
            g.in_right[fup_ti][fup_tj].append(entry)


def _adjust_ncas(extra_info, dpb_i, dpb_j, followup):
    if followup is None:
        return

    fup_ij = (followup['ti'], followup['tj'])
    fup_val = followup['val']
    fup_dir = Direction(followup['dir'])

    if extra_info['nca_AB'] == (dpb_i, dpb_j):
        extra_info['nca_AB'] = fup_ij
        extra_info['max_A_AB'] = max(extra_info['max_A_AB'], fup_val)
        extra_info['max_B_AB'] = max(extra_info['max_B_AB'], fup_val)
        extra_info['dir_A_AB'] = fup_dir
        extra_info['dir_B_AB'] = fup_dir
    if extra_info['nca_BC'] == (dpb_i, dpb_j):
        extra_info['nca_BC'] = fup_ij
        extra_info['max_B_BC'] = max(extra_info['max_B_BC'], fup_val)
        extra_info['max_C_BC'] = max(extra_info['max_C_BC'], fup_val)
        extra_info['dir_B_BC'] = fup_dir
        extra_info['dir_C_BC'] = fup_dir
    if extra_info['nca_AC'] == (dpb_i, dpb_j):
        extra_info['nca_AC'] = fup_ij
        extra_info['max_A_AC'] = max(extra_info['max_A_AC'], fup_val)
        extra_info['max_C_AC'] = max(extra_info['max_C_AC'], fup_val)
        extra_info['dir_A_AC'] = fup_dir
        extra_info['dir_C_AC'] = fup_dir


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_deepest_shortcut(g, i, j):
    """Return True if out_high points to a deeper ancestor than out_low, False otherwise."""
    has_low  = int(g.out_low_ti[i, j])  != _NONE
    has_high = int(g.out_high_ti[i, j]) != _NONE
    d_low  = int(g.depth[int(g.out_low_ti[i, j]),  int(g.out_low_tj[i, j])])  if has_low  else float('-inf')
    d_high = int(g.depth[int(g.out_high_ti[i, j]), int(g.out_high_tj[i, j])]) if has_high else float('-inf')
    return d_high > d_low


def _get_direction(ci, cj, pi, pj):
    if ci == pi + 1 and cj == pj:
        return Direction.LEFT
    if ci == pi and cj == pj + 1:
        return Direction.DOWN
    raise ValueError(f"Invalid child-parent: child ({ci},{cj}), parent ({pi},{pj})")


def _extract_matching(g, m, n):
    path = []
    max_d = float('-inf')
    ci, cj = m, n
    while ci != _NONE:
        path.append((ci, cj))
        max_d = max(max_d, float(g.dist[ci, cj]))
        ci, cj = int(g.parent_i[ci, cj]), int(g.parent_j[ci, cj])
    path.reverse()
    return path, max_d
