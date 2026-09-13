"""Slenderness, random eccentricity, and buckling factor calculation for shear walls.

Implements Section 5.1.2 and Section 7 of TCVN 5574:2018 guideline (Decision 862/QD-BXD).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional


@dataclass
class WallBucklingResult:
    """Detailed buckling and slenderness calculation result for a shear wall."""

    l0_mm: float
    h_mm: float  # Section dimension in the bending direction
    ea_mm: float  # Random eccentricity ea = max(l0/600, h/30, 10 mm)
    e0_mm: float  # Initial eccentricity max(|M/N|, ea)
    slenderness: float  # lambda = l0 / i
    consider_buckling: bool  # True if lambda > 14
    delta_e: float  # e0 / h clamped to [0.15, 1.5]
    phi_l: float  # Creep/long-term load factor 1 + M1l / M1 <= 2.0
    kb: float  # Concrete flexural stiffness factor
    ks: float  # Steel stiffness factor (0.7)
    D_Nmm2: float  # Total bending stiffness D = kb*Eb*I + ks*Es*Is
    Ncr_N: float  # Critical Euler buckling load pi^2 * D / l0^2
    eta: float  # Buckling amplification factor 1 / (1 - N / Ncr) >= 1.0
    is_stable: bool  # False when N >= Ncr or no positive stiffness is available
    M_initial_kNm: float
    M_design_kNm: float  # Design moment including buckling effect


def random_eccentricity(l0_mm: float, h_mm: float) -> float:
    """Random eccentricity ea per TCVN 5574:2018: max(l0/600, h/30, 10 mm)."""
    if l0_mm <= 0.0 or h_mm <= 0.0:
        raise ValueError("l0_mm and h_mm must be positive")
    return max(l0_mm / 600.0, h_mm / 30.0, 10.0)


def calculate_wall_buckling_eta(
    N_N: float,
    M_Nmm: float,
    l0_mm: float,
    h_mm: float,
    I_mm4: float,
    A_mm2: float,
    Eb_MPa: float,
    Es_MPa: float = 200_000.0,
    Is_mm4: float = 0.0,
    phi_l: Optional[float] = None,
    M1_Nmm: Optional[float] = None,
    M1l_Nmm: Optional[float] = None,
) -> WallBucklingResult:
    """Calculate buckling magnification factor eta according to Section 5.1.2.

    Parameters:
        N_N: Axial compressive force, N (positive for compression).
        M_Nmm: First-order bending moment, N*mm.
        l0_mm: Effective length in the bending plane, mm.
        h_mm: Section dimension in the bending direction, mm.
        I_mm4: Moment of inertia of concrete section, mm^4.
        A_mm2: Gross area of concrete section, mm^2.
        Eb_MPa: Modulus of elasticity of concrete, MPa.
        Es_MPa: Modulus of elasticity of steel, MPa (default 200,000 MPa).
        Is_mm4: Moment of inertia of longitudinal rebar about section centroid, mm^4.
        phi_l: Long-term load factor (if known). If None, calculated from M1 and M1l.
        M1_Nmm: Total moment about tension rebar axis M + N * (h0 - a') / 2.
        M1l_Nmm: Long-term moment about tension rebar axis Ml + Nl * (h0 - a') / 2.
    """
    if l0_mm <= 0.0 or h_mm <= 0.0:
        raise ValueError("l0_mm and h_mm must be positive")
    if I_mm4 <= 0.0 or A_mm2 <= 0.0 or Eb_MPa <= 0.0 or Es_MPa <= 0.0:
        raise ValueError("section properties and elastic moduli must be positive")
    if Is_mm4 < 0.0:
        raise ValueError("Is_mm4 must be non-negative")
    ea = random_eccentricity(l0_mm, h_mm)

    if N_N <= 0.0:
        # Tension or pure moment - no buckling
        return WallBucklingResult(
            l0_mm=l0_mm,
            h_mm=h_mm,
            ea_mm=ea,
            e0_mm=0.0,
            slenderness=0.0,
            consider_buckling=False,
            delta_e=0.15,
            phi_l=1.0,
            kb=0.0,
            ks=0.7,
            D_Nmm2=0.0,
            Ncr_N=float("inf"),
            eta=1.0,
            is_stable=True,
            M_initial_kNm=abs(M_Nmm) * 1e-6,
            M_design_kNm=abs(M_Nmm) * 1e-6,
        )

    # Static eccentricity
    e0_static = abs(M_Nmm) / N_N
    e0 = max(e0_static, ea)

    # Radius of gyration and slenderness
    i_rad = math.sqrt(I_mm4 / A_mm2) if A_mm2 > 0 and I_mm4 > 0 else (h_mm / math.sqrt(12))
    slenderness = l0_mm / i_rad

    if slenderness <= 14.0:
        return WallBucklingResult(
            l0_mm=l0_mm,
            h_mm=h_mm,
            ea_mm=ea,
            e0_mm=e0,
            slenderness=slenderness,
            consider_buckling=False,
            delta_e=max(0.15, min(1.5, e0 / h_mm)),
            phi_l=1.0,
            kb=0.0,
            ks=0.7,
            D_Nmm2=0.0,
            Ncr_N=float("inf"),
            eta=1.0,
            is_stable=True,
            M_initial_kNm=N_N * e0 * 1e-6,
            M_design_kNm=N_N * e0 * 1e-6,
        )

    # delta_e clamped to [0.15, 1.5]
    delta_e = max(0.15, min(1.5, e0 / h_mm))

    # Long-term factor phi_l = 1 + M1l / M1 <= 2.0
    if phi_l is not None:
        calc_phi_l = min(2.0, max(1.0, phi_l))
    elif M1_Nmm is not None and M1l_Nmm is not None and M1_Nmm > 0.0:
        calc_phi_l = min(2.0, max(1.0, 1.0 + M1l_Nmm / M1_Nmm))
    else:
        calc_phi_l = 1.0

    # Concrete stiffness factor kb = 0.15 / (phi_l * (0.3 + delta_e))
    kb = 0.15 / (calc_phi_l * (0.3 + delta_e))
    ks = 0.7

    # Total stiffness D
    D = kb * Eb_MPa * I_mm4 + ks * Es_MPa * Is_mm4

    # Euler critical buckling load Ncr = pi^2 * D / l0^2
    Ncr = (math.pi**2 * D) / (l0_mm**2)

    # Buckling factor eta = 1 / (1 - N / Ncr)
    is_stable = Ncr > 0.0 and N_N < Ncr
    if not is_stable:
        eta = float("inf")
    else:
        eta = max(1.0, 1.0 / (1.0 - N_N / Ncr))

    # TCVN 5574:2018 5.1.2 amplifies the initial eccentricity e0.  Using
    # |M| directly would discard the mandatory accidental eccentricity when
    # the first-order moment is zero or smaller than N*ea.
    m_init_kNm = N_N * e0 * 1e-6
    m_design_kNm = m_init_kNm * eta

    return WallBucklingResult(
        l0_mm=l0_mm,
        h_mm=h_mm,
        ea_mm=ea,
        e0_mm=e0,
        slenderness=slenderness,
        consider_buckling=True,
        delta_e=delta_e,
        phi_l=calc_phi_l,
        kb=kb,
        ks=ks,
        D_Nmm2=D,
        Ncr_N=Ncr,
        eta=eta,
        is_stable=is_stable,
        M_initial_kNm=m_init_kNm,
        M_design_kNm=m_design_kNm,
    )


def calculate_combined_wall_moments(
    M_v_kNm: float,
    eta_v: float,
    M_h_kNm: float,
    eta_h: float,
) -> float:
    """Calculate combined design moment per Section 7: M = Mv * eta_v + Mh * eta_h."""
    return M_v_kNm * eta_v + M_h_kNm * eta_h
