"""Unit tests for TCVN 5574-2018 RC Shear Wall and Core Wall module.

Validates against benchmark examples in MOC Guideline (QD 862/QD-BXD) pp. 36-40.
"""

import math
import pytest

from tcvn5574.wall import (
    WallSection,
    WallSegment,
    WallRebar,
    random_eccentricity,
    calculate_wall_buckling_eta,
    calculate_combined_wall_moments,
    calculate_phi_n,
    check_wall_shear,
    design_wall_shear,
    check_wall_analytical_flanged,
    generate_pm_interaction_curve,
    check_wall_interaction_dc,
    wall_to_concrete_section,
)


def test_wall_geometry_and_properties():
    """Verify Section 7 (pp. 36-37) geometric properties for flanged I-wall."""
    # Flanged I-section:
    # Length h = 1500 mm, web tw = 200 mm, flange bf = 600 mm, hf = 215 mm
    section = WallSection.flanged_I(
        length=1500.0,
        web_thickness=200.0,
        flange_width=600.0,
        flange_thickness=215.0,
    )

    Ac, Xc, Yc, Ix, Iy, Ixy, ix, iy = section.calculate_concrete_properties()

    # Manual calculation from guideline page 37:
    # A = 200 * 1500 + 2 * 400 * 215 = 472000 mm^2
    assert pytest.approx(Ac, rel=1e-3) == 472_000.0
    # Symmetric in both axes: centroid at (0, 0)
    assert abs(Xc) < 1e-4
    assert abs(Yc) < 1e-4

    # Ix (bending in plane of wall, along length Y):
    # I = 1279 * 10^8 mm^4 = 1.279e11 mm^4
    # The exact formula in guideline:
    # I = 200*1500^3/12 + 2*(400*215^3)/12 + 2*400*215*(1500/2 - 215/2)^2 = 1.279e11
    assert pytest.approx(Ix, rel=0.01) == 1.279e11

    # Radius of gyration i = sqrt(I / A) = 521 mm
    assert pytest.approx(ix, rel=0.01) == 521.0


def test_guideline_section_7_buckling_and_moments():
    """Verify buckling factors eta_v and eta_h per Section 7 (pp. 37-38)."""
    # Parameters from example:
    # H = 15m, l0_v = 0.7*15 = 10.5m = 10500 mm
    # l0_h = 1.5*15 = 22.5m = 22500 mm
    # Nv = 6000 kN, Mv = 1000 kNm
    # Nl = 5000 kN, Ml = 750 kNm
    # Mh = 2000 kN.m
    # Concrete Eb = 34500 MPa, I = 1.279e11 mm^4, A = 472000 mm^2
    # Steel Es = 200000 MPa, As = As' = 5630 mm^2, a = 79 mm, h0 = 1421 mm
    # Is = 2 * As * (0.5 * h - a)^2 = 2 * 5630 * (750 - 79)^2 = 5.07e9 mm^4

    h = 1500.0
    a = 79.0
    h0 = h - a
    As = 5630.0
    Is = 2.0 * As * (0.5 * h - a) ** 2  # 5.07e9 mm^4

    # Combined vertical + lateral moment M = 1000 + 2000 = 3000 kNm
    # M1 = M + N * (h0 - a') / 2 = 3000 + 6000 * (1.421 - 0.079) / 2 = 7026 kNm
    # M1l = Ml + Nl * (h0 - a') / 2 = 750 + 5000 * (1.421 - 0.079) / 2 = 4105 kNm
    M1_Nmm = (3000.0 + 6000.0 * (1.421 - 0.079) / 2.0) * 1e6  # 7026 kNm
    M1l_Nmm = (750.0 + 5000.0 * (1.421 - 0.079) / 2.0) * 1e6  # 4105 kNm

    phi_l = 1.0 + M1l_Nmm / M1_Nmm  # 1.584 per guideline

    # Vertical load buckling factor eta_v
    res_v = calculate_wall_buckling_eta(
        N_N=6000.0 * 1e3,
        M_Nmm=3000.0 * 1e6,
        l0_mm=10500.0,
        h_mm=1500.0,
        I_mm4=1.279e11,
        A_mm2=472000.0,
        Eb_MPa=34500.0,
        Es_MPa=200000.0,
        Is_mm4=Is,
        phi_l=phi_l,
    )

    # Guideline values: D = 1.37e15 N*mm^2, Ncr = 1.225e8 N = 122500 kN, eta_v = 1.051
    assert pytest.approx(res_v.D_Nmm2, rel=0.03) == 1.37e15
    assert pytest.approx(res_v.eta, rel=0.01) == 1.051

    # Lateral load buckling factor eta_h (l0 = 22.5 m)
    res_h = calculate_wall_buckling_eta(
        N_N=6000.0 * 1e3,
        M_Nmm=3000.0 * 1e6,
        l0_mm=22500.0,
        h_mm=1500.0,
        I_mm4=1.279e11,
        A_mm2=472000.0,
        Eb_MPa=34500.0,
        Es_MPa=200000.0,
        Is_mm4=Is,
        phi_l=phi_l,
    )

    # Guideline value: eta_h = 1.29
    assert pytest.approx(res_h.eta, rel=0.01) == 1.29
    assert res_v.is_stable is True

    # Combined design moment: M = Mv * eta_v + Mh * eta_h = 1000 * 1.051 + 2000 * 1.29 = 3631 kNm
    M_calc = calculate_combined_wall_moments(
        M_v_kNm=1000.0,
        eta_v=res_v.eta,
        M_h_kNm=2000.0,
        eta_h=res_h.eta,
    )
    assert pytest.approx(M_calc, abs=10.0) == 3631.0


