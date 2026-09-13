"""Nonlinear deformation model (8.1.2.7) via concreteproperties vs Đoàn Thị Quỳnh Mai VD 2.9-2.12."""

import pytest
from conftest import grp

pytest.importorskip("concreteproperties")
from scipy.optimize import brentq  # noqa: E402

from tcvn5574 import RectangularBeamSection, check_beam_flexure, get_concrete, get_rebar  # noqa: E402
from tcvn5574.nonlinear import to_concrete_section  # noqa: E402


def close(a, b, tol=0.01):
    return abs(a - b) <= tol * abs(b)


def capacity(sec, conc, steel):
    code, _ = to_concrete_section(sec, conc, steel)
    return code.ultimate_bending_capacity()


def test_vd211_rectangle_capacity():
    r = capacity(RectangularBeamSection(220, 500, tensile_rebar=grp((3, 22, 36), (2, 22, 88))), "B20", "CB300-V")
    assert close(r.d_n, 229.76) and close(r.m_x / 1e6, 168.81)
    assert r.governing == "concrete" and r.eps_b_max == 0.0035


def test_vd212_T_capacity():
    sec = RectangularBeamSection(220, 500, bf=500, hf=80, tensile_rebar=grp((3, 22, 36), (2, 22, 88)))
    r = capacity(sec, "B20", "CB300-V")
    assert close(r.d_n, 115.42) and close(r.m_x / 1e6, 196.85)
    assert close(r.eps_s_max, 0.01057, 0.02)  # outer layer strain in the book


def _As_for(M_kNm, make_section):
    """Tension steel area (single bar group, area varied through a fictitious diameter) giving Mu = M."""
    def f(As):
        d = (4 * As / 3.14159265) ** 0.5
        return capacity(make_section(d), "B25", "CB400-V").m_x / 1e6 - M_kNm
    return brentq(f, 500, 5000, xtol=0.5)


def test_vd29_design_with_compression_steel():
    As = _As_for(415, lambda d: RectangularBeamSection(250, 600, tensile_rebar=grp((1, d, 70)), comp_rebar=grp((2, 18, 35))))
    assert close(As, 2743.44, 0.01)


def test_vd210_design_T():
    As = _As_for(222, lambda d: RectangularBeamSection(250, 500, bf=500, hf=70, tensile_rebar=grp((1, d, 40))))
    assert close(As, 1501.82, 0.01)


def test_steel_governed_low_reinforcement():
    """1 bar d12 in a 300x600 B30 beam: eps_s would exceed 0.025 at eps_b = 0.0035 -> steel governs."""
    sec = RectangularBeamSection(300, 600, tensile_rebar=grp((2, 12, 40)))
    r = capacity(sec, "B30", "CB400-V")
    assert r.governing == "steel" and close(r.eps_s_max, 0.025) and r.eps_b_max < 0.0035
    # capacity close to the limit-force method (steel yields in both)
    assert close(r.m_x / 1e6, check_beam_flexure(0, sec, get_concrete("B30"), get_rebar("CB400-V")).Mu_kNm, 0.02)


def test_interaction_and_materials():
    sec = RectangularBeamSection(400, 400, tensile_rebar=grp((3, 20, 45)), comp_rebar=grp((3, 20, 45)))
    code, cs = to_concrete_section(sec, "B25", "CB400-V")
    A_s = 6 * 314.159
    assert close(code.squash_load, 14.5 * (400 * 400 - A_s) + 350 * A_s, 0.005)  # bars displace concrete
    assert close(code.tensile_load, -350 * A_s)
    mi = code.moment_interaction_diagram(n_points=8)
    assert mi.results[0].n == code.squash_load and mi.results[-1].n == code.tensile_load
    r_n = code.ultimate_bending_capacity(n=500e3)
    assert r_n.m_x > code.ultimate_bending_capacity(n=0).m_x  # moderate compression raises Mu
    lt = code.create_concrete_material("B25", long_term=True)
    assert lt.ultimate_stress_strain_profile.get_ultimate_compressive_strain() == 0.0048


