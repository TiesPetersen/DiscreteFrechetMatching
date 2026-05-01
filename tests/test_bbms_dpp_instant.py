import math
import random

import pytest

from src.Point import Point
from src.BBMS_dpp_instant.main import BBMS_dpp_instant
from src.BBMS_dpp_instant_opt.main import BBMS_dpp_instant_opt
from src.BBMS_inter.main import BBMS_inter
from src.DynamicProgramming.main import DynamicProgramming


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_points(coords):
    return [Point(x, y) for x, y in coords]


def _frechet_from_matching(c1, c2, matching):
    return max(
        math.sqrt((c1[i].x - c2[j].x) ** 2 + (c1[i].y - c2[j].y) ** 2)
        for i, j in matching
    )


def _is_valid_matching(matching, m, n):
    if not matching:
        return False
    if matching[0] != (0, 0):
        return False
    if matching[-1] != (m, n):
        return False
    for k in range(len(matching) - 1):
        di = matching[k + 1][0] - matching[k][0]
        dj = matching[k + 1][1] - matching[k][1]
        if not (0 <= di <= 1 and 0 <= dj <= 1 and di + dj > 0):
            return False
    return True


def _random_curves(m_len, n_len, seed, lo=0, hi=20):
    rng = random.Random(seed)
    c1 = _make_points([(rng.uniform(lo, hi), rng.uniform(lo, hi)) for _ in range(m_len)])
    c2 = _make_points([(rng.uniform(lo, hi), rng.uniform(lo, hi)) for _ in range(n_len)])
    return c1, c2


# ---------------------------------------------------------------------------
# Known-geometry tests (exact answers, unique matching)
# ---------------------------------------------------------------------------

def test_two_point_identical():
    c1 = _make_points([(0, 0), (1, 0)])
    c2 = _make_points([(0, 0), (1, 0)])
    matching, fd = BBMS_dpp_instant(c1, c2)
    assert fd == pytest.approx(0.0)
    assert matching == [(0, 0), (1, 1)]


def test_two_point_offset_parallel():
    c1 = _make_points([(0, 0), (1, 0)])
    c2 = _make_points([(0, 1), (1, 1)])
    matching, fd = BBMS_dpp_instant(c1, c2)
    assert fd == pytest.approx(1.0)


def test_two_point_perpendicular():
    c1 = _make_points([(0, 0), (0, 3)])
    c2 = _make_points([(0, 0), (3, 0)])
    matching, fd = BBMS_dpp_instant(c1, c2)
    assert fd == pytest.approx(math.sqrt(18))


def test_same_curve_zero():
    c = _make_points([(0, 0), (3, 1), (6, 0), (9, 2)])
    matching, fd = BBMS_dpp_instant(c, c)
    assert fd == pytest.approx(0.0)
    assert matching == [(0, 0), (1, 1), (2, 2), (3, 3)]


# ---------------------------------------------------------------------------
# Structural correctness: matching must be a valid monotone path
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("seed,m_len,n_len", [
    (0, 2, 2), (1, 2, 5), (2, 5, 2), (3, 5, 5),
    (4, 10, 7), (5, 7, 10), (6, 3, 3), (7, 15, 4),
])
def test_matching_validity(seed, m_len, n_len):
    c1, c2 = _random_curves(m_len, n_len, seed)
    matching, _ = BBMS_dpp_instant(c1, c2)
    assert _is_valid_matching(matching, m_len - 1, n_len - 1)


# ---------------------------------------------------------------------------
# Self-consistency: fd must equal max distance along the returned matching
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("seed", range(20))
def test_frechet_equals_max_matching_distance(seed):
    rng = random.Random(seed + 100)
    c1, c2 = _random_curves(rng.randint(2, 15), rng.randint(2, 15), seed + 100)
    matching, fd = BBMS_dpp_instant(c1, c2)
    assert fd == pytest.approx(_frechet_from_matching(c1, c2, matching), rel=1e-9)


