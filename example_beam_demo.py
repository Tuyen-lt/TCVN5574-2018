"""Comprehensive end-to-end demonstration of the tcvn5574 calculation engine."""

import sys
from tcvn5574 import (
    BeamBoundaryCondition,
    ConcreteGrade,
    HumidityCondition,
    RebarGrade,
    RebarGroup,
    RectangularBeamSection,
    calculate_anchorage_length,
    calculate_lap_splice_length,
    check_beam_cracking,
    check_beam_deflection,
    check_beam_flexure,
    check_beam_shear,
    check_beam_torsion,
    design_beam_flexure,
    design_beam_shear,
    design_hanging_reinforcement,
    get_concrete,
    get_rebar,
)

sys.stdout.reconfigure(encoding="utf-8")


def main():
    print("=" * 70)
    print("      TCVN 5574-2018 REINFORCED CONCRETE BEAM CALCULATION ENGINE")
    print("=" * 70)

    # 1. Geometry and Materials
    b = 300.0  # mm
    h = 600.0  # mm
    L = 6000.0  # mm (span)
    concrete = get_concrete("B30")
    rebar_long = get_rebar("CB400-V")
    rebar_stirrup = get_rebar("CB240-T")

    print(f"\n[1] SPECIFICATIONS:")
    print(f"  - Section: b = {b:.0f} mm, h = {h:.0f} mm, Span L = {L/1e3:.1f} m")
    print(f"  - Concrete: {concrete.grade.value} (Rb = {concrete.Rb} MPa, Rbt = {concrete.Rbt} MPa, Eb = {concrete.Eb:.0f} MPa)")
    print(f"  - Longitudinal Rebar: {rebar_long.grade.value} (Rs = {rebar_long.Rs} MPa, Es = {rebar_long.Es:.0f} MPa)")
    print(f"  - Transverse Rebar: {rebar_stirrup.grade.value} (Rsw = {rebar_stirrup.Rsw} MPa)")

    # 2. Flexural Design
    M_applied = 220.0  # kNm
    flex_design = design_beam_flexure(
        M_kNm=M_applied,
        b_mm=b,
        h_mm=h,
        concrete=concrete,
        rebar=rebar_long,
        a_mm=45.0,
    )
    print(f"\n[2] FLEXURAL DESIGN (M = {M_applied:.1f} kNm):")
    print(f"  - Boundary limits: xi_R = {flex_design.xi_R:.3f}, alpha_R = {flex_design.alpha_R:.3f}")
    print(f"  - Dimensionless factor: alpha_m = {flex_design.alpha_m:.3f}, xi = {flex_design.xi:.3f}")
    print(f"  - Double reinforced required: {flex_design.is_double_reinforced}")
    print(f"  - Required As: {flex_design.As_required_cm2:.2f} cm² (mu = {flex_design.mu_percent:.2f}%)")

    # 3. Provided Rebar & Capacity Check
    # Provide 4T22 at bottom (As = 4 * 3.801 = 15.2 cm2), 2T18 at top (Asc = 5.09 cm2)
    tensile_rebar = RebarGroup.from_simple(n_bars=4, diameter=22.0, a_dist=45.0)
    comp_rebar = RebarGroup.from_simple(n_bars=2, diameter=18.0, a_dist=40.0)
    section = RectangularBeamSection(
        b=b,
        h=h,
        tensile_rebar=tensile_rebar,
        comp_rebar=comp_rebar,
    )
    flex_check = check_beam_flexure(M_kNm=M_applied, section=section, concrete=concrete, rebar=rebar_long)
    print(f"\n[3] FLEXURAL CAPACITY CHECK (4T22 bottom, 2T18 top):")
    print(f"  - Ultimate Moment Capacity [M]gh: {flex_check.Mu_kNm:.1f} kNm")
    print(f"  - Utilization Ratio (M / Mu): {flex_check.utilization_ratio:.2f}")
    print(f"  - Check Result: {'PASS (OK)' if flex_check.is_safe else 'FAIL (NG)'} | {flex_check.failure_mode}")

    # 4. Shear Check
    Q_applied = 160.0  # kN
    shear_check = check_beam_shear(
        Q_kN=Q_applied,
        section=section,
        concrete=concrete,
        stirrup_rebar=rebar_stirrup,
        stirrup_diameter_mm=8.0,
        n_legs=2,
        s_mm=150.0,
    )
    print(f"\n[4] SHEAR CAPACITY CHECK (phi 8 a150, 2 legs, Q = {Q_applied:.1f} kN):")
    print(f"  - Web Crushing Limit Q_strut: {shear_check.Q_max_strut_kN:.1f} kN (Safe: {shear_check.is_strut_safe})")
    print(f"  - Crack Projection C: {shear_check.C_mm:.0f} mm")
    print(f"  - Concrete shear Qb: {shear_check.Qb_kN:.1f} kN, Stirrups shear Qsw: {shear_check.Qsw_kN:.1f} kN")
    print(f"  - Total Shear Capacity Qu = Qb + Qsw: {shear_check.Qu_kN:.1f} kN")
    print(f"  - Shear Check: {'PASS (OK)' if shear_check.is_safe else 'FAIL (NG)'} (UR: {shear_check.utilization_ratio:.2f})")

    # 5. Serviceability: Cracking and Deflection
    M_short = 175.0  # kNm
    M_long = 135.0   # kNm
    crack_res = check_beam_cracking(
        M_short_kNm=M_short,
        M_long_kNm=M_long,
        section=section,
        concrete=concrete,
        rebar=rebar_long,
    )
    defl_res = check_beam_deflection(
        span_mm=L,
        M_short_kNm=M_short,
        M_long_kNm=M_long,
        section=section,
        concrete=concrete,
        rebar=rebar_long,
        boundary=BeamBoundaryCondition.SIMPLY_SUPPORTED_UDL,
    )
    print(f"\n[5] SERVICEABILITY LIMIT STATE (M_short = {M_short:.1f} kNm, M_long = {M_long:.1f} kNm):")
    print(f"  - Cracking Resistance Mcrc: {crack_res.Mcrc_kNm:.1f} kNm (Cracked: {crack_res.is_cracked})")
    print(f"  - Short-term Crack Width: {crack_res.acrc_short_mm:.3f} mm <= [{crack_res.acrc_short_allowable_mm}] mm ({'OK' if crack_res.is_short_term_safe else 'NG'})")
    print(f"  - Long-term Crack Width:  {crack_res.acrc_long_mm:.3f} mm <= [{crack_res.acrc_long_allowable_mm}] mm ({'OK' if crack_res.is_long_term_safe else 'NG'})")
    print(f"  - Total Deflection f = s L2 [(1/r)1 - (1/r)2 + (1/r)3]: {defl_res.f_mm:.2f} mm <= [{defl_res.f_allowable_mm:.1f}] mm ({'OK' if defl_res.is_safe else 'NG'})")

    # 6. Hanging Reinforcement (Secondary beam 300x400 framing in with P = 110 kN)
    hanging_res = design_hanging_reinforcement(
        P_kN=110.0,
        h_main_mm=h,
        b_main_mm=b,
        h_sec_mm=400.0,
        b_sec_mm=300.0,
        stirrup_rebar=rebar_stirrup,
        stirrup_diameter_mm=8.0,
        n_legs=2,
    )
    print(f"\n[6] HANGING REINFORCEMENT AT INTERSECTION (P = 110.0 kN, h_sec = 400 mm):")
    print(f"  - Hung-up Force Fs = P: {hanging_res.Fs_kN:.1f} kN")
    print(f"  - Required Steel Atr: {hanging_res.Atr_required_cm2:.2f} cm²")
    print(f"  - Additional Stirrups: {hanging_res.n_stirrups_total} stirrups (phi 8, 2 legs) => {hanging_res.n_stirrups_each_side} on each side")

    # 7. Detailing: Anchorage & Lap Splice of Main Rebar (phi 22)
    anc_res = calculate_anchorage_length(
        diameter_mm=22.0,
        concrete=concrete,
        rebar=rebar_long,
        is_tension=True,
    )
    lap_res = calculate_lap_splice_length(
        diameter_mm=22.0,
        concrete=concrete,
        rebar=rebar_long,
        spliced_percentage=100.0,
    )
    print(f"\n[7] DETAILING - ANCHORAGE & LAP SPLICE (d = 22 mm, CB400-V in B30):")
    print(f"  - Bond Strength Rbond: {anc_res.Rbond_MPa:.3f} MPa")
    print(f"  - Basic Anchorage Length l0,an: {anc_res.l0_an_mm:.0f} mm ({anc_res.l0_an_d:.1f} d)")
    print(f"  - Design Anchorage Length lan: {anc_res.lan_mm:.0f} mm ({anc_res.lan_d:.1f} d)")
    print(f"  - Lap Splice Length (100% spliced) llap: {lap_res.llap_mm:.0f} mm ({lap_res.llap_d:.1f} d)")

    print("\n" + "=" * 70)
    print("                    ALL CALCULATIONS COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
