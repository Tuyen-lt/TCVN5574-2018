"""Transverse reinforcement and shear capacity calculation for RC shear walls.

Implements Section 5.2 of TCVN 5574:2018 guideline (Decision 862/QD-BXD).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional


@dataclass
class WallShearCheckResult:
    """Shear check result for a shear wall per Section 5.2."""

    Q_kN: float  # Applied shear force
    N_kN: float  # Applied axial force (positive = compression)
    b_mm: float  # Wall web thickness
    h0_mm: float  # Effective depth in wall length direction
    sigma_m_MPa: float  # Average compressive or tensile stress
    phi_n: float  # Axial force coefficient
    Q_strut_max_kN: float  # Inclined concrete strut limit (Eq 5-37)
    strut_ok: bool
    strut_utilization: float
    C_mm: float  # Critical diagonal crack projection length
    Qb_kN: float  # Concrete shear capacity in inclined section (Eq 5-39)
    Qsw_kN: float  # Stirrup shear capacity in inclined section (Eq 5-40)
    Q_capacity_kN: float  # Total capacity Qb + Qsw (Eq 5-38)
    shear_ok: bool
    shear_utilization: float
    governing_utilization: float
    is_safe: bool


@dataclass
class WallShearDesignResult:
    """Design result for wall transverse reinforcement."""

    Q_kN: float
    N_kN: float
    b_mm: float
    h0_mm: float
    phi_n: float
    strut_ok: bool
    Q_strut_max_kN: float
    q_sw_required_N_per_mm: float
    sw_required_mm: float  # Maximum spacing for given stirrup rebar
    sw_selected_mm: float  # Practical rounded spacing
    asw_provided_mm2: float
    design_feasible: bool  # Selected bar set can satisfy strength and spacing constraints
    check_result: WallShearCheckResult


def calculate_phi_n(
    N_N: float,
    A_mm2: float,
    Rb_MPa: float,
    Rbt_MPa: float,
) -> float:
    """Calculate axial stress coefficient phi_n per Section 5.2 of the guideline.

    Parameters:
        N_N: Axial force, N (positive = compression, negative = tension).
        A_mm2: Gross concrete cross-sectional area, mm^2.
        Rb_MPa: Concrete compressive design strength, MPa.
        Rbt_MPa: Concrete tensile design strength, MPa.
    """
    if A_mm2 <= 0.0 or Rb_MPa <= 0.0:
        return 1.0

    if N_N >= 0.0:
        # Compression
        sigma_m = N_N / A_mm2
        ratio = sigma_m / Rb_MPa
        if ratio <= 0.25:
            return 1.0 + ratio
        elif ratio <= 0.75:
            return 1.25
        elif ratio <= 1.0:
            return max(0.0, 5.0 * (1.0 - ratio))
        else:
            return 0.0
    else:
        # Tension
        sigma_t = abs(N_N) / A_mm2
        if Rbt_MPa <= 0.0:
            return 0.5
        ratio_t = sigma_t / (2.0 * Rbt_MPa)
        if sigma_t <= Rbt_MPa:
            return max(0.0, 1.0 - ratio_t)
        else:
            return 0.5


def check_wall_shear(
    Q_kN: float,
    N_kN: float,
    b_mm: float,
    h0_mm: float,
    A_mm2: float,
    Rb_MPa: float,
    Rbt_MPa: float,
    Rsw_MPa: float,
    Asw_mm2: float,
    sw_mm: float,
) -> WallShearCheckResult:
    """Verify shear resistance of a wall web according to Section 5.2.

    Parameters:
        Q_kN: Design shear force, kN.
        N_kN: Design axial force, kN (positive = compression).
        b_mm: Web thickness, mm.
        h0_mm: Effective depth of wall length, mm.
        A_mm2: Cross-sectional concrete area, mm^2.
        Rb_MPa: Design compressive strength of concrete, MPa.
        Rbt_MPa: Design tensile strength of concrete, MPa.
        Rsw_MPa: Design strength of transverse reinforcement, MPa.
        Asw_mm2: Total cross-sectional area of transverse bars per spacing sw, mm^2.
        sw_mm: Spacing of transverse bars, mm.
    """
    if b_mm <= 0.0 or h0_mm <= 0.0 or A_mm2 <= 0.0:
        raise ValueError("b_mm, h0_mm and A_mm2 must be positive")
    if Rb_MPa <= 0.0 or Rbt_MPa <= 0.0 or Rsw_MPa < 0.0:
        raise ValueError("material strengths must be positive (Rsw may be zero)")
    if Asw_mm2 < 0.0 or sw_mm <= 0.0:
        raise ValueError("Asw_mm2 must be non-negative and sw_mm must be positive")
    Q_N = abs(Q_kN) * 1e3
    N_N = N_kN * 1e3

    phi_n = calculate_phi_n(N_N, A_mm2, Rb_MPa, Rbt_MPa)
    sigma_m = N_N / A_mm2 if A_mm2 > 0 else 0.0

    # 1. Inclined concrete strut check: Q <= 0.3 * phi_n * Rb * b * h0 (Eq 5-37)
    Q_strut_max_N = 0.3 * phi_n * Rb_MPa * b_mm * h0_mm
    strut_ok = Q_N <= Q_strut_max_N
    strut_util = Q_N / Q_strut_max_N if Q_strut_max_N > 0 else float("inf")

    # 2. Diagonal tension crack check: Q <= Qb + Qsw (Eq 5-38)
    q_sw = (Asw_mm2 * Rsw_MPa) / sw_mm if sw_mm > 0 else 0.0

    # Critical crack projection length C within [h0, 2*h0]
    # C_crit = sqrt(2 * phi_n * Rbt * b * h0^2 / q_sw)
    if q_sw > 0.0:
        c_theory = math.sqrt((2.0 * phi_n * Rbt_MPa * b_mm * (h0_mm**2)) / q_sw)
        C_mm = max(h0_mm, min(2.0 * h0_mm, c_theory))
    else:
        C_mm = 2.0 * h0_mm  # Most conservative when no shear reinforcement

    # Qb = 1.5 * phi_n * Rbt * b * h0^2 / C clamped to [0.5, 2.5] * phi_n * Rbt * b * h0
    qb_raw = (1.5 * phi_n * Rbt_MPa * b_mm * (h0_mm**2)) / C_mm if C_mm > 0 else 0.0
    qb_min = 0.5 * phi_n * Rbt_MPa * b_mm * h0_mm
    qb_max = 2.5 * phi_n * Rbt_MPa * b_mm * h0_mm
    Qb_N = max(qb_min, min(qb_max, qb_raw))

    # Qsw = 0.75 * q_sw * C
    Qsw_N = 0.75 * q_sw * C_mm

    Q_capacity_N = Qb_N + Qsw_N
    shear_ok = Q_N <= Q_capacity_N
    shear_util = Q_N / Q_capacity_N if Q_capacity_N > 0 else float("inf")

    governing_util = max(strut_util, shear_util)
    is_safe = strut_ok and shear_ok

    return WallShearCheckResult(
        Q_kN=abs(Q_kN),
        N_kN=N_kN,
        b_mm=b_mm,
        h0_mm=h0_mm,
        sigma_m_MPa=sigma_m,
        phi_n=phi_n,
        Q_strut_max_kN=Q_strut_max_N * 1e-3,
        strut_ok=strut_ok,
        strut_utilization=strut_util,
        C_mm=C_mm,
        Qb_kN=Qb_N * 1e-3,
        Qsw_kN=Qsw_N * 1e-3,
        Q_capacity_kN=Q_capacity_N * 1e-3,
        shear_ok=shear_ok,
        shear_utilization=shear_util,
        governing_utilization=governing_util,
        is_safe=is_safe,
    )


def design_wall_shear(
    Q_kN: float,
    N_kN: float,
    b_mm: float,
    h0_mm: float,
    A_mm2: float,
    Rb_MPa: float,
    Rbt_MPa: float,
    Rsw_MPa: float,
    stirrup_diameter_mm: float = 10.0,
    n_legs: int = 2,
    max_sw_mm: float = 200.0,
) -> WallShearDesignResult:
    """Calculate required spacing sw of horizontal bars to satisfy shear capacity.

    Parameters:
        Q_kN: Design shear force, kN.
        N_kN: Design axial force, kN (positive = compression).
        b_mm: Web thickness, mm.
        h0_mm: Effective depth of wall length, mm.
        A_mm2: Cross-sectional concrete area, mm^2.
        Rb_MPa: Design compressive strength of concrete, MPa.
        Rbt_MPa: Design tensile strength of concrete, MPa.
        Rsw_MPa: Design strength of transverse reinforcement, MPa.
        stirrup_diameter_mm: Rebar diameter of transverse bar, mm.
        n_legs: Number of horizontal bar curtains (normally 2 for two faces).
        max_sw_mm: Maximum allowable spacing (code limit, usually 200-300 mm).
    """
    if n_legs <= 0 or stirrup_diameter_mm <= 0.0 or max_sw_mm <= 0.0:
        raise ValueError("bar diameter, number of legs and maximum spacing must be positive")
    if b_mm <= 0.0 or h0_mm <= 0.0 or A_mm2 <= 0.0:
        raise ValueError("b_mm, h0_mm and A_mm2 must be positive")
    if Rb_MPa <= 0.0 or Rbt_MPa <= 0.0 or Rsw_MPa <= 0.0:
        raise ValueError("material strengths must be positive")
    Q_N = abs(Q_kN) * 1e3
    N_N = N_kN * 1e3

    phi_n = calculate_phi_n(N_N, A_mm2, Rb_MPa, Rbt_MPa)
    Q_strut_max_N = 0.3 * phi_n * Rb_MPa * b_mm * h0_mm
    strut_ok = Q_N <= Q_strut_max_N

    asw_one_set = n_legs * math.pi * (stirrup_diameter_mm**2) / 4.0

    # If concrete alone at maximum crack C = 2*h0 can resist shear:
    qb_min = 0.5 * phi_n * Rbt_MPa * b_mm * h0_mm
    # Qb at C = 2*h0: 1.5 * phi_n * Rbt * b * h0^2 / (2*h0) = 0.75 * phi_n * Rbt * b * h0
    qb_at_2h0 = 0.75 * phi_n * Rbt_MPa * b_mm * h0_mm

    if Q_N <= qb_at_2h0:
        # Minimum constructive shear reinforcement
        sw_req = max_sw_mm
        sw_selected = max_sw_mm
        q_sw_req = (asw_one_set * Rsw_MPa) / sw_selected
    else:
        # Need transverse reinforcement.
        # Find required q_sw so that Qb(C) + Qsw(C) >= Q_N
        # From Eq 5-38 & 5-40:
        # If C is at C_crit = sqrt(2 * phi_n * Rbt * b * h0^2 / q_sw):
        # Qb + Qsw = sqrt(2 * 1.5 * 0.75 * phi_n * Rbt * b * h0^2 * q_sw) * ...
        # Standard approach: solve for q_sw at C in [h0, 2*h0]
        # At C = h0: Qsw = 0.75 * q_sw * h0, Qb = 1.5 * phi_n * Rbt * b * h0
        # q_sw >= (Q_N - Qb) / (0.75 * C)
        # Solve analytically or iterate:
        best_q_sw = 0.0
        # Search q_sw using binary search
        low = 0.0
        high = max(100.0, Q_N / (0.75 * h0_mm))
        for _ in range(50):
            mid = (low + high) / 2.0
            # compute capacity with this q_sw
            c_crit = math.sqrt((2.0 * phi_n * Rbt_MPa * b_mm * (h0_mm**2)) / mid) if mid > 0 else 2 * h0_mm
            c_use = max(h0_mm, min(2.0 * h0_mm, c_crit))
            qb_use = max(qb_min, min(2.5 * phi_n * Rbt_MPa * b_mm * h0_mm, (1.5 * phi_n * Rbt_MPa * b_mm * (h0_mm**2)) / c_use))
            qsw_use = 0.75 * mid * c_use
            cap = qb_use + qsw_use
            if cap >= Q_N:
                best_q_sw = mid
                high = mid
            else:
                low = mid

        q_sw_req = best_q_sw
        sw_raw = (asw_one_set * Rsw_MPa) / q_sw_req if q_sw_req > 0 else max_sw_mm
        # Preserve the actual strength-required spacing in the result.  The
        # selected spacing is separately limited to the practical minimum.
        sw_req = min(max_sw_mm, sw_raw)
        sw_for_selection = max(50.0, sw_req)
        # Round down to practical step (e.g. multiples of 25 mm or 50 mm)
        sw_selected = math.floor(sw_for_selection / 25.0) * 25.0
        if sw_selected < 50.0:
            sw_selected = 50.0

    # Perform final verification with chosen spacing
    check = check_wall_shear(
        Q_kN=Q_kN,
        N_kN=N_kN,
        b_mm=b_mm,
        h0_mm=h0_mm,
        A_mm2=A_mm2,
        Rb_MPa=Rb_MPa,
        Rbt_MPa=Rbt_MPa,
        Rsw_MPa=Rsw_MPa,
        Asw_mm2=asw_one_set,
        sw_mm=sw_selected,
    )

    return WallShearDesignResult(
        Q_kN=abs(Q_kN),
        N_kN=N_kN,
        b_mm=b_mm,
        h0_mm=h0_mm,
        phi_n=phi_n,
        strut_ok=strut_ok,
        Q_strut_max_kN=Q_strut_max_N * 1e-3,
        q_sw_required_N_per_mm=q_sw_req,
        sw_required_mm=sw_req,
        sw_selected_mm=sw_selected,
        asw_provided_mm2=asw_one_set,
        design_feasible=check.is_safe,
        check_result=check,
    )
