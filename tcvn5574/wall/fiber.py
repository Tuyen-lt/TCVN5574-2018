"""Nonlinear fiber section analysis and P-M interaction diagrams for shear walls.

Implements Section 3, Section 4, and Section 6 of TCVN 5574:2018 guideline (Decision 862/QD-BXD).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from tcvn5574.wall.section import WallFiber, WallSection


@dataclass
class PMPoint:
    """A point on the P-M interaction diagram."""

    N_kN: float  # Axial force in kN (positive = compression)
    Mx_kNm: float  # Bending moment about X axis in kNm
    My_kNm: float = 0.0  # Bending moment about Y axis in kNm
    eps_top: float = 0.0  # Extreme compression fiber strain
    eps_bot: float = 0.0  # Extreme tension fiber strain
    x_na_mm: float = 0.0  # Neutral axis depth, mm


@dataclass
class WallInteractionCurve:
    """Complete 2D P-M interaction diagram for a shear wall."""

    points: List[PMPoint] = field(default_factory=list)
    N_max_kN: float = 0.0  # Pure axial compression capacity
    N_min_kN: float = 0.0  # Pure axial tension capacity
    M_max_pos_kNm: float = 0.0  # Maximum positive moment capacity
    M_max_neg_kNm: float = 0.0  # Maximum negative moment capacity


@dataclass
class WallInteractionResult:
    """Demand / Capacity verification result per Section 6.2."""

    N_kN: float  # Applied axial force, kN
    M_kNm: float  # Applied moment, kNm
    D_C_radial: float  # OL / OC ratio from origin (Section 6.2)
    M_capacity_kNm: float  # Moment capacity at applied axial force N
    D_C_moment: float  # |M| / M_capacity at given N
    is_safe: bool  # True if point is inside or on interaction boundary
    capacity_point_kN_kNm: Tuple[float, float]  # Intersection point C (M_C, N_C)


def concrete_stress_2linear(
    strain: float,
    Rb_MPa: float,
    eb0: float = 0.002,
    eb2: float = 0.0035,
) -> float:
    """Bilinear concrete constitutive model per Section 3.1.2.

    Parameters:
        strain: Concrete strain (positive for compression, negative for tension).
        Rb_MPa: Design compressive strength, MPa.
        eb0: Yield-like compressive strain (0.002 for short term).
        eb2: Ultimate compressive strain (0.0035 for short term).
    """
    if strain <= 0.0:
        # Tensile strength neglected in limit state analysis
        return 0.0
    elif strain <= eb0:
        return Rb_MPa * (strain / eb0)
    elif strain <= eb2:
        return Rb_MPa
    else:
        # Crushed concrete beyond ultimate strain
        return 0.0


def rebar_stress_prandtl(
    strain: float,
    Rs_MPa: float,
    Rsc_MPa: float,
    Es_MPa: float = 200_000.0,
    esu: float = 0.025,
) -> float:
    """Bilinear elastic-perfectly plastic (Prandtl) steel model per Section 3.2.2.

    Parameters:
        strain: Rebar strain (positive for compression, negative for tension).
        Rs_MPa: Design tensile yield strength, MPa.
        Rsc_MPa: Design compressive yield strength, MPa.
        Es_MPa: Modulus of elasticity, MPa (200,000 MPa).
        esu: Ultimate limit tensile strain (0.025 per code).
    """
    es0_t = Rs_MPa / Es_MPa
    es0_c = Rsc_MPa / Es_MPa

    if strain < 0.0:
        # Tension
        abs_eps = abs(strain)
        if abs_eps <= es0_t:
            return -Es_MPa * abs_eps
        elif abs_eps <= esu:
            return -Rs_MPa
        else:
            return 0.0
    elif strain > 0.0:
        # Compression
        if strain <= es0_c:
            return Es_MPa * strain
        elif strain <= esu:
            return Rsc_MPa
        else:
            return 0.0
    else:
        return 0.0


def integrate_section_fibers(
    concrete_fibers: List[WallFiber],
    rebar_fibers: List[WallFiber],
    eps_0: float,
    kappa_x: float,
    kappa_y: float,
    Rb_MPa: float,
    Rs_MPa: float,
    Rsc_MPa: float,
    Es_MPa: float = 200_000.0,
    eb0: float = 0.002,
    eb2: float = 0.0035,
    esu: float = 0.025,
) -> Tuple[float, float, float]:
    """Integrate fiber stresses across the cross-section.

    Plane strain hypothesis: eps(x, y) = eps_0 + kappa_x * y + kappa_y * x.

    Returns:
        (N_kN, Mx_kNm, My_kNm)
    """
    n_total = 0.0
    mx_total = 0.0
    my_total = 0.0

    # Concrete fibers
    for fb in concrete_fibers:
        eps = eps_0 + kappa_x * fb.y + kappa_y * fb.x
        sig_c = concrete_stress_2linear(eps, Rb_MPa, eb0=eb0, eb2=eb2)
        if sig_c > 0.0:
            force = sig_c * fb.area
            n_total += force
            mx_total += force * fb.y
            my_total += force * fb.x

    # Rebar fibers
    for fr in rebar_fibers:
        eps = eps_0 + kappa_x * fr.y + kappa_y * fr.x
        sig_s = rebar_stress_prandtl(eps, Rs_MPa, Rsc_MPa, Es_MPa=Es_MPa, esu=esu)
        # Concrete fibers represent the gross section, including the area
        # occupied by embedded bars.  Add only the steel-minus-concrete stress
        # on a bar area to avoid double-counting concrete in compression.
        sig_c_at_bar = concrete_stress_2linear(eps, Rb_MPa, eb0=eb0, eb2=eb2)
        sig_net = sig_s - sig_c_at_bar
        if sig_net != 0.0:
            force = sig_net * fr.area
            n_total += force
            mx_total += force * fr.y
            my_total += force * fr.x

    # Convert N to kN, and N*mm to kNm
    return n_total * 1e-3, mx_total * 1e-6, my_total * 1e-6


def generate_pm_interaction_curve(
    section: WallSection,
    Rb_MPa: float,
    Rs_MPa: float,
    Rsc_MPa: float,
    Es_MPa: float = 200_000.0,
    eb0: float = 0.002,
    eb2: float = 0.0035,
    esu: float = 0.025,
    n_steps: int = 40,
    max_fiber_size: float = 25.0,
    bending_axis: str = "x",  # "x" means moment Mx, bending variation along Y
) -> WallInteractionCurve:
    """Generate 2D P-M interaction diagram per Section 6.1 of the guideline.

    Parameters:
        section: WallSection instance.
        Rb_MPa: Design compressive strength of concrete.
        Rs_MPa: Design tensile strength of rebar.
        Rsc_MPa: Design compressive strength of rebar.
        Es_MPa: Elastic modulus of steel.
        eb0: Yield-like compressive strain of concrete.
        eb2: Ultimate compressive strain of concrete.
        esu: Ultimate tensile strain of steel.
        n_steps: Number of points along each branch of the envelope.
        max_fiber_size: Maximum dimension of fiber mesh, mm.
        bending_axis: Axis of bending ("x" for Mx, variation along Y).
    """
    if bending_axis.lower() not in {"x", "y"}:
        raise ValueError("bending_axis must be 'x' or 'y'")
    if n_steps < 2:
        raise ValueError("n_steps must be at least 2")
    if max_fiber_size <= 0.0:
        raise ValueError("max_fiber_size must be positive")
    if not section.segments:
        raise ValueError("section must contain at least one concrete segment")

    # Shift section to centroid so that M is relative to section center
    centered = section.shifted_to_centroid()
    c_fibers, r_fibers = centered.discretize_fibers(
        max_dx=max_fiber_size, max_dy=max_fiber_size
    )

    # Determine extents along the bending direction
    if bending_axis.lower() == "x":
        all_coords = [f.y for f in c_fibers] + [r.y for r in r_fibers]
    else:
        all_coords = [f.x for f in c_fibers] + [r.x for r in r_fibers]

    y_min = min(all_coords) if all_coords else -100.0
    y_max = max(all_coords) if all_coords else 100.0
    h_span = y_max - y_min
    if h_span <= 0.0:
        h_span = 1.0

    # Helper function to evaluate state along bending axis
    def eval_state(eps_top: float, eps_bot: float) -> PMPoint:
        kappa = (eps_top - eps_bot) / h_span
        eps_0 = eps_bot - kappa * y_min
        if bending_axis.lower() == "x":
            n, mx, my = integrate_section_fibers(
                c_fibers, r_fibers, eps_0=eps_0, kappa_x=kappa, kappa_y=0.0,
                Rb_MPa=Rb_MPa, Rs_MPa=Rs_MPa, Rsc_MPa=Rsc_MPa, Es_MPa=Es_MPa,
                eb0=eb0, eb2=eb2, esu=esu,
            )
            x_na = (-eps_bot / kappa) if abs(kappa) > 1e-15 else float("inf")
            return PMPoint(N_kN=n, Mx_kNm=mx, My_kNm=my, eps_top=eps_top, eps_bot=eps_bot, x_na_mm=x_na)
        else:
            n, mx, my = integrate_section_fibers(
                c_fibers, r_fibers, eps_0=eps_0, kappa_x=0.0, kappa_y=kappa,
                Rb_MPa=Rb_MPa, Rs_MPa=Rs_MPa, Rsc_MPa=Rsc_MPa, Es_MPa=Es_MPa,
                eb0=eb0, eb2=eb2, esu=esu,
            )
            x_na = (-eps_bot / kappa) if abs(kappa) > 1e-15 else float("inf")
            return PMPoint(N_kN=n, Mx_kNm=my, My_kNm=mx, eps_top=eps_top, eps_bot=eps_bot, x_na_mm=x_na)

    points: List[PMPoint] = []
    # 1. Pure axial compression starting point
    points.append(eval_state(eps_top=eb2, eps_bot=eb2))

    # 2. Branch 1a: Positive moment, compression zone (top = eb2, bot decreases from eb2 to -esu)
    for i in range(1, n_steps + 1):
        eps_bot = eb2 - (eb2 - (-esu)) * (i / n_steps)
        points.append(eval_state(eps_top=eb2, eps_bot=eps_bot))

    # 3. Branch 1b: Positive moment, tension zone (bot = -esu, top decreases from eb2 to -esu)
    for i in range(1, n_steps + 1):
        eps_top = eb2 - (eb2 - (-esu)) * (i / n_steps)
        points.append(eval_state(eps_top=eps_top, eps_bot=-esu))

    # 4. Branch 2a: Negative moment, tension zone (top = -esu, bot increases from -esu to eb2)
    for i in range(1, n_steps + 1):
        eps_bot = -esu + (eb2 - (-esu)) * (i / n_steps)
        points.append(eval_state(eps_top=-esu, eps_bot=eps_bot))

    # 5. Branch 2b: Negative moment, compression zone (bot = eb2, top increases from -esu to eb2)
    for i in range(1, n_steps + 1):
        eps_top = -esu + (eb2 - (-esu)) * (i / n_steps)
        points.append(eval_state(eps_top=eps_top, eps_bot=eb2))

    n_vals = [p.N_kN for p in points]
    m_vals = [p.Mx_kNm for p in points]

    return WallInteractionCurve(
        points=points,
        N_max_kN=max(n_vals),
        N_min_kN=min(n_vals),
        M_max_pos_kNm=max(m_vals),
        M_max_neg_kNm=min(m_vals),
    )


def check_wall_interaction_dc(
    N_kN: float,
    M_kNm: float,
    curve: WallInteractionCurve,
) -> WallInteractionResult:
    """Evaluate Demand / Capacity (D/C) ratio per Section 6.2 (Figure 6-4).

    Parameters:
        N_kN: Design axial force, kN (positive = compression).
        M_kNm: Design bending moment, kNm.
        curve: Computed WallInteractionCurve.
    """
    pts = curve.points
    if len(pts) < 3:
        return WallInteractionResult(
            N_kN=N_kN,
            M_kNm=M_kNm,
            D_C_radial=float("inf"),
            M_capacity_kNm=0.0,
            D_C_moment=float("inf"),
            is_safe=False,
            capacity_point_kN_kNm=(0.0, 0.0),
        )

    # 1. Moment capacity at the given axial force N_kN (horizontal slice)
    # Find segments crossing N = N_kN
    m_caps_at_N: List[float] = []
    for i in range(len(pts) - 1):
        p1 = pts[i]
        p2 = pts[i + 1]
        n1, m1 = p1.N_kN, p1.Mx_kNm
        n2, m2 = p2.N_kN, p2.Mx_kNm
        if (n1 <= N_kN <= n2) or (n2 <= N_kN <= n1):
            if abs(n2 - n1) > 1e-6:
                frac = (N_kN - n1) / (n2 - n1)
                m_interp = m1 + frac * (m2 - m1)
                m_caps_at_N.append(m_interp)

    m_cap_chosen = 0.0
    if m_caps_at_N:
        # Match the sign of applied moment M_kNm
        if M_kNm >= 0.0:
            pos_caps = [m for m in m_caps_at_N if m >= 0.0]
            m_cap_chosen = max(pos_caps) if pos_caps else max(m_caps_at_N)
        else:
            neg_caps = [m for m in m_caps_at_N if m <= 0.0]
            m_cap_chosen = min(neg_caps) if neg_caps else min(m_caps_at_N)

    d_c_moment = (
        abs(M_kNm) / abs(m_cap_chosen)
        if abs(m_cap_chosen) > 1e-6
        else (0.0 if abs(M_kNm) <= 1e-6 else float("inf"))
    )

    # 2. Radial D/C = OL / OC from origin (0, 0)
    ol = math.hypot(M_kNm, N_kN)
    if ol < 1e-9:
        return WallInteractionResult(
            N_kN=N_kN,
            M_kNm=M_kNm,
            D_C_radial=0.0,
            M_capacity_kNm=abs(m_cap_chosen),
            D_C_moment=0.0,
            is_safe=True,
            capacity_point_kN_kNm=(0.0, 0.0),
        )

    # Ray from (0, 0) in direction (M_kNm, N_kN):
    # Intersection with polygon segment (p1, p2)
    best_t: Optional[float] = None
    best_c: Tuple[float, float] = (0.0, 0.0)

    # Direction vector
    dm = M_kNm
    dn = N_kN

    for i in range(len(pts) - 1):
        m1, n1 = pts[i].Mx_kNm, pts[i].N_kN
        m2, n2 = pts[i + 1].Mx_kNm, pts[i + 1].N_kN

        # Segment vector
        sm = m2 - m1
        sn = n2 - n1

        # Ray: (t * dm, t * dn)
        # Segment: (m1 + u * sm, n1 + u * sn), u in [0, 1]
        # Cross product: dm * (n1 + u * sn) - dn * (m1 + u * sm) = 0
        denom = dm * sn - dn * sm
        if abs(denom) > 1e-9:
            u = (dn * m1 - dm * n1) / denom
            if 0.0 <= u <= 1.0:
                t = (m1 + u * sm) / dm if abs(dm) > 1e-6 else (n1 + u * sn) / dn
                if t > 0.0:
                    if best_t is None or t < best_t:
                        best_t = t
                        best_c = (m1 + u * sm, n1 + u * sn)

    if best_t is not None and best_t > 0.0:
        # Since ray is (t * dm, t * dn), OC = t * OL => OL / OC = 1 / t
        d_c_radial = 1.0 / best_t
    else:
        # Fallback to moment ratio if radial ray misses due to numerical edge
        d_c_radial = d_c_moment

    is_safe = (d_c_radial <= 1.0) and (curve.N_min_kN <= N_kN <= curve.N_max_kN)

    return WallInteractionResult(
        N_kN=N_kN,
        M_kNm=M_kNm,
        D_C_radial=d_c_radial,
        M_capacity_kNm=abs(m_cap_chosen),
        D_C_moment=d_c_moment,
        is_safe=is_safe,
        capacity_point_kN_kNm=best_c,
    )
