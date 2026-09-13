"""Demonstration script: RC Shear Wall and Core Wall calculation per TCVN 5574-2018.

Implements the complete verification workflow from Ministry of Construction Guideline
(QD 862/QD-BXD) Section 7 benchmark example (pp. 36-40).
"""

from __future__ import annotations

import math
from tcvn5574.wall import (
    WallSection,
    WallRebar,
    calculate_wall_buckling_eta,
    calculate_combined_wall_moments,
    check_wall_analytical_flanged,
    check_wall_shear,
    design_wall_shear,
    generate_pm_interaction_curve,
    check_wall_interaction_dc,
)


def run_wall_benchmark_example() -> None:
    print("=" * 80)
    print("TCVN 5574-2018 RC SHEAR WALL VERIFICATION - BENCHMARK SECTION 7")
    print("=" * 80)

    # 1. GEOMETRY & MATERIAL DEFINITION
    # Flanged I-section wall (pp. 36-37)
    # Total length H = 15.0 m, L0 = 0.7*H = 10.5 m (vertical load), L0 = 1.5*H = 22.5 m (wind)
    # Section length h = 1500 mm, web thickness bw = 200 mm
    # Flanges at both ends: width bf = 600 mm, average thickness hf = 215 mm
    H_wall_m = 15.0
    l0_v_mm = 0.7 * H_wall_m * 1000.0  # 10500 mm
    l0_h_mm = 1.5 * H_wall_m * 1000.0  # 22500 mm

    h_mm = 1500.0
    bw_mm = 200.0
    bf_mm = 600.0
    hf_mm = 215.0

    # Boundary rebars: As = As' = 5630 mm^2 located at a = a' = 79 mm
    a_mm = 79.0
    a_prime_mm = 79.0
    As_mm2 = 5630.0
    As_prime_mm2 = 5630.0
    h0_mm = h_mm - a_mm

    # Materials
    Rb_MPa = 19.5  # Concrete design compressive strength
    Rbt_MPa = 1.05  # Concrete design tensile strength
    Eb_MPa = 34500.0  # Concrete elastic modulus
    Rs_MPa = 350.0  # Longitudinal rebar tensile design strength (CB400-V)
    Rsc_MPa = 350.0  # Longitudinal rebar compressive design strength
    Es_MPa = 200000.0  # Rebar elastic modulus
    Rsw_MPa = 280.0  # Transverse reinforcement design strength

    # Applied internal forces at wall base (p. 36)
    Nv_kN = 6000.0  # Axial force from total vertical loads
    Mv_kNm = 1000.0  # Bending moment from total vertical loads
    Nl_kN = 5000.0  # Axial force from long-term loads
    Ml_kNm = 750.0  # Bending moment from long-term loads
    Nh_kN = 0.0  # Axial force from lateral wind loads
    Mh_kNm = 2000.0  # Bending moment from lateral wind loads

    # Create WallSection
    # Distribute boundary rebars at ends for fiber analysis
    rebars = [
        # Bottom boundary zone (Y around -671 mm)
        WallRebar(x=-150.0, y=-671.0, diameter=28.0, area=As_mm2 / 4.0),
        WallRebar(x=-50.0, y=-671.0, diameter=28.0, area=As_mm2 / 4.0),
        WallRebar(x=50.0, y=-671.0, diameter=28.0, area=As_mm2 / 4.0),
        WallRebar(x=150.0, y=-671.0, diameter=28.0, area=As_mm2 / 4.0),
        # Top boundary zone (Y around +671 mm)
        WallRebar(x=-150.0, y=671.0, diameter=28.0, area=As_prime_mm2 / 4.0),
        WallRebar(x=-50.0, y=671.0, diameter=28.0, area=As_prime_mm2 / 4.0),
        WallRebar(x=50.0, y=671.0, diameter=28.0, area=As_prime_mm2 / 4.0),
        WallRebar(x=150.0, y=671.0, diameter=28.0, area=As_prime_mm2 / 4.0),
    ]

    wall = WallSection.flanged_I(
        length=h_mm,
        web_thickness=bw_mm,
        flange_width=bf_mm,
        flange_thickness=hf_mm,
        rebars=rebars,
    )

    Ac, Xc, Yc, Ix, Iy, Ixy, ix, iy = wall.calculate_concrete_properties()
    print("\n[1] GROSS CONCRETE PROPERTIES:")
    print(f"  - Total Concrete Area Ac : {Ac:,.0f} mm^2 (Reference: 472,000 mm^2)")
    print(f"  - Centroid (Xc, Yc)      : ({Xc:.1f}, {Yc:.1f}) mm")
    print(f"  - In-plane Inertia Ix    : {Ix:,.3e} mm^4 (Reference: 1.279e11 mm^4)")
    print(f"  - In-plane Radius ix     : {ix:.1f} mm (Reference: 521 mm)")
    print(f"  - Out-of-plane Radius iy : {iy:.1f} mm")

    # 2. SLENDERNESS & BUCKLING (Mục 5.1.2 & Mục 7)
    print("\n[2] SLENDERNESS & SECOND-ORDER BUCKLING FACTORS:")
    slenderness_v = l0_v_mm / ix
    print(f"  - In-plane slenderness lambda_v = l0/ix: {slenderness_v:.2f} > 14 -> buckling must be considered")

    # Longitudinal steel inertia Is
    Is_mm4 = 2.0 * As_mm2 * ((0.5 * h_mm - a_mm) ** 2)
    # Long-term factor phi_l (p. 37)
    M_total_kNm = Mv_kNm + Mh_kNm
    N_total_kN = Nv_kN + Nh_kN
    M1_Nmm = (M_total_kNm + N_total_kN * (h0_mm - a_prime_mm) / 2000.0) * 1e6
    M1l_Nmm = (Ml_kNm + Nl_kN * (h0_mm - a_prime_mm) / 2000.0) * 1e6
    phi_l = 1.0 + M1l_Nmm / M1_Nmm

    res_buckling_v = calculate_wall_buckling_eta(
        N_N=N_total_kN * 1e3,
        M_Nmm=M_total_kNm * 1e6,
        l0_mm=l0_v_mm,
        h_mm=h_mm,
        I_mm4=Ix,
        A_mm2=Ac,
        Eb_MPa=Eb_MPa,
        Es_MPa=Es_MPa,
        Is_mm4=Is_mm4,
        phi_l=phi_l,
    )
    res_buckling_h = calculate_wall_buckling_eta(
        N_N=N_total_kN * 1e3,
        M_Nmm=M_total_kNm * 1e6,
        l0_mm=l0_h_mm,
        h_mm=h_mm,
        I_mm4=Ix,
        A_mm2=Ac,
        Eb_MPa=Eb_MPa,
        Es_MPa=Es_MPa,
        Is_mm4=Is_mm4,
        phi_l=phi_l,
    )

    eta_v = res_buckling_v.eta
    eta_h = res_buckling_h.eta
    M_calc_kNm = calculate_combined_wall_moments(Mv_kNm, eta_v, Mh_kNm, eta_h)

    print(f"  - Long-term factor phi_l       : {phi_l:.3f} (Reference: 1.584)")
    print(f"  - Flexural stiffness D         : {res_buckling_v.D_Nmm2:,.2e} N*mm^2 (Reference: 1.37e15)")
    print(f"  - Vertical buckling factor eta_v : {eta_v:.3f} (Reference: 1.051)")
    print(f"  - Wind lateral factor eta_h    : {eta_h:.3f} (Reference: 1.290)")
    print(f"  - Design moment M_calc         : {M_calc_kNm:,.1f} kNm (Reference: 3,631 kNm)")

    # 3. ANALYTICAL CAPACITY VERIFICATION (Mục 7 trang 38-39)
    print("\n[3] ANALYTICAL FLEXURAL CAPACITY (TCVN 5574-2018):")
    res_analytical = check_wall_analytical_flanged(
        N_kN=N_total_kN,
        M_calc_kNm=M_calc_kNm,
        h_mm=h_mm,
        b_mm=bw_mm,
        bf_prime_mm=bf_mm,
        hf_prime_mm=hf_mm,
        As_mm2=As_mm2,
        As_prime_mm2=As_prime_mm2,
        a_mm=a_mm,
        a_prime_mm=a_prime_mm,
        Rb_MPa=Rb_MPa,
        Rs_MPa=Rs_MPa,
        Rsc_MPa=Rsc_MPa,
        xi_R=0.533,
    )

    print(f"  - Overhang area Aov          : {(bf_mm - bw_mm) * hf_mm:,.0f} mm^2 (Reference: 86,000 mm^2)")
    print(f"  - Relative depth xi          : {res_analytical.xi:.3f} > xi_R = 0.533 (Reference: 0.78)")
    print(f"  - Neutral axis depth x       : {res_analytical.x_mm:.1f} mm (Reference: 896 mm)")
    print(f"  - Moment capacity Mu         : {res_analytical.Mu_kNm:,.1f} kNm (Reference: 4,221.2 kNm)")
    print(f"  - Demand / Capacity ratio    : {res_analytical.utilization:.3f} <= 1.0")
    print(f"  - Verification status        : {'SAFE [PASS]' if res_analytical.is_safe else 'UNSAFE [FAIL]'}")

    # 4. SHEAR CAPACITY AND TRANSVERSE REINFORCEMENT (Mục 5.2)
    print("\n[4] TRANSVERSE REINFORCEMENT & SHEAR CAPACITY:")
    Q_design_kN = 450.0  # Applied shear force
    Asw_set = 2.0 * math.pi * (10.0**2) / 4.0  # 2 legs d10 = 157.08 mm^2
    sw_mm = 150.0  # Spacing 150 mm

    shear_check = check_wall_shear(
        Q_kN=Q_design_kN,
        N_kN=N_total_kN,
        b_mm=bw_mm,
        h0_mm=h0_mm,
        A_mm2=Ac,
        Rb_MPa=Rb_MPa,
        Rbt_MPa=Rbt_MPa,
        Rsw_MPa=Rsw_MPa,
        Asw_mm2=Asw_set,
        sw_mm=sw_mm,
    )

    print(f"  - Axial force factor phi_n   : {shear_check.phi_n:.3f}")
    print(f"  - Inclined strut max Qstrut  : {shear_check.Q_strut_max_kN:,.1f} kN (Applied: {Q_design_kN:.1f} kN)")
    print(f"  - Critical crack length C    : {shear_check.C_mm:,.1f} mm in [{h0_mm:.0f}, {2*h0_mm:.0f}] mm")
    print(f"  - Concrete shear Qb          : {shear_check.Qb_kN:,.1f} kN")
    print(f"  - Stirrups shear Qsw         : {shear_check.Qsw_kN:,.1f} kN")
    print(f"  - Total shear capacity Qcap  : {shear_check.Q_capacity_kN:,.1f} kN")
    print(f"  - Shear utilization ratio    : {shear_check.shear_utilization:.3f}")
    print(f"  - Shear status               : {'SAFE [PASS]' if shear_check.is_safe else 'UNSAFE [FAIL]'}")

    # 5. FIBER SECTION MODEL & P-M INTERACTION (Mục 6)
    print("\n[5] NONLINEAR FIBER MODEL & P-M INTERACTION ENVELOPE:")
    pm_curve = generate_pm_interaction_curve(
        section=wall,
        Rb_MPa=Rb_MPa,
        Rs_MPa=Rs_MPa,
        Rsc_MPa=Rsc_MPa,
        n_steps=25,
        max_fiber_size=40.0,
        bending_axis="x",
    )

    print(f"  - Pure compression N_max     : {pm_curve.N_max_kN:,.1f} kN")
    print(f"  - Pure tension N_min         : {pm_curve.N_min_kN:,.1f} kN")
    print(f"  - Peak moment capacity M_max : {pm_curve.M_max_pos_kNm:,.1f} kNm")

    # Evaluate point (N = 6000 kN, M = 3631 kNm)
    fiber_res = check_wall_interaction_dc(
        N_kN=N_total_kN,
        M_kNm=M_calc_kNm,
        curve=pm_curve,
    )

    print(f"  - Fiber capacity at N={N_total_kN:.0f}kN: {fiber_res.M_capacity_kNm:,.1f} kNm")
    print(f"  - Moment ratio |M|/M_cap     : {fiber_res.D_C_moment:.3f}")
    print(f"  - Radial D/C (OL/OC) ratio   : {fiber_res.D_C_radial:.3f}")
    print(f"  - Fiber verification status  : {'SAFE [PASS]' if fiber_res.is_safe else 'UNSAFE [FAIL]'}")

    print("\n" + "=" * 80)
    print("IN-PLANE BENCHMARK CHECKS COMPLETED AGAINST TCVN 5574:2018 GUIDELINE")
    print("=" * 80)


if __name__ == "__main__":
    run_wall_benchmark_example()
