"""Concentric compression (8.1.2.4.3, Bảng 16) and biaxial eccentric compression (8.1.2.7.6)."""

import math

import pytest

from tcvn5574 import RectangularBeamSection, get_concrete, get_rebar
from tcvn5574.column import check_column_axial, design_column_axial, phi_axial
from tcvn5574.sections.column import RectangularColumnSection

B20, B25 = get_concrete("B20"), get_concrete("B25")
CB300, CB400 = get_rebar("CB300-V"), get_rebar("CB400-V")


def close(a, b, tol=0.01):
    return abs(a - b) <= tol * abs(b)


# ---------------------------------------------------------------- concentric
def test_phi_table16_and_short_term():
    assert phi_axial(6, 25) == 0.92 and phi_axial(10, 55) == 0.90 and phi_axial(15, 40) == 0.83 and phi_axial(20, 30) == 0.70
    assert phi_axial(20, 60) == 0.65 and phi_axial(4, 20) == 0.92
    assert close(phi_axial(8.25, 20), 0.909, 0.001)  # Mai VD 4.2 interpolation
    assert close(phi_axial(10, 25, long_term=False), 0.90, 1e-9) and close(phi_axial(20, 25, long_term=False), 0.85, 1e-9)
    with pytest.raises(ValueError):
        phi_axial(21, 25)


def test_mai_vd41_capacity():
    r = check_column_axial(900, 250, 300, 1256, get_concrete("B20", gamma_b=0.85), CB300, 3000, h_plane_mm=300)
    assert r.phi == 0.90 and r.A_mm2 == 75000  # mu = 1.67 % < 3 %: gross area
    assert close(r.Nu_kN, 954.05, 0.001) and r.is_safe


def test_mai_vd42_design():
    assert close(design_column_axial(1690, 400, 400, get_concrete("B20", gamma_b=0.85), CB300, 3300), 1176.5, 0.005)


def test_bui_quoc_bao_concrete_alone():
    assert design_column_axial(1260, 350, 350, B25, CB400, 2170) == 0.0  # book: As < 0 -> minimum reinforcement


def test_le_ba_hue_short_term_net_area():
    r = check_column_axial(412.42, 220, 350, 1256.6, B20, CB400, 3600, long_term=False, net_area=True)
    assert close(r.phi, 0.868, 0.001) and close(r.Nu_kN, 1137.8, 0.001) and r.is_safe


cp = pytest.importorskip("concreteproperties")


def test_axial_nonlinear_toggle():
    """nonlinear=True: largest N with (N, N ea) inside the nonlinear envelope (short column, eta = 1)."""
    from tcvn5574.column import check_column

    sec = RectangularBeamSection(400, 400, tensile_rebar=_row(3, 20, 40), comp_rebar=_row(3, 20, 40))
    l0 = 14 * 400 / math.sqrt(12)  # L0/i = 14: no buckling
    lin = check_column_axial(1500, 400, 400, 6 * 314.16, B25, CB400, l0)
    nl = check_column_axial(1500, 400, 400, 6 * 314.16, B25, CB400, l0, nonlinear=True, section=sec)
    assert nl.method.startswith("nonlinear")
    assert check_column(nl.Nu_kN * 0.999, 0, sec, B25, CB400, l0, nonlinear=True).is_safe
    assert not check_column(nl.Nu_kN * 1.01, 0, sec, B25, CB400, l0, nonlinear=True).is_safe
    assert 0.9 < nl.Nu_kN / (lin.Nu_kN / lin.phi) < 1.0  # ea = 13 mm costs a few percent of the squash load


def _row(n, d, a):
    from tcvn5574 import RebarGroup

    return RebarGroup().add_layer(n, d, a)


# ---------------------------------------------------------------- biaxial
COL = RectangularColumnSection.perimeter(400, 600, 45, 3, 4, 22)


def test_perimeter_layout():
    assert len(COL.bars) == 10 and close(COL.As_total, 10 * 380.13, 1e-4)
    assert COL.uniaxial("x").As == pytest.approx(3 * 380.13, rel=1e-4)  # bottom row only
    assert COL.uniaxial("y").As == pytest.approx(4 * 380.13, rel=1e-4)


def test_biaxial_requires_nonlinear():
    from tcvn5574.column import check_column_biaxial

    with pytest.raises(ValueError, match="nonlinear"):
        check_column_biaxial(1000, 100, 50, COL, B25, CB400, 3000, nonlinear=False)


