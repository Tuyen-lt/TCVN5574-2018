"""Analytical capacity equations for flanged and rectangular shear walls per TCVN 5574:2018.

Implements Section 6.4 and Section 7 of the guideline (MOC Decision 862/QD-BXD).
Provides direct closed-form verification exactly matching the benchmark example (pp. 36-40).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class WallAnalyticalResult:
    """Analytical capacity calculation result for a flanged or rectangular wall."""

    N_kN: float  # Design axial compressive force
    M_calc_kNm: float  # Design bending moment (including buckling eta)
    h_mm: float  # Total wall length in bending plane
    b_mm: float  # Web thickness
    bf_prime_mm: float  # Compression flange width
    hf_prime_mm: float  # Compression flange thickness
    h0_mm: float  # Effective depth h - a
    a_mm: float  # Tension steel centroid distance to edge
    a_prime_mm: float  # Compression steel centroid distance to edge
    As_mm2: float  # Boundary tension steel area
    As_prime_mm2: float  # Boundary compression steel area
    xi: float  # Neutral axis ratio
    xi_R: float  # Boundary limit neutral axis ratio
    case: str  # "large_eccentricity" or "small_eccentricity"
    x_mm: float  # Compression zone depth
    Mu_kNm: float  # Ultimate moment capacity
    utilization: float  # M_calc / Mu
    is_safe: bool  # M_calc <= Mu


def check_wall_analytical_flanged(
    N_kN: float,
    M_calc_kNm: float,
    h_mm: float,
    b_mm: float,
    bf_prime_mm: float,
    hf_prime_mm: float,
    As_mm2: float,
    As_prime_mm2: float,
    a_mm: float,
    a_prime_mm: float,
    Rb_MPa: float,
    Rs_MPa: float,
    Rsc_MPa: float,
    xi_R: float = 0.533,
) -> WallAnalyticalResult:
    """Analytical flexural capacity for a flanged shear wall per Section 7.

    Parameters:
        N_kN: Design axial force, kN (compression positive).
        M_calc_kNm: Factored design moment (with slenderness eta), kNm.
        h_mm: Section depth / length in the bending plane, mm.
        b_mm: Web thickness, mm.
        bf_prime_mm: Compression flange width, mm.
        hf_prime_mm: Compression flange thickness, mm.
        As_mm2: Area of boundary reinforcement at tension edge, mm^2.
        As_prime_mm2: Area of boundary reinforcement at compression edge, mm^2.
        a_mm: Distance from tension edge to tension steel centroid, mm.
        a_prime_mm: Distance from compression edge to compression steel centroid, mm.
        Rb_MPa: Concrete compressive strength, MPa.
        Rs_MPa: Rebar tensile yield strength, MPa.
        Rsc_MPa: Rebar compressive yield strength, MPa.
        xi_R: Boundary relative compression zone depth (default 0.533 for CB400-V).
    """
    N_N = N_kN * 1e3
    M_calc_Nmm = M_calc_kNm * 1e6
    h0_mm = h_mm - a_mm

    # Flange overhang area
    A_ov = (bf_prime_mm - b_mm) * hf_prime_mm if bf_prime_mm > b_mm else 0.0

    # Relative neutral axis depth indicator: xi = (N - Rb * Aov) / (Rb * b * h0)
    denom_Rb_b_h0 = Rb_MPa * b_mm * h0_mm
    xi = (N_N - Rb_MPa * A_ov) / denom_Rb_b_h0 if denom_Rb_b_h0 > 0 else 1.0

    if xi > xi_R:
        case = "small_eccentricity"  # xi > xi_R: Tension rebar not yielding
        alpha_s = (Rs_MPa * As_mm2) / denom_Rb_b_h0
        alpha_n = N_N / denom_Rb_b_h0
        alpha_ov = A_ov / (b_mm * h0_mm)

        # Formula from Section 7 (p. 39):
        # x = h0 * [ (alpha_n - alpha_ov)*(1 - xi_R) + 2*alpha_s*xi_R ] / [ 1 - xi_R + 2*alpha_s ]
        numerator = (alpha_n - alpha_ov) * (1.0 - xi_R) + 2.0 * alpha_s * xi_R
        denominator = 1.0 - xi_R + 2.0 * alpha_s
        x_mm = h0_mm * (numerator / denominator)
    else:
        case = "large_eccentricity"  # xi <= xi_R: Tension rebar yields
        x_mm = (N_N + Rs_MPa * As_mm2 - Rsc_MPa * As_prime_mm2 - Rb_MPa * A_ov) / (
            Rb_MPa * b_mm
        )
        x_mm = max(2.0 * a_prime_mm, min(h0_mm, x_mm))

    # Ultimate moment capacity Mu per Section 7 (p. 39):
    # Mu = Rb * b * x * (h0 - x/2) + Rb * Aov * (h0 - hf'/2) + (Rsc * As' - N/2) * (h0 - a')
    term_web = Rb_MPa * b_mm * x_mm * (h0_mm - x_mm / 2.0)
    term_flange = Rb_MPa * A_ov * (h0_mm - hf_prime_mm / 2.0)
    term_rebar = (Rsc_MPa * As_prime_mm2 - N_N / 2.0) * (h0_mm - a_prime_mm)

    Mu_Nmm = term_web + term_flange + term_rebar
    Mu_kNm = Mu_Nmm * 1e-6

    utilization = (M_calc_kNm / Mu_kNm) if Mu_kNm > 0 else float("inf")
    is_safe = (M_calc_kNm <= Mu_kNm) and (utilization <= 1.0)

    return WallAnalyticalResult(
        N_kN=N_kN,
        M_calc_kNm=M_calc_kNm,
        h_mm=h_mm,
        b_mm=b_mm,
        bf_prime_mm=bf_prime_mm,
        hf_prime_mm=hf_prime_mm,
        h0_mm=h0_mm,
        a_mm=a_mm,
        a_prime_mm=a_prime_mm,
        As_mm2=As_mm2,
        As_prime_mm2=As_prime_mm2,
        xi=xi,
        xi_R=xi_R,
        case=case,
        x_mm=x_mm,
        Mu_kNm=Mu_kNm,
        utilization=utilization,
        is_safe=is_safe,
    )
