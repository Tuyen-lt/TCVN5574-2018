"""Flexural design and capacity check for reinforced concrete beams per TCVN 5574-2018."""

import math
from dataclasses import dataclass
from typing import Optional

from tcvn5574.constants import EPSILON_B2_SHORT_TERM, MU_MIN_PERCENT
from tcvn5574.materials.concrete import Concrete
from tcvn5574.materials.rebar import Rebar
from tcvn5574.sections.rectangular import RectangularBeamSection


@dataclass
class FlexureDesignResult:
    """Result of flexural reinforcement design."""

    M_kNm: float  # Applied bending moment in kNm
    b_mm: float  # Beam width in mm
    h_mm: float  # Beam height in mm
    h0_mm: float  # Effective depth in mm
    a_mm: float  # Assumed or provided tensile cover distance in mm
    a_prime_mm: float  # Assumed or provided compressive cover distance in mm
    Rb: float  # Effective concrete compressive strength in MPa
    Rs: float  # Effective rebar tensile strength in MPa
    Rsc: float  # Effective rebar compressive strength in MPa
    xi_R: float  # Relative compression zone boundary limit
    alpha_R: float  # Relative moment boundary limit
    alpha_m: float  # Dimensionless moment factor
    xi: float  # Relative compression zone depth
    x_mm: float  # Depth of compression zone in mm
    is_double_reinforced: bool  # True if compression steel is required
    As_required_mm2: float  # Required tensile steel area in mm²
    Asc_required_mm2: float  # Required compressive steel area in mm²
    As_required_cm2: float  # Required tensile steel area in cm²
    Asc_required_cm2: float  # Required compressive steel area in cm²
    mu_percent: float  # Reinforcement ratio in %
    mu_min_percent: float  # Minimum reinforcement ratio in %
    mu_max_percent: float  # Maximum singly-reinforced ratio in %


@dataclass
class FlexureCheckResult:
    """Result of flexural capacity check for a beam with provided rebar."""

    M_kNm: float  # Applied bending moment in kNm
    Mu_kNm: float  # Ultimate moment resistance capacity in kNm
    utilization_ratio: float  # M / Mu
    is_safe: bool  # True if M <= Mu
    x_mm: float  # Depth of compression zone in mm
    xi: float  # Relative depth x / h0
    xi_R: float  # Boundary limit xi_R
    alpha_m: float  # alpha_m factor
    failure_mode: str  # Description of section state (Ductile, Over-reinforced, x < 2a', etc.)
    method: str = "limit_force"  # "limit_force" (8.1.2.3) or "nonlinear" (8.1.2.7)
    N_kN: float = 0.0  # axial force used (nonlinear only; compression +)


def calculate_xi_R(
    Rs: float,
    Es: float,
    epsilon_b2: float = EPSILON_B2_SHORT_TERM,
) -> float:
    """Calculate relative boundary depth of compression zone xi_R (Điều 8.1.2.2.1).

    xi_R = 0.8 / (1 + (Rs / Es) / epsilon_b2)
    """
    epsilon_s_el = Rs / Es
    return 0.8 / (1.0 + (epsilon_s_el / epsilon_b2))


def calculate_alpha_R(xi_R: float) -> float:
    """Calculate boundary moment factor alpha_R = xi_R * (1 - 0.5 * xi_R)."""
    return xi_R * (1.0 - 0.5 * xi_R)


