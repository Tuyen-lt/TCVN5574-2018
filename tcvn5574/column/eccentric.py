"""Eccentric compression of rectangular columns per TCVN 5574:2018 (8.1.2.3 - 8.1.2.4).

Two methods, selected by `nonlinear`:
- False: limit-force method, N e <= Rb b x (h0 - 0.5x) + Rsc A's (h0 - a'), large / small eccentricity.
- True: nonlinear deformation model (8.1.2.7) via concreteproperties, point (N, N e0 eta) inside the M-N envelope.
Both use the same random eccentricity and slenderness factor eta = 1/(1 - N/Ncr).
"""

import math
from dataclasses import dataclass
from typing import Optional

from tcvn5574.flexure.beam_flexure import calculate_xi_R
from tcvn5574.materials.concrete import Concrete
from tcvn5574.materials.rebar import Rebar
from tcvn5574.sections.rebar_layout import RebarGroup
from tcvn5574.sections.rectangular import RectangularBeamSection


@dataclass
class ColumnCheckResult:
    N_kN: float
    M_kNm: float  # first-order moment |M|
    method: str  # "limit_force" / "nonlinear"
    l0_mm: float
    ea_mm: float  # random eccentricity
    e0_mm: float  # design eccentricity (with ea)
    l0_i: float  # slenderness l0 / i
    consider_buckling: bool  # l0/i > 14
    delta_e: float
    phi_L: float
    kb: float
    D_Nmm2: float
    Ncr_kN: float
    eta: float
    M_design_kNm: float  # N e0 eta
    e_mm: float  # e0 eta + (h0 - a')/2
    x_mm: float
    xi: float
    xi_R: float
    case: str  # "large eccentricity" / "small eccentricity" / nonlinear governing
    sigma_s: float  # stress in As (tension +) at the limit state, MPa
    capacity_kNm: float  # limit-force: Rb b x (h0 - x/2) + Rsc A's (h0 - a') [kNm, = N e allowed]; nonlinear: Mu(N)
    utilization_ratio: float
    is_safe: bool
    Mu_neg_kNm: float = 0.0  # nonlinear envelope at N
    Mu_pos_kNm: float = 0.0


def random_eccentricity(l_mm: float, h_mm: float) -> float:
    """ea = max(l/600, h/30, 10 mm)."""
    return max(l_mm / 600.0, h_mm / 30.0, 10.0)


def slenderness_eta(
    N_N: float,
    M1_Nmm: float,
    M1L_Nmm: float,
    e0: float,
    section: RectangularBeamSection,
    concrete: Concrete,
    rebar: Rebar,
    l0: float,
):
    """eta = 1/(1 - N/Ncr), Ncr = pi^2 D / l0^2, D = kb Eb I + ks Es Is.

    kb = 0.15 / (phi_L (0.3 + delta_e)), ks = 0.7, phi_L = 1 + M1L/M1 <= 2, delta_e = e0/h in [0.15, 1.5];
    I, Is about the concrete centroid. Returns (l0/i, consider, delta_e, phi_L, kb, D, Ncr, eta).
    """
    b, h = section.b, section.h
    I = b * h**3 / 12.0
    i = h / math.sqrt(12.0)
    lam = l0 / i
    yc = h / 2.0
    Is = sum(l.area * (h - l.distance_from_edge - yc) ** 2 for l in (section.tensile_rebar.layers if section.tensile_rebar else []))
    Is += sum(l.area * (l.distance_from_edge - yc) ** 2 for l in (section.comp_rebar.layers if section.comp_rebar else []))
    delta_e = min(max(e0 / h, 0.15), 1.5)
    phi_L = min(1.0 + (M1L_Nmm / M1_Nmm if M1_Nmm > 0 else 1.0), 2.0)
    kb = 0.15 / (phi_L * (0.3 + delta_e))
    D = kb * concrete.Eb * I + 0.7 * rebar.Es * Is
    Ncr = math.pi**2 * D / l0**2
    consider = lam > 14.0
    if not consider:
        eta = 1.0
    elif N_N >= Ncr:
        eta = math.inf
    else:
        eta = 1.0 / (1.0 - N_N / Ncr)
    return lam, consider, delta_e, phi_L, kb, D, Ncr, eta


