"""Eccentric compression (TCVN 5574:2018 8.1.2.4) vs Đoàn Thị Quỳnh Mai, Chương 4 (VD 4.3-4.9).

The book switches buckling off for l0/h <= 8 (TCVN 5574:2012 rule); TCVN 5574:2018 8.1.2.1.2 uses L0/i <= 14.
Examples the book computes with eta = 1 are therefore run with l0 = 14 i (buckling off) to compare the
section capacity. The book takes phi_L moments about h/2 instead of the bar (h/2 - a) -> ~1% difference.
"""

import math

import pytest
from conftest import grp

from tcvn5574 import RectangularBeamSection, get_concrete, get_rebar
from tcvn5574.column import check_column, design_column_symmetric, random_eccentricity

B20, B25 = get_concrete("B20"), get_concrete("B25")
CB300, CB400 = get_rebar("CB300-V"), get_rebar("CB400-V")


def close(a, b, tol=0.01):
    return abs(a - b) <= tol * abs(b)


def sym(b, h, As, a):
    d = math.sqrt(4 * As / math.pi)  # one equivalent bar per face
    return RectangularBeamSection(b, h, tensile_rebar=grp((1, d, a)), comp_rebar=grp((1, d, a)))


def no_buckling(h):
    return 14 * h / math.sqrt(12)


def M_gh(r, sec):
    """Book's Mgh about the centroid = right side of CT (40) - N (h0 - a')/2."""
    return r.capacity_kNm - r.N_kN * (sec.h0 - sec.a_prime) / 2e3


def test_random_eccentricity():
    assert random_eccentricity(3600, 450) == 15.0 and random_eccentricity(3000, 200) == 10.0
    assert random_eccentricity(12000, 400) == 20.0


def test_vd45_large_eccentricity_not_safe():
    sec = sym(400, 600, 1520, 36)
    r = check_column(810, 390, sec, B20, CB300, l0_mm=no_buckling(600))
    assert r.eta == 1.0 and "large" in r.case
    assert close(r.x_mm, 176.1) and close(M_gh(r, sec), 380.37)
    assert not r.is_safe  # 390 > 380.37


def test_vd46_slenderness_and_capacity():
    sec = RectangularBeamSection(400, 400, tensile_rebar=grp((3, 25, 37.5)), comp_rebar=grp((3, 25, 37.5)))
    r = check_column(750, 220, sec, get_concrete("B25", gamma_b=0.85), CB400, l0_mm=3600, N_long_kN=562.5, M_long_kNm=99)
    assert r.consider_buckling and close(r.e0_mm, 293.3)
    assert close(r.delta_e, 0.733) and close(r.phi_L, 1.57, 0.012) and close(r.kb, 0.092, 0.015)
    assert close(r.D_Nmm2, 16769.8e9) and close(r.Ncr_kN, 12759.9) and close(r.eta, 1.06)
    assert close(r.x_mm, 152.3) and close(M_gh(r, sec), 260.45)
    assert close(r.M_design_kNm, 232.94, 0.01) and r.is_safe  # book rounds eta to 1.06


def test_vd49_small_eccentricity():
    sec = sym(400, 700, 1520, 36)
    r = check_column(3905, 255, sec, B25, CB400, l0_mm=6000, N_long_kN=2928.75, M_long_kNm=114.8)
    assert r.delta_e == 0.15 and close(r.phi_L, 1.70) and close(r.kb, 0.196)
    assert close(r.D_Nmm2, 109022.6e9) and close(r.Ncr_kN, 29858.6) and close(r.eta, 1.15)
    assert "small" in r.case and close(r.x_mm, 554.7)
    assert close(M_gh(r, sec), 351.88) and close(r.M_design_kNm, 293.25) and r.is_safe


@pytest.mark.parametrize(
    "N, M, b, h, conc, steel, book_As, tol",
    [
        (150, 85, 220, 400, "B20", "CB300-V", 733.8, 0.01),  # VD 4.4, x < 2a'
        (2100, 230, 500, 500, ("B20", 0.85), "CB300-V", 1674.8, 0.01),  # VD 4.7, small eccentricity
    ],
)
def test_design_symmetric(N, M, b, h, conc, steel, book_As, tol):
    c = get_concrete(*conc) if isinstance(conc, tuple) else get_concrete(conc)
    As, r = design_column_symmetric(N, M, b, h, 40, c, get_rebar(steel), no_buckling(h))
    assert close(As, book_As, tol) and close(r.utilization_ratio, 1.0, 1e-3)


def test_vd48_book_approximate_design_is_conservative():
    """VD 4.8 uses the approximate symmetric design formulas (xi_1, alpha_s1): 783 mm2.
    The exact CT (40)/(43) solution needs less, and the book's area passes the check."""
    As, _ = design_column_symmetric(4605, 286, 500, 700, 40, B25, CB400, no_buckling(700))
    assert As < 783.0
    assert check_column(4605, 286, sym(500, 700, 783.0, 40), B25, CB400, no_buckling(700)).is_safe


def test_negative_moment_flips_section():
    sec = RectangularBeamSection(400, 600, tensile_rebar=grp((4, 22, 40)), comp_rebar=grp((2, 16, 40)))
    flipped = RectangularBeamSection(400, 600, tensile_rebar=grp((2, 16, 40)), comp_rebar=grp((4, 22, 40)))
    a = check_column(800, -250, sec, B25, CB400, 3000)
    b = check_column(800, 250, flipped, B25, CB400, 3000)
    assert close(a.utilization_ratio, b.utilization_ratio, 1e-9)


def test_unstable_when_N_exceeds_Ncr():
    r = check_column(3000, 50, sym(300, 300, 400, 40), B25, CB400, l0_mm=12000)
    assert r.eta == math.inf and not r.is_safe


# ---------------------------------------------------------------- nonlinear toggle
cp = pytest.importorskip("concreteproperties")


def test_nonlinear_vs_limit_force_vd46():
    sec = RectangularBeamSection(400, 400, tensile_rebar=grp((3, 25, 37.5)), comp_rebar=grp((3, 25, 37.5)))
    kw = dict(l0_mm=3600, N_long_kN=562.5, M_long_kNm=99)
    lf = check_column(750, 220, sec, get_concrete("B25", gamma_b=0.85), CB400, **kw)
    nl = check_column(750, 220, sec, get_concrete("B25", gamma_b=0.85), CB400, nonlinear=True, **kw)
    assert lf.method == "limit_force" and nl.method == "nonlinear"
    assert lf.eta == nl.eta and lf.M_design_kNm == nl.M_design_kNm  # same second-order moment
    assert nl.is_safe and close(nl.Mu_pos_kNm, M_gh(lf, sec), 0.04)  # capacities of the two methods agree


def test_nonlinear_small_eccentricity_vd49():
    """At N = 0.77 N_ult the nonlinear model (three-linear concrete) gives ~11% less than the limit-force
    small-eccentricity formula CT (43); the nonlinear value is confirmed by an independent fibre integration."""
    sec = sym(400, 700, 1520, 36)
    kw = dict(l0_mm=6000, N_long_kN=2928.75, M_long_kNm=114.8)
    lf = check_column(3905, 255, sec, B25, CB400, **kw)
    nl = check_column(3905, 255, sec, B25, CB400, nonlinear=True, **kw)
    assert nl.is_safe and nl.Mu_pos_kNm < M_gh(lf, sec)
    assert close(nl.Mu_pos_kNm, 314.09, 0.005)  # hand layer integration, d_n = 687.1 mm, eps_b = 3.5 per mille