def design_beam_flexure(
    M_kNm: float,
    b_mm: float,
    h_mm: float,
    concrete: Concrete,
    rebar: Rebar,
    a_mm: float = 40.0,
    a_prime_mm: float = 40.0,
    bf_mm: Optional[float] = None,
    hf_mm: float = 0.0,
) -> FlexureDesignResult:
    """Design tensile and compressive longitudinal rebar for rectangular or T beam
    (flange in compression, 8.1.2.3.3). bf_mm must already respect the 8.1.2.3.4 limits.

    Args:
        M_kNm: Applied bending moment (kNm) (positive value)
        b_mm: Beam width (mm)
        h_mm: Beam height (mm)
        concrete: Concrete material
        rebar: Rebar material
        a_mm: Assumed distance from tension edge to rebar centroid (mm)
        a_prime_mm: Assumed distance from compression edge to rebar centroid (mm)

    Returns:
        FlexureDesignResult
    """
    M_Nmm = abs(M_kNm) * 1e6
    h0 = max(10.0, h_mm - a_mm)
    Rb = concrete.Rb_calc
    Rs = rebar.Rs_calc
    Rsc = rebar.Rsc_calc
    Es = rebar.Es

    xi_R = calculate_xi_R(Rs, Es)
    alpha_R = calculate_alpha_R(xi_R)

    # T-section: flange term used only when the neutral axis falls in the web (CT 36-38)
    M_f = 0.0
    N_f = 0.0
    if bf_mm and hf_mm > 0 and bf_mm > b_mm:
        if M_Nmm <= Rb * bf_mm * hf_mm * (h0 - 0.5 * hf_mm):
            b_mm_eff = bf_mm  # neutral axis in the flange: rectangle of width bf
        else:
            b_mm_eff = b_mm
            N_f = Rb * (bf_mm - b_mm) * hf_mm
            M_f = N_f * (h0 - 0.5 * hf_mm)
    else:
        b_mm_eff = b_mm

    denom = Rb * b_mm_eff * (h0**2)
    alpha_m = (M_Nmm - M_f) / denom if denom > 0 else 0.0

    mu_min = MU_MIN_PERCENT
    mu_max = xi_R * (Rb / Rs) * 100.0

    if alpha_m <= alpha_R:
        is_double = False
        xi = 1.0 - math.sqrt(max(0.0, 1.0 - 2.0 * alpha_m))
        x_mm = xi * h0
        As_calc = (xi * Rb * b_mm_eff * h0 + N_f) / Rs
        Asc_calc = 0.0
    else:
        is_double = True
        xi = xi_R
        x_mm = xi_R * h0
        delta_M = max(0.0, M_Nmm - M_f - alpha_R * denom)
        Asc_calc = delta_M / (Rsc * max(10.0, h0 - a_prime_mm))
        As_calc = (xi_R * Rb * b_mm_eff * h0 + N_f + Rsc * Asc_calc) / Rs

    # Check minimum reinforcement
    As_min = (mu_min / 100.0) * b_mm * h0
    As_final = max(As_calc, As_min)
    mu_final = (As_final / (b_mm * h0)) * 100.0

    return FlexureDesignResult(
        M_kNm=abs(M_kNm),
        b_mm=b_mm,
        h_mm=h_mm,
        h0_mm=h0,
        a_mm=a_mm,
        a_prime_mm=a_prime_mm,
        Rb=Rb,
        Rs=Rs,
        Rsc=Rsc,
        xi_R=round(xi_R, 4),
        alpha_R=round(alpha_R, 4),
        alpha_m=round(alpha_m, 4),
        xi=round(xi, 4),
        x_mm=round(x_mm, 2),
        is_double_reinforced=is_double,
        As_required_mm2=round(As_final, 2),
        Asc_required_mm2=round(Asc_calc, 2),
        As_required_cm2=round(As_final / 100.0, 2),
        Asc_required_cm2=round(Asc_calc / 100.0, 2),
        mu_percent=round(mu_final, 3),
        mu_min_percent=mu_min,
        mu_max_percent=round(mu_max, 3),
    )


