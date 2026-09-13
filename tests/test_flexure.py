"""Flexure vs Đoàn Thị Quỳnh Mai, Hướng dẫn tính toán cấu kiện BTCT theo TCVN 5574:2018, VD 2.1-2.8."""

from conftest import grp
from tcvn5574 import (
    RectangularBeamSection,
    calculate_alpha_R,
    calculate_xi_R,
    check_beam_flexure,
    design_beam_flexure,
    get_concrete,
    get_rebar,
)

B20, B25, B30 = get_concrete("B20"), get_concrete("B25"), get_concrete("B30")
CB300, CB400 = get_rebar("CB300-V"), get_rebar("CB400-V")
S22 = grp((3, 22, 36), (2, 22, 88))  # 5d22 in two layers, a = 56.8


def close(a, b, tol=0.01):
    return abs(a - b) <= tol * abs(b)


def test_xi_R():
    xi = calculate_xi_R(350, 200000)
    assert close(xi, 0.533) and close(calculate_alpha_R(xi), 0.391)
    assert close(calculate_xi_R(260, 200000), 0.583)


def test_vd21_singly_design():
    assert close(design_beam_flexure(253, 250, 600, B25, CB400, a_mm=50).As_required_mm2, 1515.9)


def test_vd22_vd23_capacity_and_over_reinforced():
    sec = RectangularBeamSection(220, 500, tensile_rebar=S22)
    assert close(check_beam_flexure(0, sec, B20, CB300).Mu_kNm, 170.954)
    r = check_beam_flexure(0, sec, B20, CB400)  # xi = 0.593 > xi_R -> x = xi_R h0
    assert close(r.Mu_kNm, 194.311) and "Over" in r.failure_mode


def test_vd24_doubly_design():
    d = design_beam_flexure(415, 250, 600, B25, CB400, a_mm=70, a_prime_mm=35)
    assert d.is_double_reinforced
    assert close(d.Asc_required_mm2, 97.31, 0.02) and close(d.As_required_mm2, 3023.1)


def test_vd26_doubly_capacity():
    sec = RectangularBeamSection(250, 600, tensile_rebar=grp((3, 22, 36), (2, 20, 88)), comp_rebar=grp((2, 16, 35)))
    assert close(check_beam_flexure(0, sec, B25, CB400).Mu_kNm, 301.118)


def test_vd27_vd28_T_section():
    assert close(design_beam_flexure(222, 250, 500, B25, CB400, a_mm=40, bf_mm=500, hf_mm=70).As_required_mm2, 1496.8)
    sec = RectangularBeamSection(220, 500, bf=500, hf=80, tensile_rebar=S22)
    assert close(check_beam_flexure(0, sec, B20, CB300).Mu_kNm, 197.593)


def test_excel_rc_beam_row():
    """02.RC BEAM sheet 'Beams': B30/SD390 600x500, 12T20 a=80 -> [M] = 464.2 kNm."""
    sec = RectangularBeamSection(600, 500, tensile_rebar=grp((12, 20, 80)))
    assert close(check_beam_flexure(425, sec, B30, get_rebar("SD390")).Mu_kNm, 464.2)


def test_nonlinear_toggle_vd211():
    """check_beam_flexure(nonlinear=True) -> 8.1.2.7 (VD 2.11: 168.81 kNm), default -> limit force (VD 2.2: 170.95)."""
    import pytest

    pytest.importorskip("concreteproperties")
    sec = RectangularBeamSection(220, 500, tensile_rebar=S22)
    lf = check_beam_flexure(150, sec, B20, CB300)
    nl = check_beam_flexure(150, sec, B20, CB300, nonlinear=True)
    assert lf.method == "limit_force" and close(lf.Mu_kNm, 170.954)
    assert nl.method == "nonlinear" and close(nl.Mu_kNm, 168.81) and close(nl.x_mm, 229.76)
    assert check_beam_flexure(-150, sec, B20, CB300, nonlinear=True).Mu_kNm < 60  # hogging: no top bars
