"""Beam curvature and deflection per TCVN 5574:2018 (Điều 8.2.3)."""

from dataclasses import dataclass
from enum import Enum

from tcvn5574.constants import EPS_B1_RED_LONG, HumidityCondition
from tcvn5574.materials.concrete import Concrete
from tcvn5574.materials.rebar import Rebar
from tcvn5574.sections.rectangular import RectangularBeamSection
from tcvn5574.sls.crack import EPS_B1_RED_SHORT, cracked_section, cracking_moment


class BeamBoundaryCondition(str, Enum):
    """Deflection factor s in f = s L^2 (1/r)max (8.2.3.2.4, CT 180)."""

    SIMPLY_SUPPORTED_UDL = "simply_supported_udl"  # s = 5/48
    FIXED_ENDS_UDL = "fixed_ends_udl"  # s = 1/16 (curvature at midspan)
    CANTILEVER_UDL = "cantilever_udl"  # s = 1/4


_S_FACTOR = {
    BeamBoundaryCondition.SIMPLY_SUPPORTED_UDL: 5.0 / 48.0,
    BeamBoundaryCondition.FIXED_ENDS_UDL: 1.0 / 16.0,
    BeamBoundaryCondition.CANTILEVER_UDL: 0.25,
}


@dataclass
class DeflectionCheckResult:
    """Result of beam deflection verification."""

    L_span_mm: float
    M_short_kNm: float  # all service loads
    M_long_kNm: float  # permanent + long-term variable service loads
    Mcrc_kNm: float
    is_cracked: bool

    curvature_1: float  # 1/mm, see CT (185)/(186)
    curvature_2: float
    curvature_3: float  # 0 for uncracked sections
    curvature_total: float

    f_mm: float  # total deflection s L^2 (1/r)
    f_allowable_mm: float
    is_safe: bool


def curvature_uncracked(M_Nmm, section, concrete, rebar, long_term, humidity) -> float:
    """(1/r) = M / (Eb1 Ired), Ired with alpha = Es/Eb1 (CT 188-192)."""
    Eb1 = concrete.Eb / (1.0 + concrete.get_creep_coefficient(humidity)) if long_term else 0.85 * concrete.Eb
    Ired = section.get_transformed_properties(rebar.Es / Eb1)["Ired"]
    return M_Nmm / (Eb1 * Ired)


def curvature_cracked(M_Nmm, Mcrc_Nmm, section, concrete, rebar, long_term, humidity) -> float:
    """(1/r) = M / (Eb,red Ired) with alpha_s1 = Es/Eb,red, alpha_s2 = Es,red/Eb,red (CT 193-204)."""
    eps = EPS_B1_RED_LONG[HumidityCondition(humidity)] if long_term else EPS_B1_RED_SHORT
    Eb_red = concrete.Rb_ser / eps
    psi_s = 1.0 - 0.8 * Mcrc_Nmm / M_Nmm if M_Nmm > Mcrc_Nmm else 1.0  # psi_s = 1 allowed (conservative)
    alpha_s1 = rebar.Es / Eb_red
    _, Ired = cracked_section(section, alpha_s1, alpha_s1 / psi_s)
    return M_Nmm / (Eb_red * Ired)


def check_beam_deflection(
    span_mm: float,
    M_short_kNm: float,
    M_long_kNm: float,
    section: RectangularBeamSection,
    concrete: Concrete,
    rebar: Rebar,
    boundary: BeamBoundaryCondition = BeamBoundaryCondition.SIMPLY_SUPPORTED_UDL,
    humidity: HumidityCondition = HumidityCondition.MEDIUM,
    f_allowable_ratio: float = 250.0,
) -> DeflectionCheckResult:
    """Deflection from the curvature of the critical section (8.2.3).

    Uncracked (CT 185): (1/r) = (1/r)1 [short action of short-term loads M_short - M_long]
                              + (1/r)2 [long action of M_long]
    Cracked   (CT 186): (1/r) = (1/r)1 [short, M_short] - (1/r)2 [short, M_long] + (1/r)3 [long, M_long]

    This simplified CT (180) implementation assumes a prismatic member and the
    selected built-in moment diagram without moment reversal.  It calculates
    flexural deflection only; for L/h < 10, TCVN 5574:2018 8.2.3.2.5 also
    requires shear deflection, which is not implemented here.

    f_allowable_ratio: L/[f] from the deflection limit table of the project.
    """
    if span_mm <= 0.0 or f_allowable_ratio <= 0.0:
        raise ValueError("span_mm and f_allowable_ratio must be positive")
    if M_short_kNm < 0.0 or M_long_kNm < 0.0:
        raise ValueError("service moments must be non-negative magnitudes")
    if M_long_kNm > M_short_kNm + 1e-12:
        raise ValueError(
            "M_long_kNm must be the long-term component of M_short_kNm "
            "and therefore cannot exceed it"
        )
    if span_mm / section.h < 10.0:
        raise ValueError(
            "L/h < 10 requires shear-deflection calculation per 8.2.3.2.5, "
            "which this simplified flexural-deflection function does not implement"
        )

    M_s, M_l = M_short_kNm * 1e6, M_long_kNm * 1e6
    Mcrc = cracking_moment(section, concrete, rebar)
    cracked = M_s > Mcrc
    args = (section, concrete, rebar)

    if not cracked:
        k1 = curvature_uncracked(M_s - M_l, *args, False, humidity)
        k2 = curvature_uncracked(M_l, *args, True, humidity)
        k3 = 0.0
        k = k1 + k2
    else:
        k1 = curvature_cracked(M_s, Mcrc, *args, False, humidity)
        k2 = curvature_cracked(M_l, Mcrc, *args, False, humidity) if M_l > 0 else 0.0
        k3 = curvature_cracked(M_l, Mcrc, *args, True, humidity) if M_l > 0 else 0.0
        k = k1 - k2 + k3

    f = _S_FACTOR[BeamBoundaryCondition(boundary)] * span_mm**2 * k
    f_lim = span_mm / f_allowable_ratio

    return DeflectionCheckResult(
        L_span_mm=span_mm,
        M_short_kNm=M_short_kNm,
        M_long_kNm=M_long_kNm,
        Mcrc_kNm=round(Mcrc / 1e6, 2),
        is_cracked=cracked,
        curvature_1=k1,
        curvature_2=k2,
        curvature_3=k3,
        curvature_total=k,
        f_mm=round(f, 2),
        f_allowable_mm=round(f_lim, 2),
        is_safe=f <= f_lim + 1e-6,
    )