def test_guideline_section_7_analytical_capacity():
    """Verify Section 7 (pp. 38-39) analytical capacity Mu = 4221.2 kNm."""
    # N = 6000 kN, M_calc = 3631 kNm
    # h = 1500 mm, b = 200 mm, bf' = 600 mm, hf' = 215 mm
    # As = As' = 5630 mm^2, a = a' = 79 mm
    # Rb = 19.5 MPa, Rs = Rsc = 350 MPa, xi_R = 0.533
    res = check_wall_analytical_flanged(
        N_kN=6000.0,
        M_calc_kNm=3631.0,
        h_mm=1500.0,
        b_mm=200.0,
        bf_prime_mm=600.0,
        hf_prime_mm=215.0,
        As_mm2=5630.0,
        As_prime_mm2=5630.0,
        a_mm=79.0,
        a_prime_mm=79.0,
        Rb_MPa=19.5,
        Rs_MPa=350.0,
        Rsc_MPa=350.0,
        xi_R=0.533,
    )

    assert res.case == "small_eccentricity"
    # Guideline page 39: xi = 0.78, x = 896 mm, Mu = 4221.2 kNm
    assert pytest.approx(res.xi, abs=0.02) == 0.78
    assert pytest.approx(res.x_mm, abs=5.0) == 896.0
    assert pytest.approx(res.Mu_kNm, rel=0.01) == 4221.2
    assert res.is_safe is True
    assert res.utilization < 1.0


