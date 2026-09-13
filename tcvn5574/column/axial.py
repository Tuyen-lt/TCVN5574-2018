"""Compression with random eccentricity only (TCVN 5574:2018 8.1.2.4.3): N <= phi (Rb A + Rsc As,tot)."""

import math
from dataclasses import dataclass
from typing import Optional

from tcvn5574.materials.concrete import Concrete
from tcvn5574.materials.rebar import Rebar

# Bảng 16: phi for long-term loading at L0/h = 6, 10, 15, 20, by concrete class (upper bound of the range)
_PHI_TABLE = [(55, (0.92, 0.90, 0.83, 0.70)), (70, (0.91, 0.89, 0.80, 0.65)), (90, (0.90, 0.88, 0.79, 0.64)), (100, (0.89, 0.87, 0.78, 0.63))]
_LAMBDAS = (6.0, 10.0, 15.0, 20.0)


def phi_axial(l0_h: float, concrete_class: float, long_term: bool = True) -> float:
    """phi of 8.1.2.4.3. long_term: Bảng 16 (linear interpolation, phi(6) for L0/h < 6);
    short-term: linear with phi = 0.9 at L0/h = 10 and 0.85 at 20, i.e. 0.95 - 0.005 L0/h."""
    if l0_h > 20.0:
        raise ValueError("8.1.2.4.3 applies only for L0/h <= 20; use check_column")
    if not long_term:
        return 0.95 - 0.005 * l0_h
    row = next(v for cls, v in _PHI_TABLE if concrete_class <= cls)
    if l0_h <= _LAMBDAS[0]:
        return row[0]
    for (l1, p1), (l2, p2) in zip(zip(_LAMBDAS, row), zip(_LAMBDAS[1:], row[1:])):
        if l0_h <= l2:
            return p1 + (p2 - p1) * (l0_h - l1) / (l2 - l1)
    return row[-1]


@dataclass
class AxialCheckResult:
    N_kN: float
    l0_h: float
    phi: float
    A_mm2: float  # concrete area used
    As_tot_mm2: float
    Nu_kN: float
    utilization_ratio: float
    is_safe: bool
    method: str = "phi (8.1.2.4.3)"


def _grade_class(concrete: Concrete) -> float:
    return float(concrete.grade.value.lstrip("B"))


def check_column_axial(
    N_kN: float,
    b_mm: float,
    h_mm: float,
    As_tot_mm2: float,
    concrete: Concrete,
    rebar: Rebar,
    l0_mm: float,
    long_term: bool = True,
    net_area: Optional[bool] = None,
    h_plane_mm: Optional[float] = None,
    nonlinear: bool = False,
    section=None,
) -> AxialCheckResult:
    """Nu = phi (Rb A + Rsc As,tot) (nonlinear=False), or with nonlinear=True: the largest N for which
    (N, N ea eta) lies inside the nonlinear M-N envelope (check_column with M = 0); needs `section`
    (RectangularBeamSection with the two bar faces in the plane considered).

    h_plane_mm: section dimension in the plane considered for L0/h; default the smaller side (conservative).
    net_area: A = b h - As,tot when True, b h when False; None -> net only for mu > 3 % (Đoàn Thị Quỳnh Mai).
    """
    lam = l0_mm / (h_plane_mm or min(b_mm, h_mm))
    if nonlinear:
        return _axial_nonlinear(N_kN, section, concrete, rebar, l0_mm, As_tot_mm2, lam)
    phi = phi_axial(lam, _grade_class(concrete), long_term)
    Ab = b_mm * h_mm
    if net_area or (net_area is None and As_tot_mm2 / Ab > 0.03):
        Ab -= As_tot_mm2
    Nu = phi * (concrete.Rb_calc * Ab + rebar.Rsc_calc * As_tot_mm2)
    ur = N_kN * 1e3 / Nu
    return AxialCheckResult(N_kN, lam, phi, Ab, As_tot_mm2, Nu / 1e3, ur, ur <= 1.0 + 1e-9)


def design_column_axial(
    N_kN: float, b_mm: float, h_mm: float, concrete: Concrete, rebar: Rebar, l0_mm: float, long_term: bool = True,
    h_plane_mm: Optional[float] = None,
) -> float:
    """Required As,tot (mm2) from N = phi (Rb (A - As) + Rsc As); 0 if concrete alone suffices."""
    phi = phi_axial(l0_mm / (h_plane_mm or min(b_mm, h_mm)), _grade_class(concrete), long_term)
    A = b_mm * h_mm
    As = (N_kN * 1e3 / phi - concrete.Rb_calc * A) / (rebar.Rsc_calc - concrete.Rb_calc)
    return max(0.0, As)


def _axial_nonlinear(N_kN, section, concrete, rebar, l0_mm, As_tot_mm2, lam) -> AxialCheckResult:
    from tcvn5574.column.eccentric import check_column

    if section is None:
        raise ValueError("nonlinear=True needs section=RectangularBeamSection(...)")

    def ok(n):
        return check_column(n, 0.0, section, concrete, rebar, l0_mm, nonlinear=True).is_safe

    lo, hi = 1.0, (concrete.Rb_calc * section.b * section.h + rebar.Rsc_calc * As_tot_mm2) / 1e3
    for _ in range(14):  # bisection on N: < 0.01 % of the squash-type bound
        mid = 0.5 * (lo + hi)
        lo, hi = (mid, hi) if ok(mid) else (lo, mid)
    Nu = lo
    ur = N_kN / Nu
    return AxialCheckResult(N_kN, lam, float("nan"), section.b * section.h, As_tot_mm2, Nu, ur, ur <= 1.0 + 1e-9,
                            method="nonlinear (8.1.2.7), M = N ea eta")