# ---------------------------------------------------------------- one-sign strain states, CT (86)
COL = RectangularBeamSection(400, 400, tensile_rebar=grp((3, 20, 45)), comp_rebar=grp((3, 20, 45)))


@pytest.fixture(scope="module")
def column():
    return to_concrete_section(COL, "B25", "CB400-V")


def test_ct86_limit_strain(column):
    code, _ = column
    D = 400.0
    assert code.limit_strain_state(D) == (0.0035, "concrete")
    for d_n in (450.0, 800.0, 4000.0):
        eps2, gov = code.limit_strain_state(d_n)
        eps1 = eps2 * (d_n - D) / d_n  # strain at the opposite face
        assert gov == "one-sign"
        assert abs(eps2 - (0.0035 - (0.0035 - 0.002) * eps1 / eps2)) < 1e-12  # CT (86)
    assert code.limit_strain_state(float("inf")) == (0.002, "one-sign")


def test_axial_force_continuous_and_tends_to_squash(column):
    code, _ = column
    ns = [code.section_actions(d).n for d in (100, 300, 399.9, 400.0, 400.1, 600, 2000, 1e6)]
    assert all(b > a for a, b in zip(ns, ns[1:]))  # monotone in d_n
    assert close(code.section_actions(399.999).n, code.section_actions(400.001).n, 1e-4)  # no jump at D
    assert close(ns[-1], code.squash_load, 0.002)


def test_ct86_reduces_capacity_only_for_one_sign(column):
    code, cs = column
    n_hi = 0.85 * code.squash_load
    new = code.ultimate_bending_capacity(n=n_hi)
    old = cs.ultimate_bending_capacity(n=n_hi)  # concreteproperties: eps_b2 at the extreme fibre always
    # three-linear plateau: lowering eps_b,u barely changes the compressed-edge stress, so the drop is small
    assert new.governing == "one-sign" and new.m_x < old.m_x
    lo = code.ultimate_bending_capacity(n=300e3)
    assert lo.governing == "concrete" and close(lo.m_x, cs.ultimate_bending_capacity(n=300e3).m_x, 0.002)


def test_large_eccentricity_vs_limit_force_method(column):
    """N = 600 kN: x = N/(Rb b) = 103.4 mm (As = A's, both yield), 2a' < x < xi_R h0.
    Mu about the centroid = Rb b x (h0 - x/2) + Rsc A's (h0 - a') - N (h0 - a')/2."""
    code, _ = column
    N, Rb, b, h0, a, As = 600e3, 14.5, 400.0, 355.0, 45.0, 3 * 314.159
    x = N / (Rb * b)
    M_lf = Rb * b * x * (h0 - x / 2) + 350 * As * (h0 - a) - N * (h0 - a) / 2
    assert close(code.ultimate_bending_capacity(n=N).m_x, M_lf, 0.03)


def test_interaction_diagram_shape(column):
    code, _ = column
    mi = code.moment_interaction_diagram(n_points=8)
    n, m = mi.get_results_lists("m_x")
    assert n[0] == code.squash_load and n[-1] == code.tensile_load
    assert abs(m[0]) < 1e-3 * max(m) and abs(m[-1]) < 1e-3 * max(m)  # symmetric section: end points on the axis
    assert all(b < a for a, b in zip(n, n[1:]))
    assert all(v > 0 for v in m[1:-1])
    k = m.index(max(m))
    assert 0 < n[k] < 0.6 * code.squash_load  # peak near the balanced point
    with pytest.raises(ValueError):
        code.ultimate_bending_capacity(n=1.01 * code.squash_load)