def test_wall_shear_calculations():
    """Verify shear check and transverse reinforcement design per Section 5.2."""
    # Test axial stress coefficient phi_n
    # A = 472000 mm^2, Rb = 19.5 MPa, Rbt = 1.05 MPa
    A = 472_000.0
    Rb = 19.5
    Rbt = 1.05

    # Case 1: compression sigma_m = 0.1 * Rb <= 0.25 Rb -> phi_n = 1.1
    N_comp_small = 0.1 * Rb * A
    assert pytest.approx(calculate_phi_n(N_comp_small, A, Rb, Rbt), rel=1e-3) == 1.1

    # Case 2: compression sigma_m = 0.5 * Rb in (0.25, 0.75) -> phi_n = 1.25
    N_comp_mid = 0.5 * Rb * A
    assert pytest.approx(calculate_phi_n(N_comp_mid, A, Rb, Rbt), rel=1e-3) == 1.25

    # Case 3: compression sigma_m = 0.8 * Rb in (0.75, 1.0) -> phi_n = 5*(1 - 0.8) = 1.0
    N_comp_high = 0.8 * Rb * A
    assert pytest.approx(calculate_phi_n(N_comp_high, A, Rb, Rbt), rel=1e-3) == 1.0

    # Shear check with stirrup d10 s150 (2 legs)
    # Asw = 2 * pi * 10^2 / 4 = 157.08 mm^2, sw = 150 mm
    # Rsw = 280 MPa, b = 200 mm, h0 = 1421 mm
    b = 200.0
    h0 = 1421.0
    Asw = 2.0 * math.pi * (10.0**2) / 4.0
    sw = 150.0
    Rsw = 280.0

    shear_res = check_wall_shear(
        Q_kN=450.0,
        N_kN=2000.0,
        b_mm=b,
        h0_mm=h0,
        A_mm2=A,
        Rb_MPa=Rb,
        Rbt_MPa=Rbt,
        Rsw_MPa=Rsw,
        Asw_mm2=Asw,
        sw_mm=sw,
    )

    assert shear_res.is_safe is True
    assert h0 <= shear_res.C_mm <= 2.0 * h0
    assert shear_res.strut_ok is True
    assert shear_res.Q_capacity_kN > 450.0

    # Design shear reinforcement
    design_res = design_wall_shear(
        Q_kN=500.0,
        N_kN=2000.0,
        b_mm=b,
        h0_mm=h0,
        A_mm2=A,
        Rb_MPa=Rb,
        Rbt_MPa=Rbt,
        Rsw_MPa=Rsw,
        stirrup_diameter_mm=10.0,
        n_legs=2,
        max_sw_mm=200.0,
    )

    assert design_res.sw_selected_mm <= 200.0
    assert design_res.check_result.is_safe is True


def test_fiber_discretization_and_interaction():
    """Verify fiber discretization and P-M interaction curve generation."""
    # Create simple rectangular wall: length 2000 mm, thickness 250 mm
    # 2 boundary bars of 4d25 at each end (a = 50 mm)
    rebars = [
        # Bottom edge (Y = -950 mm): 4 bars
        WallRebar(x=-50.0, y=-950.0, diameter=25.0),
        WallRebar(x=50.0, y=-950.0, diameter=25.0),
        # Top edge (Y = 950 mm): 4 bars
        WallRebar(x=-50.0, y=950.0, diameter=25.0),
        WallRebar(x=50.0, y=950.0, diameter=25.0),
    ]
    wall = WallSection.rectangle(length=2000.0, thickness=250.0, rebars=rebars)

    curve = generate_pm_interaction_curve(
        section=wall,
        Rb_MPa=14.5,
        Rs_MPa=350.0,
        Rsc_MPa=350.0,
        n_steps=20,
        max_fiber_size=50.0,
    )

    assert curve.N_max_kN > 0.0
    assert curve.N_min_kN < 0.0
    assert curve.M_max_pos_kNm > 0.0
    assert len(curve.points) > 10

    # Test point inside curve: safe
    res_safe = check_wall_interaction_dc(
        N_kN=2000.0,
        M_kNm=300.0,
        curve=curve,
    )
    assert res_safe.is_safe is True
    assert res_safe.D_C_radial < 1.0

    # Test extreme point outside curve: unsafe
    res_unsafe = check_wall_interaction_dc(
        N_kN=2000.0,
        M_kNm=50000.0,
        curve=curve,
    )
    assert res_unsafe.is_safe is False
    assert res_unsafe.D_C_radial > 1.0


def test_accidental_eccentricity_produces_minimum_design_moment():
    """A concentric compression member must still be checked at N*ea."""
    result = calculate_wall_buckling_eta(
        N_N=2_000_000.0,
        M_Nmm=0.0,
        l0_mm=3_000.0,
        h_mm=300.0,
        I_mm4=6.75e9,
        A_mm2=90_000.0,
        Eb_MPa=30_000.0,
    )
    assert result.ea_mm == 10.0
    assert result.e0_mm == 10.0
    assert result.M_initial_kNm == pytest.approx(20.0)
    assert result.M_design_kNm >= 20.0


