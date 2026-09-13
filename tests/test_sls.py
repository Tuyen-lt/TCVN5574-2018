"""SLS per TCVN 5574:2018 8.2 vs Đoàn Thị Quỳnh Mai VD 6.1-6.5."""

import pytest

from conftest import grp
from tcvn5574 import CrackRequirement, RectangularBeamSection, check_beam_cracking, check_beam_deflection, get_concrete, get_rebar
from tcvn5574.sls.crack import cracked_section, crack_width, cracking_moment
from tcvn5574.sls.deflection import curvature_cracked, curvature_uncracked

B20, B25, B30, B35 = (get_concrete(g) for g in ("B20", "B25", "B30", "B35"))
CB400, CB500 = get_rebar("CB400-V"), get_rebar("CB500-V")
SEC61 = RectangularBeamSection(220, 500, tensile_rebar=grp((3, 16, 28)), comp_rebar=grp((2, 16, 28)))
SEC62 = RectangularBeamSection(250, 600, tensile_rebar=grp((3, 20, 30)), comp_rebar=grp((2, 16, 28)))
SEC63 = RectangularBeamSection(400, 660, tensile_rebar=grp((4, 22, 46)), comp_rebar=grp((4, 16, 33)))  # h0 = 614


def close(a, b, tol=0.01):
    return abs(a - b) <= tol * abs(b)


def test_vd61_cracking_moment():
    tp = SEC61.get_transformed_properties(200000 / 27500)
    assert close(tp["Ared"], 117311) and close(tp["yt"], 247) and close(tp["Ired"], 26.51e8) and close(tp["Wpl"], 13.94e6)
    assert close(cracking_moment(SEC61, B20, CB400) / 1e6, 18.82)
    assert close(cracking_moment(SEC61, B35, CB400) / 1e6, 26.38)


def test_vd62_crack_width():
    Mcrc = cracking_moment(SEC62, B25, CB500)
    assert close(Mcrc / 1e6, 35.31)
    a1 = 200000 / (18.5 / 0.0015)
    x, Ired = cracked_section(SEC62, a1, a1)
    assert close(x, 193) and close(Ired, 29.49e8)
    d = crack_width(82.5e6, 1.0, SEC62, B25, CB500, Mcrc)
    # book p.144-146: yt = 294, Abt = 73500, Ls = 780 -> 400, sigma_s = 170.8, psi_s = 0.66, acrc = 0.112
    assert close(d.yt_mm, 294) and close(d.Abt_mm2, 73500) and close(d.Ls_calc_mm, 780) and d.Ls_mm == 400
    assert close(d.sigma_s, 170.8) and close(d.psi_s, 0.66) and close(d.acrc_mm, 0.112)


def test_vd63_long_crack_width():
    Mcrc = cracking_moment(SEC63, B30, CB400)
    assert close(Mcrc / 1e6, 73.5, 0.03)
    a1 = 200000 / (22 / 0.0015)
    x, Ired = cracked_section(SEC63, a1, a1)
    assert close(x, 189) and close(Ired, 49.12e8)
    d = crack_width(166e6, 1.4, SEC63, B30, CB400, Mcrc)
    assert close(d.sigma_s, 196) and d.Ls_mm == 400 and close(d.acrc_mm, 0.177, 0.02)


def test_vd64_uncracked_curvature():
    # book: Eb1 = 0.85 Eb, alpha = 6.82; the book's Ired = 22.92e8 = b h^3/12 omits the steel terms of CT (189)
    Eb1 = 0.85 * 34500
    alpha = 200000 / Eb1
    Ired = SEC61.get_transformed_properties(alpha)["Ired"]
    k = curvature_uncracked(24e6, SEC61, B35, CB400, False, "40-75%")
    assert close(k, 24e6 / (Eb1 * Ired))
    assert k < 3.57e-7


def test_vd65_cracked_long_curvature():
    Mcrc = cracking_moment(SEC63, B30, CB400)
    assert close(curvature_cracked(166e6, Mcrc, SEC63, B30, CB400, True, "40-75%"), 19.45e-7, 0.02)