def _flip(section: RectangularBeamSection) -> RectangularBeamSection:
    return RectangularBeamSection(section.b, section.h, tensile_rebar=section.comp_rebar or RebarGroup(),
                                  comp_rebar=section.tensile_rebar or RebarGroup())


def check_column(
    N_kN: float,
    M_kNm: float,
    section: RectangularBeamSection,
    concrete: Concrete,
    rebar: Rebar,
    l0_mm: float,
    l_mm: Optional[float] = None,
    N_long_kN: Optional[float] = None,
    M_long_kNm: Optional[float] = None,
    statically_indeterminate: bool = True,
    nonlinear: bool = False,
) -> ColumnCheckResult:
    """Check a rectangular column under N (compression +) and M in the plane of h.

    section: b x h with bars on the two faces perpendicular to h. M >= 0 compresses the comp_rebar face;
        a negative M flips the section (comp_rebar becomes the tension side).
    l0_mm: effective length; l_mm: member length for ea (default l0).
    N_long_kN, M_long_kNm: long-term parts for phi_L (default = total, i.e. phi_L = 2, conservative).
    statically_indeterminate: e0 = max(M/N, ea); otherwise e0 = M/N + ea.
    nonlinear: False = limit-force method; True = nonlinear deformation model (needs concreteproperties).
    """
    if N_kN <= 0:
        raise ValueError("check_column needs compression N > 0; use check_beam_flexure for N <= 0")
    sec = section if M_kNm >= 0 else _flip(section)
    N = N_kN * 1e3
    M = abs(M_kNm) * 1e6
    b, h, h0, a, ap = sec.b, sec.h, sec.h0, sec.a, sec.a_prime
    As, Asc = sec.As, sec.Asc
    Rb, Rs, Rsc = concrete.Rb_calc, rebar.Rs_calc, rebar.Rsc_calc
    xi_R = calculate_xi_R(Rs, rebar.Es)

    ea = random_eccentricity(l_mm or l0_mm, h)
    e0 = max(M / N, ea) if statically_indeterminate else M / N + ea

    # phi_L (CT 48): moments about the most tensioned (least compressed) bars, N acting at the centroid
    NL = N if N_long_kN is None else N_long_kN * 1e3
    ML = M if M_long_kNm is None else abs(M_long_kNm) * 1e6
    arm_bar = h / 2.0 - a
    M1 = N * e0 + N * arm_bar
    M1L = max(ML, NL * ea) + NL * arm_bar
    arm = (h0 - ap) / 2.0  # CT (41)
    lam, consider, delta_e, phi_L, kb, D, Ncr, eta = slenderness_eta(N, M1, M1L, e0, sec, concrete, rebar, l0_mm)
    common = dict(N_kN=N_kN, M_kNm=abs(M_kNm), l0_mm=l0_mm, ea_mm=ea, e0_mm=e0, l0_i=lam, consider_buckling=consider,
                  delta_e=delta_e, phi_L=phi_L, kb=kb, D_Nmm2=D, Ncr_kN=Ncr / 1e3, eta=eta, xi_R=xi_R)
    if math.isinf(eta):
        return ColumnCheckResult(**common, method="nonlinear" if nonlinear else "limit_force", M_design_kNm=math.inf,
                                 e_mm=math.inf, x_mm=0.0, xi=0.0, case="N >= Ncr (unstable)", sigma_s=0.0,
                                 capacity_kNm=0.0, utilization_ratio=999.0, is_safe=False)
    Md = N * e0 * eta
    e = e0 * eta + arm

    if nonlinear:
        from tcvn5574.nonlinear import to_concrete_section

        code, _ = to_concrete_section(sec, concrete.grade.value, rebar.grade.value, gamma_b=concrete.gamma_b)
        ok, mu_neg, mu_pos = code.check_point(N, Md)
        r = code.ultimate_bending_capacity(theta=0.0, n=N) if code.tensile_load < N < code.squash_load else None
        x = r.d_n if r else math.inf
        sig = float(-r.eps_s_max * rebar.Es) if r else 0.0
        sig = max(-Rsc, min(Rs, sig))
        cap = mu_pos / 1e6
        return ColumnCheckResult(**common, method="nonlinear", M_design_kNm=Md / 1e6, e_mm=e, x_mm=x,
                                 xi=x / h0 if math.isfinite(x) else math.inf, case=f"nonlinear: {r.governing if r else 'N > Nult'}",
                                 sigma_s=sig, capacity_kNm=cap, utilization_ratio=Md / mu_pos if mu_pos > 0 else 999.0,
                                 is_safe=bool(ok), Mu_neg_kNm=mu_neg / 1e6, Mu_pos_kNm=mu_pos / 1e6)

    # ---- limit-force method: Rb b x = N + sigma_s As - Rsc A's
    x = (N + Rs * As - Rsc * Asc) / (Rb * b)  # CT (42)
    if x <= xi_R * h0:
        case, sig = "large eccentricity (x <= xi_R h0)", Rs
    else:
        x = (N + Rs * As * (1.0 + xi_R) / (1.0 - xi_R) - Rsc * Asc) / (Rb * b + 2.0 * Rs * As / (h0 * (1.0 - xi_R)))  # CT (43)
        sig = (2.0 * (1.0 - x / h0) / (1.0 - xi_R) - 1.0) * Rs
        case = "small eccentricity (x > xi_R h0)"
    if Asc > 0 and x < 2.0 * ap:
        # compression bars not yielded: moments about A's, N e' <= Rs As (h0 - a'), e' = e0 eta - (h0 - a')/2
        e_p = e0 * eta - arm
        cap = Rs * As * (h0 - ap)
        ur = N * e_p / cap if cap > 0 else 999.0
        return ColumnCheckResult(**common, method="limit_force", M_design_kNm=Md / 1e6, e_mm=e, x_mm=max(x, 0.0), xi=max(x, 0.0) / h0,
                                 case="x < 2a' (moments about A's)", sigma_s=Rs, capacity_kNm=cap / 1e6,
                                 utilization_ratio=max(ur, 0.0), is_safe=ur <= 1.0 + 1e-9)
    x = max(x, 0.0)
    cap = Rb * b * x * (h0 - 0.5 * x) + Rsc * Asc * (h0 - ap)  # right side of CT (40)
    ur = N * e / cap if cap > 0 else 999.0
    return ColumnCheckResult(**common, method="limit_force", M_design_kNm=Md / 1e6, e_mm=e, x_mm=x, xi=x / h0, case=case,
                             sigma_s=sig, capacity_kNm=cap / 1e6, utilization_ratio=ur, is_safe=ur <= 1.0 + 1e-9)