def test_buckling_instability_is_explicit_not_arbitrary_eta_cap():
    result = calculate_wall_buckling_eta(
        N_N=1.0e12,
        M_Nmm=1.0e8,
        l0_mm=10_000.0,
        h_mm=300.0,
        I_mm4=6.75e9,
        A_mm2=90_000.0,
        Eb_MPa=30_000.0,
    )
    assert result.is_stable is False
    assert math.isinf(result.eta)
    assert math.isinf(result.M_design_kNm)


def test_shear_design_reports_unachievable_required_spacing():
    result = design_wall_shear(
        Q_kN=2_000.0,
        N_kN=2_000.0,
        b_mm=200.0,
        h0_mm=1_421.0,
        A_mm2=472_000.0,
        Rb_MPa=19.5,
        Rbt_MPa=1.05,
        Rsw_MPa=280.0,
        stirrup_diameter_mm=10.0,
        n_legs=2,
        max_sw_mm=200.0,
    )
    assert result.sw_required_mm < 50.0
    assert result.sw_selected_mm == 50.0
    assert result.design_feasible is False
    assert result.check_result.is_safe is False


def test_wall_input_validation_and_neutral_axis_output():
    with pytest.raises(ValueError):
        WallSection.rectangle(length=0.0, thickness=200.0)
    wall = WallSection.rectangle(length=2_000.0, thickness=250.0)
    with pytest.raises(ValueError):
        generate_pm_interaction_curve(wall, 14.5, 350.0, 350.0, bending_axis="z")

    curve = generate_pm_interaction_curve(
        wall, 14.5, 350.0, 350.0, n_steps=3, max_fiber_size=100.0
    )
    assert any(math.isfinite(point.x_na_mm) for point in curve.points)


def test_concreteproperties_wall_adapter_rectangle():
    """Main nonlinear engine accepts a complete wall section with explicit bars."""
    pytest.importorskip("concreteproperties")
    bars = [
        WallRebar(x=-75.0, y=-950.0, diameter=25.0),
        WallRebar(x=75.0, y=-950.0, diameter=25.0),
        WallRebar(x=-75.0, y=950.0, diameter=25.0),
        WallRebar(x=75.0, y=950.0, diameter=25.0),
    ]
    wall = WallSection.rectangle(2_000.0, 250.0, rebars=bars)
    code, concrete_section = wall_to_concrete_section(wall, "B25", "CB400-V")

    gross_bar_area = sum(bar.area for bar in bars)
    assert concrete_section.gross_properties.total_area == pytest.approx(
        wall.total_concrete_area
    )
    assert code.tensile_load == pytest.approx(-350.0 * gross_bar_area, rel=0.01)
    result = code.ultimate_bending_capacity(n=2_000e3)
    assert result.m_x > 0.0
    assert result.governing in {"concrete", "steel", "one-sign"}


def test_concreteproperties_wall_adapter_flanged_and_biaxial():
    pytest.importorskip("concreteproperties")
    wall = WallSection.flanged_I(
        length=1_500.0,
        web_thickness=200.0,
        flange_width=600.0,
        flange_thickness=215.0,
        rebars=[
            WallRebar(x=-150.0, y=-671.0, diameter=28.0, area=2_815.0),
            WallRebar(x=150.0, y=671.0, diameter=28.0, area=2_815.0),
        ],
    )
    # B35 matches the guideline benchmark properties Rb=19.5 MPa, Eb=34500 MPa.
    code, _ = wall_to_concrete_section(wall, "B35", "CB400-V")
    ok, capacity, utilization, _ = code.biaxial_check(
        n=2_000e3, m_x=500e6, m_y=50e6
    )
    assert capacity > 0.0
    assert utilization > 0.0
    assert ok is (utilization <= 1.0 + 1e-9)
