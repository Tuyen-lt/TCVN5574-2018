"""Torsion per TCVN 5574:2018 8.1.4 vs Đoàn Thị Quỳnh Mai VD 5.7-5.9."""

from conftest import grp
from tcvn5574 import RectangularBeamSection, check_beam_torsion, get_concrete, get_rebar
from tcvn5574.shear.beam_shear import shear_capacity
from tcvn5574.torsion.beam_torsion import spatial_section_T0

B30, CB400, CB300 = get_concrete("B30"), get_rebar("CB400-V"), get_rebar("CB300-V")
QSW1 = 210 * 78.5 / 150  # d10 leg, s = 150


def close(a, b, tol=0.005):
    return abs(a - b) <= tol * abs(b)


def test_vd57_spatial_section():
    assert close(spatial_section_T0(350, 942, QSW1, 300, 400) / 1e6, 17.54)  # ratio < 0.5 -> As1 reduced
    assert close(spatial_section_T0(350, 948, QSW1, 400, 300) / 1e6, 21.24)


def test_ratio_upper_limit():
    # qsw1 Z1 / (Rs As1) > 1.5 -> qsw1 reduced to 1.5 Rs As1 / Z1
    assert spatial_section_T0(350, 100, 500, 300, 400) == spatial_section_T0(350, 100, 1.5 * 350 * 100 / 300, 300, 400)


def test_vd58_bending_torsion():
    sec = RectangularBeamSection(300, 400, tensile_rebar=grp((3, 22, 32)), comp_rebar=grp((3, 20, 32)))
    r = check_beam_torsion(15, 115, 0, sec, B30, CB400, CB300, 10, 150)
    assert close(r.T_max_crushing_kNm, 61.2)
    assert close(r.T0_bottom_kNm, 17.54)
    assert r.ratio_MT_major > 1.0 and not r.is_overall_safe  # book: 8.46 < 15 kNm -> NG


def test_vd59_strut_between_spatial_sections():
    sec = RectangularBeamSection(300, 400, tensile_rebar=grp((3, 20, 36)), comp_rebar=grp((3, 20, 36)))
    r = check_beam_torsion(18, 0, 110, sec, B30, CB400, CB300, 10, 150, n_stirrup_legs=3)
    # book: [T] = 0.1 Rb b2 h (1 - Q/(0.3 Rb b h0)) = 49.11 kNm
    assert close(1 - r.ratio_strut_TQ + 18 / 61.2, 49.11 / 61.2)
    # book: Qgh = 260.5 kN = Qb + Qsw at C = 526.9 (3 legs d10), T0 = 21.24 kNm.
    # Library also scans C up to 3h0 (as the book does in VD 3.2): Qb = 0.5 Rbt b h0, Qsw = 0.75 qsw 2h0
    qsw = 210 * 236 / 150
    Q0 = 0.5 * 1.15 * 300 * 364 + 0.75 * qsw * 728
    assert close(1.5 * 1.15 * 300 * 364**2 / 526.9 + 0.75 * qsw * 526.9, 260.5e3)
    assert close(shear_capacity(qsw, 1.15, 300, 364)[0], Q0)
    # CT (115) is linear: T/T0 + Q/Q0 <= 1 (the book uses T0*sqrt(1 - Q/Q0), less conservative)
    assert close(r.ratio_QT_major, 18 / 21.24 + 110e3 / Q0)
    assert not r.is_overall_safe  # book: NG