def _fibre_integration(d_n, eps2, b=400.0, h=400.0, Rb=14.5, Eb=30000.0, Rs=350.0, Es=2e5, bars=((45, 3), (355, 3)), n=4000):
    """Independent layer integration of the rectangular column (compression +, y from the compressed face)."""
    def sig_c(e):
        e1 = 0.6 * Rb / Eb
        if e <= 0:
            return 0.0
        if e <= e1:
            return Eb * e
        if e < 0.002:
            return (0.4 * (e - e1) / (0.002 - e1) + 0.6) * Rb
        return Rb
    A_bar = 314.159265
    N = M = 0.0
    dy = h / n
    for i in range(n):
        y = (i + 0.5) * dy
        e = eps2 * (d_n - y) / d_n
        N += sig_c(e) * b * dy
        M += sig_c(e) * b * dy * (h / 2 - y)
    for y, k in bars:
        e = eps2 * (d_n - y) / d_n
        s = max(-Rs, min(Rs, Es * e))
        # bars displace concrete in the concreteproperties model
        s_net = s - sig_c(e)
        N += s_net * k * A_bar
        M += s_net * k * A_bar * (h / 2 - y)
    return N, M


@pytest.mark.parametrize("d_n", [250.0, 520.0, 1500.0])
def test_section_actions_vs_independent_fibre_integration(column, d_n):
    code, _ = column
    r = code.section_actions(d_n)
    N, M = _fibre_integration(d_n, r.eps_b_max)
    assert close(r.n, N, 0.003) and close(abs(r.m_x), abs(M), 0.005)


def test_biaxial_smoke(column):
    code, _ = column
    bb = code.biaxial_bending_diagram(n=500e3, n_points=4)
    assert len(bb.results) == 5 and all(r.m_xy > 0 for r in bb.results)


# ---------------------------------------------------------------- unsymmetric T section, both branches
T_SEC = RectangularBeamSection(300, 600, bf=900, hf=120, tensile_rebar=grp((4, 22, 45), (2, 20, 90)), comp_rebar=grp((2, 18, 40)))


@pytest.fixture(scope="module")
def tee():
    return to_concrete_section(T_SEC, "B30", "CB400-V")


def test_branches_meet_at_end_points(tee):
    import math

    code, _ = tee
    p, q = code.moment_interaction_diagram(0.0, 6), code.moment_interaction_diagram(math.pi, 6)
    for a, b in ((p.results[0], q.results[0]), (p.results[-1], q.results[-1])):
        assert a.n == b.n and close(a.m_x, b.m_x, 1e-6)
    assert p.results[0].m_x < -100e6  # plastic centroid below the geometric centroid (steel mostly at the bottom)


def test_theta_pi_equals_flipped_section(tee):
    """Hogging capacity of the T section = sagging capacity of the same section turned upside down."""
    import math

    code, _ = tee
    flipped = RectangularBeamSection(300, 600, bf=900, hf=120, tensile_rebar=grp((2, 18, 40)),
                                     comp_rebar=grp((4, 22, 45), (2, 20, 90)), flange_in_tension=True)
    code_f, _ = to_concrete_section(flipped, "B30", "CB400-V")
    for n in (-300e3, 500e3, 2000e3):
        assert close(-code.ultimate_bending_capacity(theta=math.pi, n=n).m_x, code_f.ultimate_bending_capacity(n=n).m_x, 0.002)


def test_check_point(tee):
    code, _ = tee
    ok, mu_neg, mu_pos = code.check_point(150e3, 320e6)
    assert ok and mu_neg < 0 < 320e6 < mu_pos
    assert not code.check_point(150e3, 1.01 * mu_pos)[0]
    assert not code.check_point(150e3, 1.01 * mu_neg)[0]
    assert not code.check_point(1.01 * code.squash_load, 0.0)[0]


def test_figures_png(tee):
    import math

    from tcvn5574.report.figures import limit_state_figure, mn_figure

    code, _ = tee
    for th, n in ((0.0, 150e3), (math.pi, 800e3), (0.0, 0.95 * code.squash_load)):
        png = limit_state_figure(code, code.ultimate_bending_capacity(theta=th, n=n)).getvalue()
        assert png[1:4] == b"PNG"
    png = mn_figure([code.moment_interaction_diagram(0.0, 6), code.moment_interaction_diagram(math.pi, 6)], [(150, 320, "P", True)]).getvalue()
    assert png[1:4] == b"PNG" and len(png) > 20000