# ---------------------------------------------------------------------------
# Correctness: must agree with DynamicProgramming ground truth
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("seed", range(30))
def test_vs_dynamic_programming(seed):
    rng = random.Random(seed + 200)
    c1, c2 = _random_curves(rng.randint(2, 20), rng.randint(2, 20), seed + 200)
    _, fd = BBMS_dpp_instant(c1, c2)
    assert fd == pytest.approx(DynamicProgramming(c1, c2), rel=1e-9)


# ---------------------------------------------------------------------------
# Agreement with BBMS_inter (distance only — multiple optimal matchings may exist)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("seed", range(30))
def test_vs_bbms_inter(seed):
    rng = random.Random(seed + 300)
    c1, c2 = _random_curves(rng.randint(2, 20), rng.randint(2, 20), seed + 300)
    _, fd = BBMS_dpp_instant(c1, c2)
    _, inter_fd = BBMS_inter(c1, c2)
    assert fd == pytest.approx(inter_fd, rel=1e-9)


# ---------------------------------------------------------------------------
# Stress: various sizes, all three checks combined
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("m_len,n_len,seed", [
    (2,  2,  10), (2,  10, 11), (10, 2,  12),
    (10, 10, 13), (20, 20, 14), (50, 3,  15),
    (3,  50, 16), (30, 30, 17), (50, 50, 18),
])
def test_random_various_sizes(m_len, n_len, seed):
    c1, c2 = _random_curves(m_len, n_len, seed)
    matching, fd = BBMS_dpp_instant(c1, c2)
    assert _is_valid_matching(matching, m_len - 1, n_len - 1)
    assert fd == pytest.approx(_frechet_from_matching(c1, c2, matching), rel=1e-9)
    assert fd == pytest.approx(DynamicProgramming(c1, c2), rel=1e-9)


# ---------------------------------------------------------------------------
# BBMS_dpp_instant_opt (numpy) — must agree exactly with the reference on all cases
# ---------------------------------------------------------------------------

def test_opt_two_point_identical():
    c1 = _make_points([(0, 0), (1, 0)])
    c2 = _make_points([(0, 0), (1, 0)])
    matching, fd = BBMS_dpp_instant_opt(c1, c2)
    assert fd == pytest.approx(0.0)
    assert matching == [(0, 0), (1, 1)]


def test_opt_same_curve_zero():
    c = _make_points([(0, 0), (3, 1), (6, 0), (9, 2)])
    matching, fd = BBMS_dpp_instant_opt(c, c)
    assert fd == pytest.approx(0.0)
    assert matching == [(0, 0), (1, 1), (2, 2), (3, 3)]


@pytest.mark.parametrize("seed", range(40))
def test_opt_agrees_with_reference(seed):
    rng = random.Random(seed + 500)
    c1, c2 = _random_curves(rng.randint(2, 25), rng.randint(2, 25), seed + 500)
    matching_ref, fd_ref = BBMS_dpp_instant(c1, c2)
    matching_opt, fd_opt = BBMS_dpp_instant_opt(c1, c2)
    assert fd_opt == pytest.approx(fd_ref, rel=1e-9)
    assert _is_valid_matching(matching_opt, len(c1) - 1, len(c2) - 1)
    assert fd_opt == pytest.approx(_frechet_from_matching(c1, c2, matching_opt), rel=1e-9)


@pytest.mark.parametrize("m_len,n_len,seed", [
    (2,  2,  20), (2,  10, 21), (10, 2,  22),
    (10, 10, 23), (20, 20, 24), (50, 3,  25),
    (3,  50, 26), (30, 30, 27), (50, 50, 28),
])
def test_opt_various_sizes(m_len, n_len, seed):
    c1, c2 = _random_curves(m_len, n_len, seed)
    matching, fd = BBMS_dpp_instant_opt(c1, c2)
    assert _is_valid_matching(matching, m_len - 1, n_len - 1)
    assert fd == pytest.approx(_frechet_from_matching(c1, c2, matching), rel=1e-9)
    assert fd == pytest.approx(DynamicProgramming(c1, c2), rel=1e-9)