def design_column_symmetric(
    N_kN: float,
    M_kNm: float,
    b_mm: float,
    h_mm: float,
    a_mm: float,
    concrete: Concrete,
    rebar: Rebar,
    l0_mm: float,
    **kwargs,
) -> tuple[float, "ColumnCheckResult"]:
    """Required As = A's (mm2 per face) by bisection on check_column (same method / options via kwargs).

    Bars are modelled as one layer (one equivalent bar) at distance a on each face. Returns (As, result).
    """

    def sec(As):
        g = lambda: RebarGroup().add_layer(1, math.sqrt(4 * As / math.pi), a_mm) if As > 0 else RebarGroup()  # noqa: E731
        return RectangularBeamSection(b_mm, h_mm, tensile_rebar=g(), comp_rebar=g())

    def ok(As):
        return check_column(N_kN, M_kNm, sec(As), concrete, rebar, l0_mm, **kwargs).is_safe

    lo, hi = 0.0, 100.0
    if ok(1e-6):
        return 0.0, check_column(N_kN, M_kNm, sec(1e-6), concrete, rebar, l0_mm, **kwargs)
    while not ok(hi):
        lo, hi = hi, hi * 2.0
        if hi > b_mm * h_mm:
            raise ValueError("section too small: As > b h")
    for _ in range(40):
        mid = 0.5 * (lo + hi)
        lo, hi = (lo, mid) if ok(mid) else (mid, hi)
    return hi, check_column(N_kN, M_kNm, sec(hi), concrete, rebar, l0_mm, **kwargs)
