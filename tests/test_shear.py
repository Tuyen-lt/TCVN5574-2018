"""Shear per TCVN 5574:2018 8.1.3 vs Đoàn Thị Quỳnh Mai VD 3.1-3.4; hanging stirrups."""

from conftest import grp
from tcvn5574 import (
    RectangularBeamSection,
    check_beam_shear,
    design_beam_shear,
    design_hanging_reinforcement,
    get_concrete,
    get_rebar,
)
from tcvn5574.shear.beam_shear import shear_capacity

B20, B25 = get_concrete("B20"), get_concrete("B25")
CB240 = get_rebar("CB240-T")


def close(a, b, tol=0.005):
    return abs(a - b) <= tol * abs(b)


def test_vd31_concentrated_load():
    sec = RectangularBeamSection(300, 600, tensile_rebar=grp((2, 20, 70)))  # h0 = 530
    r = check_beam_shear(195, sec, B20, CB240, 8, 2, 100, a_load_mm=1500)
    assert close(r.Q_max_strut_kN, 548.55)
    assert close(r.Qu_kN * 1e3, 211711) and r.is_safe


def test_vd32_vd33_distributed_load():
    sec = RectangularBeamSection(220, 500, tensile_rebar=grp((2, 20, 50)))  # h0 = 450
    # VD 3.2: Qu(3h0) = 128310 N is the governing value among the sections listed in the book
    assert close(check_beam_shear(120, sec, B20, CB240, 6, 2, 150, q1_kN_per_m=30).Qu_kN * 1e3, 128310)
    r = check_beam_shear(135, sec, B20, CB240, 6, 2, 150, q1_kN_per_m=35)
    assert close(r.Qu_kN * 1e3, 135020) and r.is_safe


def test_vd34_not_safe():
    sec = RectangularBeamSection(200, 400, tensile_rebar=grp((2, 20, 30)))  # h0 = 370
    r = check_beam_shear(114.4, sec, get_concrete("B15"), CB240, 6, 2, 100, q1_kN_per_m=32)
    assert close(r.Qu_kN * 1e3, 113252) and close(r.C_mm, 544, 0.01)
    assert not r.is_safe


def test_2018_formulas_no_phi_n_no_phi_w1():
    """Excel '02.TIES BAR' Shear case recomputed with 2018: strut 0.3 Rb b h0, Qsw = 0.75 qsw C."""
    sec = RectangularBeamSection(300, 600, tensile_rebar=grp((3, 20, 40)))
    r = check_beam_shear(525, sec, B25, get_rebar("SD390"), 12, 2, 100)
    assert close(r.Q_max_strut_kN, 730.8)
    qsw = 2 * 113.097 * 280 / 100
    Mb = 1.5 * 1.05 * 300 * 560**2
    assert close(r.Qu_kN * 1e3, 2 * (Mb * 0.75 * qsw) ** 0.5)  # C* inside [h0, 2h0]


def test_qsw_min_branch_continuous():
    lim = 0.25 * 1.05 * 300
    assert close(shear_capacity(lim * 0.9999, 1.05, 300, 560)[0], shear_capacity(lim, 1.05, 300, 560)[0])
    sec = RectangularBeamSection(300, 600, tensile_rebar=grp((2, 20, 40)))
    assert not check_beam_shear(100, sec, B25, CB240, 6, 2, 300).is_qsw_min_ok


def test_design_round_trip():
    sec = RectangularBeamSection(300, 600, tensile_rebar=grp((2, 20, 40)))
    for Q in (60, 150, 300, 450):
        d = design_beam_shear(Q, sec, B25, CB240, 8, 2)
        chk = check_beam_shear(Q, sec, B25, CB240, 8, 2, d.s_required_mm)
        assert chk.is_safe and d.s_required_mm <= d.s_max_code_mm
    assert not design_beam_shear(60, sec, B25, CB240).is_shear_reinforcement_needed


def test_hanging_full_reaction():
    """Excel 'Stirrup Puncture': P = 131.4 kN, A-I Rsw = 175 -> Atr = 7.51 cm2."""
    r = design_hanging_reinforcement(131.4, 600, 300, 400, 300, get_rebar("A-I"), 8, 2)
    assert close(r.Atr_required_cm2, 7.51, 0.01)
    assert r.n_stirrups_total * 2 * 50.27 >= r.Atr_required_mm2


def test_final_shear_verdict_includes_spacing_limits():
    """Passing strength alone is insufficient when CT (98)/10.3.4.3 spacing fails."""
    sec = RectangularBeamSection(300, 600, tensile_rebar=grp((3, 20, 40)))
    r = check_beam_shear(50, sec, get_concrete("B30"), CB240, 8, 2, 2000)
    assert r.Qu_kN > r.Q_kN
    assert r.is_strut_safe
    assert not r.is_spacing_ok
    assert not r.is_safe
