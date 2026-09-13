"""Biaxial eccentric compression (TCVN 5574:2018 8.1.2.7.6): nonlinear deformation model only.

TCVN 5574:2018 gives no limit-force / approximate formula for biaxial bending (8.1.2.1.1, 8.1.2.7.6), so this
check always uses the nonlinear model. Random eccentricity and the slenderness factor are applied in each
plane: e0x, e0y (8.1.2.2.4) and eta_x, eta_y from CT (44)-(48) with I, Is about the corresponding axis.
ponytail: per-plane eta is the usual engineering practice; the code itself refers to a deformed-scheme analysis.
"""

import math
from dataclasses import dataclass
from typing import Optional

from tcvn5574.column.eccentric import random_eccentricity
from tcvn5574.materials.concrete import Concrete
from tcvn5574.materials.rebar import Rebar
from tcvn5574.sections.column import RectangularColumnSection


@dataclass
class BiaxialPlane:
    """Slenderness data of one bending plane (x: Mx in the plane of h, y: My in the plane of b)."""

    depth_mm: float
    l0_mm: float
    ea_mm: float
    e0_mm: float
    l0_i: float
    phi_L: float
    delta_e: float
    kb: float
    D_Nmm2: float
    Ncr_kN: float
    eta: float
    M_design_kNm: float  # signed N e0 eta


@dataclass
class BiaxialCheckResult:
    N_kN: float
    Mx_kNm: float
    My_kNm: float
    x: BiaxialPlane
    y: BiaxialPlane
    theta: float  # neutral-axis angle of the governing limit state (concreteproperties convention)
    Mu_kNm: float  # resultant capacity along the direction of (Mx*, My*)
    M_kNm: float  # resultant design moment
    utilization_ratio: float
    is_safe: bool
    method: str = "nonlinear section + separate-plane eta approximation"


def _plane(N, M, M_long, N_long, depth, width, a, Is, concrete, rebar, l0, l, indeterminate) -> BiaxialPlane:
    ea = random_eccentricity(l or l0, depth)
    e0 = max(abs(M) / N, ea) if indeterminate else abs(M) / N + ea
    I = width * depth**3 / 12.0
    lam = l0 / (depth / math.sqrt(12.0))
    arm = depth / 2.0 - a
    NL = N if N_long is None else N_long
    ML = abs(M) if M_long is None else abs(M_long)
    M1 = N * e0 + N * arm
    M1L = max(ML, NL * ea) + NL * arm
    phi_L = min(1.0 + M1L / M1, 2.0)
    delta_e = min(max(e0 / depth, 0.15), 1.5)
    kb = 0.15 / (phi_L * (0.3 + delta_e))
    D = kb * concrete.Eb * I + 0.7 * rebar.Es * Is
    Ncr = math.pi**2 * D / l0**2
    if lam <= 14.0:
        eta = 1.0
    elif N >= Ncr:
        eta = math.inf
    else:
        eta = 1.0 / (1.0 - N / Ncr)
    sign = 1.0 if M >= 0 else -1.0
    return BiaxialPlane(depth, l0, ea, e0, lam, phi_L, delta_e, kb, D, Ncr / 1e3, eta, sign * N * e0 * eta / 1e6)


def check_column_biaxial(
    N_kN: float,
    Mx_kNm: float,
    My_kNm: float,
    column: RectangularColumnSection,
    concrete: Concrete,
    rebar: Rebar,
    l0x_mm: float,
    l0y_mm: Optional[float] = None,
    lx_mm: Optional[float] = None,
    ly_mm: Optional[float] = None,
    N_long_kN: Optional[float] = None,
    Mx_long_kNm: Optional[float] = None,
    My_long_kNm: Optional[float] = None,
    statically_indeterminate: bool = True,
    nonlinear: bool = True,
) -> BiaxialCheckResult:
    """Check N (compression +) with Mx (plane of h) and My (plane of b) on a RectangularColumnSection.

    l0x_mm: effective length for buckling in the plane of h (Mx); l0y_mm defaults to l0x_mm.
    nonlinear must be True: TCVN 5574:2018 requires the nonlinear deformation model for biaxial bending.
    The section resistance is nonlinear, but eta_x and eta_y are evaluated
    independently.  This is an engineering approximation, not a substitute for
    a global deformed-scheme/second-order analysis of slender biaxial members.
    """
    if not nonlinear:
        raise ValueError("TCVN 5574:2018 8.1.2.1.1 / 8.1.2.7.6: biaxial eccentric compression only by the nonlinear model "
                         "(nonlinear=True); for uniaxial checks use check_column")
    if N_kN <= 0:
        raise ValueError("check_column_biaxial needs compression N > 0")
    from tcvn5574.nonlinear import column_to_concrete_section

    N = N_kN * 1e3
    NL = None if N_long_kN is None else N_long_kN * 1e3
    a_x = min(y for _, y, _ in column.bars)  # distance of the outer bar row from the face
    a_y = min(x for x, _, _ in column.bars)
    px = _plane(N, Mx_kNm * 1e6, None if Mx_long_kNm is None else Mx_long_kNm * 1e6, NL, column.h, column.b, a_x,
                column.Is("x"), concrete, rebar, l0x_mm, lx_mm, statically_indeterminate)
    py = _plane(N, My_kNm * 1e6, None if My_long_kNm is None else My_long_kNm * 1e6, NL, column.b, column.h, a_y,
                column.Is("y"), concrete, rebar, l0y_mm or l0x_mm, ly_mm, statically_indeterminate)
    common = dict(N_kN=N_kN, Mx_kNm=Mx_kNm, My_kNm=My_kNm, x=px, y=py)
    if math.isinf(px.eta) or math.isinf(py.eta):
        return BiaxialCheckResult(**common, theta=0.0, Mu_kNm=0.0, M_kNm=math.inf, utilization_ratio=999.0, is_safe=False)

    code, _ = column_to_concrete_section(column, concrete.grade.value, rebar.grade.value, gamma_b=concrete.gamma_b)
    mx, my = px.M_design_kNm * 1e6, py.M_design_kNm * 1e6
    ok, Mu, ur, theta = code.biaxial_check(N, mx, my)
    return BiaxialCheckResult(**common, theta=theta, Mu_kNm=Mu / 1e6, M_kNm=math.hypot(mx, my) / 1e6,
                              utilization_ratio=ur, is_safe=bool(ok))
