"""Shear design and checking for reinforced concrete beams per TCVN 5574:2018 (Điều 8.1.3)."""

import math
from dataclasses import dataclass

from tcvn5574.materials.concrete import Concrete
from tcvn5574.materials.rebar import Rebar, bar_area
from tcvn5574.sections.rectangular import RectangularBeamSection

PHI_B1 = 0.3  # 8.1.3.2, CT (88)
PHI_B2 = 1.5  # 8.1.3.3.1, CT (90)
PHI_SW = 0.75  # 8.1.3.3.1, CT (91)


@dataclass
class ShearCheckResult:
    """Result of shear capacity verification per TCVN 5574:2018."""

    Q_kN: float
    b_mm: float
    h_mm: float
    h0_mm: float
    stirrup_diameter_mm: float
    n_legs: int
    s_mm: float

    Q_max_strut_kN: float  # 0.3 Rb b h0 (CT 88)
    is_strut_safe: bool

    qsw_N_per_mm: float  # Rsw Asw / sw (CT 92)
    is_qsw_min_ok: bool  # qsw >= 0.25 Rbt b (CT 96); if False Qb uses CT (97)
    C_mm: float  # most dangerous inclined section projection
    Qb_kN: float
    Qsw_kN: float
    Qu_kN: float  # min over C of Qb + Qsw + q1*C
    utilization_ratio: float
    is_safe: bool

    s_max_calc_mm: float  # sw,max = Rbt b h0^2 / Q (CT 98)
    s_max_constructive_mm: float  # 10.3.4.3
    is_spacing_ok: bool


@dataclass
class ShearDesignResult:
    """Result of required stirrup spacing design."""

    Q_kN: float
    b_mm: float
    h_mm: float
    h0_mm: float
    stirrup_diameter_mm: float
    n_legs: int
    s_required_mm: float  # spacing to use (rounded down to 10 mm)
    s_calc_mm: float  # exact spacing from strength
    s_max_code_mm: float  # min(sw,max, constructive limit)
    is_shear_reinforcement_needed: bool  # False if Q <= 0.5 Rbt b h0
    Q_max_strut_kN: float
    is_section_adequate: bool  # strut OK and s_required >= 50 mm


def shear_capacity(qsw: float, Rbt: float, b: float, h0: float, q1: float = 0.0, C_max: float = None):
    """Qu = min over C of Qb(C) + Qsw(C) + q1*C per 8.1.3.3.1. Returns (Qu, Qb, Qsw, C) in N, N, N, mm.

    Q (at the support / start of the inclined section) is compared with Qu; q1 (N/mm) is the
    distributed load on the inclined section (Đoàn Thị Quỳnh Mai: q1 = g + 0.5p), 0 = conservative.
    Qb = 1.5 Rbt b h0^2 / C (CT 90), or 4*1.5*h0^2*qsw/C when qsw < 0.25 Rbt b (CT 97),
    bounded to [0.5, 2.5] Rbt b h0. Qsw = 0.75 qsw C, C in (91) taken within [h0, 2h0].
    C_max: distance to the first concentrated load (default 3h0; beyond it Qb, Qsw no longer change).
    """
    qb_base = Rbt * b if qsw >= 0.25 * Rbt * b else 4.0 * qsw
    lo, hi = 0.5 * Rbt * b * h0, 2.5 * Rbt * b * h0
    C_max = 3.0 * h0 if C_max is None else min(C_max, 3.0 * h0)
    best = None
    # ponytail: 600-step scan of C, exact to <0.1% and branch-free
    for i in range(601):
        C = C_max * i / 600
        Qb = hi if C == 0 else min(hi, max(lo, PHI_B2 * qb_base * h0**2 / C))
        Qsw = PHI_SW * qsw * min(max(C, h0), 2.0 * h0)
        Qu = Qb + Qsw + q1 * C
        if best is None or Qu < best[0]:
            best = (Qu, Qb, Qsw, C)
    return best


def _constructive_spacing(h0: float, stirrups_needed: bool) -> float:
    """10.3.4.3: <= 0.5h0 and 300 mm where stirrups carry shear, else <= 0.75h0 and 500 mm."""
    return min(0.5 * h0, 300.0) if stirrups_needed else min(0.75 * h0, 500.0)