def check_beam_flexure(
    M_kNm: float,
    section: RectangularBeamSection,
    concrete: Concrete,
    rebar: Rebar,
    nonlinear: bool = False,
    N_kN: float = 0.0,
) -> FlexureCheckResult:
    """Check flexural capacity of a beam section with provided reinforcement.

    Args:
        M_kNm: Applied bending moment (kNm). With nonlinear=True the sign matters: M >= 0 compresses the
            comp_rebar face, M < 0 the tensile_rebar face.
        section: RectangularBeamSection with provided tensile and comp rebar
        concrete: Concrete material
        rebar: Rebar material
        nonlinear: False -> limit-force method (8.1.2.3, N ignored); True -> nonlinear deformation model
            (8.1.2.7, needs concreteproperties), with axial force N_kN.
        N_kN: Axial force (compression +), nonlinear model only.

    Returns:
        FlexureCheckResult
    """
    if nonlinear:
        return _check_nonlinear(M_kNm, section, concrete, rebar, N_kN)
    M_Nmm = abs(M_kNm) * 1e6
    b = section.b
    h0 = section.h0
    a_prime = section.a_prime
    As = section.As
    Asc = section.Asc

    Rb = concrete.Rb_calc
    Rs = rebar.Rs_calc
    Rsc = rebar.Rsc_calc
    Es = rebar.Es

    xi_R = calculate_xi_R(Rs, Es)
    alpha_R = calculate_alpha_R(xi_R)

    # T-section with flange in compression (8.1.2.3.3, CT 36-38)
    bf, hf = section.bf, section.hf
    N_f = M_f = 0.0
    width = b
    if section.has_compression_flange:
        if Rs * As <= Rb * bf * hf + Rsc * Asc:  # CT (36): neutral axis in the flange
            width = bf
        else:
            N_f = Rb * (bf - b) * hf
            M_f = N_f * (h0 - 0.5 * hf)

    # Equilibrium: Rb * width * x + N_f + Rsc * Asc = Rs * As (CT 35, 38)
    x = (Rs * As - Rsc * Asc - N_f) / (Rb * width) if width > 0 and Rb > 0 else 0.0
    xi = x / h0 if h0 > 0 else 0.0

    if Asc > 0 and x <= 2.0 * a_prime:
        # compression steel not yielded: moment about compression steel
        Mu_Nmm = Rs * As * max(0.0, h0 - a_prime)
        failure_mode = "x <= 2a' (Mu = Rs*As*(h0-a'))"
        alpha_m = 0.0
    elif xi <= xi_R:
        alpha_m = xi * (1.0 - 0.5 * xi)
        Mu_Nmm = Rb * width * x * (h0 - 0.5 * x) + M_f + Rsc * Asc * (h0 - a_prime)
        failure_mode = "Ductile (x <= xi_R*h0)"
    else:
        # 8.1.2.3.5: take x = xi_R * h0
        Mu_Nmm = alpha_R * Rb * width * h0**2 + M_f + Rsc * Asc * (h0 - a_prime)
        failure_mode = "Over-reinforced (xi > xi_R, x = xi_R*h0 used)"
        alpha_m = alpha_R

    Mu_kNm = Mu_Nmm / 1e6
    ur = (abs(M_kNm) / Mu_kNm) if Mu_kNm > 0 else 999.0
    is_safe = (abs(M_kNm) <= Mu_kNm + 1e-4)

    return FlexureCheckResult(
        M_kNm=abs(M_kNm),
        Mu_kNm=round(Mu_kNm, 2),
        utilization_ratio=round(ur, 3),
        is_safe=is_safe,
        x_mm=round(x, 2),
        xi=round(xi, 4),
        xi_R=round(xi_R, 4),
        alpha_m=round(alpha_m, 4),
        failure_mode=failure_mode,
    )


def _check_nonlinear(M_kNm, section, concrete, rebar, N_kN) -> FlexureCheckResult:
    """Nonlinear deformation model (8.1.2.7): Mu_neg(N) <= M <= Mu_pos(N)."""
    from tcvn5574.nonlinear import to_concrete_section

    code, _ = to_concrete_section(section, concrete.grade.value, rebar.grade.value, gamma_b=concrete.gamma_b)
    theta = 0.0 if M_kNm >= 0 else math.pi
    r = code.ultimate_bending_capacity(theta=theta, n=N_kN * 1e3)
    ok, mu_neg, mu_pos = code.check_point(N_kN * 1e3, M_kNm * 1e6)
    Mu = (mu_pos if M_kNm >= 0 else -mu_neg) / 1e6
    ur = abs(M_kNm) / Mu if Mu > 0 else 999.0
    h0 = section.h0
    return FlexureCheckResult(
        M_kNm=abs(M_kNm),
        Mu_kNm=round(Mu, 2),
        utilization_ratio=round(ur, 3),
        is_safe=ok,
        x_mm=round(r.d_n, 2) if math.isfinite(r.d_n) else float("inf"),
        xi=round(r.d_n / h0, 4) if math.isfinite(r.d_n) else float("inf"),
        xi_R=round(calculate_xi_R(rebar.Rs_calc, rebar.Es), 4),
        alpha_m=0.0,
        failure_mode=f"Nonlinear 8.1.2.7: governing = {r.governing}, eps_b = {r.eps_b_max:.5f}, eps_s = {r.eps_s_max:.5f}",
        method="nonlinear",
        N_kN=N_kN,
    )