def test_biaxial_slenderness_per_plane():
    from tcvn5574.column import check_column_biaxial

    r = check_column_biaxial(1200, 180, 120, COL, B25, CB400, 4200, N_long_kN=900, Mx_long_kNm=100, My_long_kNm=60)
    for plane, depth, width, Is in ((r.x, 600, 400, COL.Is("x")), (r.y, 400, 600, COL.Is("y"))):
        assert plane.l0_i > 14
        D = plane.kb * B25.Eb * width * depth**3 / 12 + 0.7 * CB400.Es * Is
        assert close(plane.D_Nmm2, D, 1e-9) and close(plane.eta, 1 / (1 - 1200e3 / (math.pi**2 * D / 4200**2)), 1e-9)
    assert close(r.x.M_design_kNm, 1200 * r.x.e0_mm * r.x.eta / 1e3, 1e-9)
    assert r.y.eta > r.x.eta  # weaker plane buckles more


def test_biaxial_reduces_to_uniaxial_and_symmetry():
    from tcvn5574.column import check_column_biaxial
    from tcvn5574.nonlinear import column_to_concrete_section

    short = 2000.0
    code, _ = column_to_concrete_section(COL, "B25", "CB400-V")
    ux = check_column_biaxial(800, 250, 0, COL, B25, CB400, short)
    # My = 0 still carries the random eccentricity of the y plane (8.1.2.2.4): My* = N ea_y eta_y
    assert close(ux.y.M_design_kNm, 800 * ux.y.ea_mm * ux.y.eta / 1e3, 1e-9)
    ok, Mu, _, _ = code.biaxial_check(800e3, ux.x.M_design_kNm * 1e6, ux.y.M_design_kNm * 1e6)
    assert close(ux.Mu_kNm, Mu / 1e6, 1e-6)
    Mu_plane = code.ultimate_bending_capacity(theta=0.0, n=800e3).m_x / 1e6
    assert 0.98 * Mu_plane < ux.Mu_kNm <= Mu_plane  # the small skew costs < 2 %
    urs = [check_column_biaxial(800, sx * 200, 120, COL, B25, CB400, short).utilization_ratio for sx in (1, -1)]
    assert max(urs) - min(urs) < 1e-3 * max(urs)  # doubly symmetric section


def test_biaxial_state_vs_independent_2d_integration():
    """At the governing skew limit state, N / Mx / My from a hand grid integration of the TCVN diagrams."""
    from concreteproperties import utils

    from tcvn5574.nonlinear import column_to_concrete_section

    code, cs = column_to_concrete_section(COL, "B25", "CB400-V")
    ok, Mu, ur, theta = code.biaxial_check(800e3, 200e6, 150e6)
    r = code.ultimate_bending_capacity(theta=theta, n=800e3)
    corners = [(0, 0), (400, 0), (400, 600), (0, 600)]
    v_max = max(utils.global_to_local(theta, x, y)[1] for x, y in corners)

    def strain(x, y):
        return r.eps_b_max * (r.d_n - (v_max - utils.global_to_local(theta, x, y)[1])) / r.d_n

    Rb, Eb, Rs = 14.5, 30000.0, 350.0

    def sc(e):
        e1 = 0.6 * Rb / Eb
        return 0.0 if e <= 0 else Eb * e if e <= e1 else (0.4 * (e - e1) / (0.002 - e1) + 0.6) * Rb if e < 0.002 else Rb

    N = Mx = My = 0.0
    nx, ny = 160, 240
    dx, dy = 400 / nx, 600 / ny
    for i in range(nx):
        for j in range(ny):
            x, y = (i + 0.5) * dx, (j + 0.5) * dy
            f = sc(strain(x, y)) * dx * dy
            N, Mx, My = N + f, Mx + f * (y - 300), My + f * (x - 200)
    for x, y, d in COL.bars:
        e = strain(x, y)
        f = (max(-Rs, min(Rs, 2e5 * e)) - sc(e)) * math.pi * d * d / 4
        N, Mx, My = N + f, Mx + f * (y - 300), My + f * (x - 200)
    assert close(N, 800e3, 0.005) and close(Mx, r.m_x, 0.01) and close(My, r.m_y, 0.01)
    assert close(math.atan2(r.m_y, r.m_x), math.atan2(150, 200), 1e-4)  # capacity vector parallel to the load