def check_beam_shear(
    Q_kN: float,
    section: RectangularBeamSection,
    concrete: Concrete,
    stirrup_rebar: Rebar,
    stirrup_diameter_mm: float,
    n_legs: int,
    s_mm: float,
    q1_kN_per_m: float = 0.0,
    a_load_mm: float = None,
) -> ShearCheckResult:
    """Check shear capacity of a beam per TCVN 5574:2018 (8.1.3.2, 8.1.3.3.1, 10.3.4.3).

    Q_kN: shear at the support face. q1_kN_per_m: distributed load acting on the inclined
    section (0 = conservative). a_load_mm: distance from support to the first concentrated load.
    """
    b, h, h0 = section.b, section.h, section.h0
    Q_N = abs(Q_kN) * 1e3
    Rb, Rbt = concrete.Rb_calc, concrete.Rbt_calc

    Q_strut_N = PHI_B1 * Rb * b * h0
    qsw = stirrup_rebar.Rsw_calc * n_legs * bar_area(stirrup_diameter_mm) / s_mm
    Qu_N, Qb_N, Qsw_N, C = shear_capacity(qsw, Rbt, b, h0, q1_kN_per_m, a_load_mm)

    is_strut_safe = Q_N <= Q_strut_N
    s_max_calc = Rbt * b * h0**2 / Q_N if Q_N > 0 else float("inf")
    s_con = _constructive_spacing(h0, Q_N > 0.5 * Rbt * b * h0)
    is_spacing_ok = s_mm <= min(s_max_calc, s_con) + 1e-6
    # A shear design is not code-compliant if the transverse reinforcement
    # spacing violates either CT (98) or the detailing limit in 10.3.4.3,
    # even when Q <= Qb + Qsw and the inclined concrete strut is adequate.
    is_safe = Q_N <= Qu_N + 1e-3 and is_strut_safe and is_spacing_ok

    return ShearCheckResult(
        Q_kN=abs(Q_kN),
        b_mm=b,
        h_mm=h,
        h0_mm=h0,
        stirrup_diameter_mm=stirrup_diameter_mm,
        n_legs=n_legs,
        s_mm=s_mm,
        Q_max_strut_kN=round(Q_strut_N / 1e3, 2),
        is_strut_safe=is_strut_safe,
        qsw_N_per_mm=round(qsw, 3),
        is_qsw_min_ok=qsw >= 0.25 * Rbt * b,
        C_mm=round(C, 1),
        Qb_kN=round(Qb_N / 1e3, 2),
        Qsw_kN=round(Qsw_N / 1e3, 2),
        Qu_kN=round(Qu_N / 1e3, 2),
        utilization_ratio=round(Q_N / Qu_N, 3) if Qu_N > 0 else 999.0,
        is_safe=is_safe,
        s_max_calc_mm=round(min(s_max_calc, 1e6), 1),
        s_max_constructive_mm=round(s_con, 1),
        is_spacing_ok=is_spacing_ok,
    )


def design_beam_shear(
    Q_kN: float,
    section: RectangularBeamSection,
    concrete: Concrete,
    stirrup_rebar: Rebar,
    stirrup_diameter_mm: float = 8.0,
    n_legs: int = 2,
    q1_kN_per_m: float = 0.0,
    a_load_mm: float = None,
) -> ShearDesignResult:
    """Design stirrup spacing so that Q <= min_C(Qb + Qsw) per TCVN 5574:2018."""
    b, h, h0 = section.b, section.h, section.h0
    Q_N = abs(Q_kN) * 1e3
    Rb, Rbt = concrete.Rb_calc, concrete.Rbt_calc
    Asw_Rsw = n_legs * bar_area(stirrup_diameter_mm) * stirrup_rebar.Rsw_calc

    Q_strut_N = PHI_B1 * Rb * b * h0
    needed = Q_N > 0.5 * Rbt * b * h0
    s_code = _constructive_spacing(h0, needed)
    if Q_N > 0:
        s_code = min(s_code, Rbt * b * h0**2 / Q_N)

    if not needed:
        s_calc = float("inf")
    else:
        # Qu(qsw) is monotone increasing: bisection for the minimum qsw
        lo, hi = 0.0, 1.0
        while shear_capacity(hi, Rbt, b, h0, q1_kN_per_m, a_load_mm)[0] < Q_N and hi < 1e7:
            hi *= 2.0
        for _ in range(60):
            mid = 0.5 * (lo + hi)
            if shear_capacity(mid, Rbt, b, h0, q1_kN_per_m, a_load_mm)[0] >= Q_N:
                hi = mid
            else:
                lo = mid
        s_calc = Asw_Rsw / hi

    s_req = math.floor(min(s_calc, s_code) / 10.0) * 10.0

    return ShearDesignResult(
        Q_kN=abs(Q_kN),
        b_mm=b,
        h_mm=h,
        h0_mm=h0,
        stirrup_diameter_mm=stirrup_diameter_mm,
        n_legs=n_legs,
        s_required_mm=s_req,
        s_calc_mm=round(min(s_calc, 1e6), 1),
        s_max_code_mm=round(s_code, 1),
        is_shear_reinforcement_needed=needed,
        Q_max_strut_kN=round(Q_strut_N / 1e3, 2),
        is_section_adequate=Q_N <= Q_strut_N and s_req >= 50.0,
    )