def test_check_beam_cracking_combination():
    r = check_beam_cracking(98, 82.5, SEC62, B25, CB500)
    assert r.is_cracked
    assert close(r.acrc_short_mm, r.acrc1_mm + r.acrc2_mm - r.acrc3_mm, 0.02)
    assert (r.acrc_short_allowable_mm, r.acrc_long_allowable_mm) == (0.4, 0.3)  # Bảng 17
    assert check_beam_cracking(10, 5, SEC62, B25, CB500).acrc_short_mm == 0.0


def test_deflection_total_curvature():
    L = 6500
    r = check_beam_deflection(L, 98, 82.5, SEC62, B25, CB500)
    assert r.is_cracked
    assert abs(r.curvature_total - (r.curvature_1 - r.curvature_2 + r.curvature_3)) < 1e-15
    assert r.curvature_3 > r.curvature_2  # long-term > short-term under the same load
    assert close(r.f_mm, 5 / 48 * L**2 * r.curvature_total)
    u = check_beam_deflection(L, 20, 15, SEC62, B25, CB500)
    assert not u.is_cracked and u.curvature_3 == 0


def test_no_crack_returns_none():
    assert crack_width(10e6, 1.0, SEC62, B25, CB500, cracking_moment(SEC62, B25, CB500)) is None


def test_sigma_s_capped_at_Rs_ser():
    d = crack_width(400e6, 1.0, SEC62, B25, CB500, cracking_moment(SEC62, B25, CB500))
    assert d.sigma_s_calc > 500 and d.sigma_s == 500.0  # 8.2.2.3.2: sigma_s <= Rs,ser


def test_T_flange_in_tension():
    """Support section of a continuous beam: slab 1200x100 on the tension side (Bảng L.1 item 3)."""
    top = grp((4, 20, 40))
    sec = RectangularBeamSection(300, 600, bf=1200, hf=100, tensile_rebar=top, flange_in_tension=True)
    tp = sec.get_transformed_properties(200000 / 30000)
    assert tp["gamma"] == 1.20  # bf/b = 4 > 2, hf/h = 0.167 < 0.2
    assert sec.tension_concrete_area(150) == 1200 * 100 + 300 * 50
    rect = RectangularBeamSection(300, 600, tensile_rebar=top)
    assert cracking_moment(sec, B25, CB400) > cracking_moment(rect, B25, CB400)
    a1 = 200000 / (18.5 / 0.0015)
    assert cracked_section(sec, a1, a1) == cracked_section(rect, a1, a1)  # flange ignored when cracked
    assert RectangularBeamSection(300, 600, bf=500, hf=150, tensile_rebar=top, flange_in_tension=True).get_transformed_properties(6.67)["gamma"] == 1.25


def test_mixed_diameter_and_limits():
    g = grp((2, 25, 40), (2, 16, 40))
    assert close(g.nominal_diameter, (2 * 625 + 2 * 256) / (2 * 25 + 2 * 16))
    r = check_beam_cracking(98, 82.5, SEC62, B25, CB500, requirement=CrackRequirement.IMPERMEABILITY)
    assert (r.acrc_short_allowable_mm, r.acrc_long_allowable_mm) == (0.3, 0.2)
    assert r.detail1.phi1 == 1.4 and r.detail2.phi1 == 1.0


def test_service_load_decomposition_validation():
    with pytest.raises(ValueError, match="cannot exceed"):
        check_beam_cracking(100, 150, SEC62, B25, CB500)
    with pytest.raises(ValueError, match="cannot exceed"):
        check_beam_deflection(6500, 100, 150, SEC62, B25, CB500)
    with pytest.raises(ValueError, match="non-negative"):
        check_beam_cracking(-100, 50, SEC62, B25, CB500)


def test_simplified_deflection_rejects_deep_beam():
    with pytest.raises(ValueError, match="shear-deflection"):
        check_beam_deflection(5000, 100, 80, SEC63, B30, CB400)
