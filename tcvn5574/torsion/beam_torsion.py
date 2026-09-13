"""Torsion with bending and shear for rectangular beams per TCVN 5574:2018 (Điều 8.1.4)."""

import math
from dataclasses import dataclass

from tcvn5574.flexure.beam_flexure import check_beam_flexure
from tcvn5574.materials.concrete import Concrete
from tcvn5574.materials.rebar import Rebar, bar_area
from tcvn5574.sections.rectangular import RectangularBeamSection
from tcvn5574.shear.beam_shear import PHI_B1, shear_capacity


@dataclass
class TorsionCheckResult:
    """Result of torsion checks. All ratios must be <= 1.0."""

    T_kNm: float
    M3_kNm: float
    V2_kN: float
    M2_kNm: float
    V3_kN: float

    T_max_crushing_kNm: float  # 0.1 Rb b^2 h (CT 102)
    ratio_crushing: float  # T / (0.1 Rb b^2 h)
    ratio_strut_TQ: float  # T/T0 + Q/Q0 between spatial sections (8.1.4.4.1)

    T0_bottom_kNm: float  # spatial section, tension face = tensile_rebar face (CT 103-110)
    T0_top_kNm: float  # tension face = comp_rebar face
    T0_side_kNm: float  # tension face = side face

    ratio_T_top: float  # T / T0_top (pure torsion, 8.1.4.2.2)
    ratio_MT_major: float  # (T/T0_bottom)^2 + (M3/M0)^2 (CT 114)
    ratio_QT_major: float  # T/T0_side + V2/Q0 (CT 115)
    ratio_MT_minor: float  # (T/T0_side)^2 + (M2/M0,2)^2
    ratio_QT_minor: float  # T/T0_bottom + V3/Q0,3

    is_overall_safe: bool
    status_summary: str


def spatial_section_T0(Rs: float, As1: float, qsw1: float, Z1: float, Z2: float) -> float:
    """Limit torque of the spatial section, min over C (8.1.4.2.2, CT 103-110), N.mm.

    Tsw = 0.9 qsw1 delta C Z2 ; Ts = 0.9 Rs As1 Z1 Z2 / C ; delta = Z1 / (2 Z2 + Z1)
    C <= 2 Z2 + Z1 and C <= Z1 sqrt(2/delta). qsw1 Z1 / (Rs As1) limited to 0.5..1.5 by
    reducing whichever reinforcement is in excess.
    """
    if As1 <= 0 or qsw1 <= 0:
        return 0.0
    ratio = qsw1 * Z1 / (Rs * As1)
    if ratio > 1.5:
        qsw1 = 1.5 * Rs * As1 / Z1
    elif ratio < 0.5:
        As1 = qsw1 * Z1 / (0.5 * Rs)
    delta = Z1 / (2.0 * Z2 + Z1)
    C_opt = math.sqrt(Rs * As1 * Z1 / (qsw1 * delta))
    C = min(C_opt, 2.0 * Z2 + Z1, Z1 * math.sqrt(2.0 / delta))
    return 0.9 * qsw1 * delta * C * Z2 + 0.9 * Rs * As1 * Z1 * Z2 / C


def _corner_bar_area(group) -> float:
    """Area of one corner bar: a bar of the layer closest to the face."""
    if not group or not group.layers:
        return 0.0
    layer = min(group.layers, key=lambda l: l.distance_from_edge)
    return bar_area(layer.diameter)


def check_beam_torsion(
    T_kNm: float,
    M3_kNm: float,
    V2_kN: float,
    section: RectangularBeamSection,
    concrete: Concrete,
    longitudinal_rebar: Rebar,
    stirrup_rebar: Rebar,
    stirrup_diameter_mm: float,
    stirrup_spacing_mm: float,
    n_stirrup_legs: int = 2,
    M2_kNm: float = 0.0,
    V3_kN: float = 0.0,
    side_rebar_area_mm2: float = 0.0,
    n_stirrup_legs_horizontal: int = 2,
) -> TorsionCheckResult:
    """Check a rectangular beam under T with M3/V2 (major) and M2/V3 (minor) per 8.1.4.

    section.tensile_rebar is the face in tension under M3 (bottom), comp_rebar the opposite face.
    side_rebar_area_mm2: total side (web) bars on both faces; each side face gets half plus
    one corner bar from top and bottom groups. Asw,1 = one stirrup leg.
    """
    b, h, h0 = section.b, section.h, section.h0
    T = abs(T_kNm) * 1e6
    M3, M2 = abs(M3_kNm) * 1e6, abs(M2_kNm) * 1e6
    V2, V3 = abs(V2_kN) * 1e3, abs(V3_kN) * 1e3
    Rb, Rbt = concrete.Rb_calc, concrete.Rbt_calc
    Rs, Rsw = longitudinal_rebar.Rs_calc, stirrup_rebar.Rsw_calc
    s = stirrup_spacing_mm
    asw = bar_area(stirrup_diameter_mm)

    # 8.1.4.2.1 and 8.1.4.4.1 (b, h = short and long side)
    b_s, h_l = min(b, h), max(b, h)
    T_crush = 0.1 * Rb * b_s**2 * h_l
    ratio_strut = T / T_crush + V2 / (PHI_B1 * Rb * b * h0)

    # 8.1.4.2.2 spatial sections: Z1 = side at the tension face, Z2 = other side
    qsw1 = Rsw * asw / s
    As_side = side_rebar_area_mm2 / 2.0 + _corner_bar_area(section.tensile_rebar) + _corner_bar_area(section.comp_rebar)
    T0_bot = spatial_section_T0(Rs, section.As, qsw1, b, h)
    T0_top = spatial_section_T0(Rs, section.Asc, qsw1, b, h)
    T0_side = spatial_section_T0(Rs, As_side, qsw1, h, b)

    def ratio(x, cap):
        return x / cap if cap > 0 else (0.0 if x == 0 else 999.0)

    # 8.1.4.3.2 (CT 114): tension face of the bending moment
    M0 = check_beam_flexure(0.0, section, concrete, longitudinal_rebar).Mu_kNm * 1e6
    a_side = section.a if section.a > 0 else 40.0
    M0_2 = Rs * As_side * max(0.0, b - 2.0 * a_side)  # x <= 2a' case for symmetric side bars
    r_MT_major = ratio(T, T0_bot) ** 2 + ratio(M3, M0) ** 2
    r_MT_minor = ratio(T, T0_side) ** 2 + ratio(M2, M0_2) ** 2

    # 8.1.4.4.2 (CT 115): tension face parallel to the shear plane
    Q0 = shear_capacity(n_stirrup_legs * asw * Rsw / s, Rbt, b, h0)[0]
    Q0_3 = shear_capacity(n_stirrup_legs_horizontal * asw * Rsw / s, Rbt, h, b - a_side)[0]
    r_QT_major = ratio(T, T0_side) + ratio(V2, Q0)
    r_QT_minor = ratio(T, T0_bot) + ratio(V3, Q0_3)
    r_T_top = ratio(T, T0_top)

    checks = {
        "crushing T <= 0.1Rb b2 h": T / T_crush,
        "T/T0 + Q/Q0 between spatial sections": ratio_strut,
        "pure torsion, top face": r_T_top,
        "M3 & T (bottom face)": r_MT_major,
        "V2 & T (side face)": r_QT_major,
        "M2 & T (side face)": r_MT_minor,
        "V3 & T (bottom face)": r_QT_minor,
    }
    failed = [k for k, v in checks.items() if v > 1.001]
    summary = "OK" if not failed else "NG: " + "; ".join(failed)

    return TorsionCheckResult(
        T_kNm=abs(T_kNm),
        M3_kNm=abs(M3_kNm),
        V2_kN=abs(V2_kN),
        M2_kNm=abs(M2_kNm),
        V3_kN=abs(V3_kN),
        T_max_crushing_kNm=round(T_crush / 1e6, 2),
        ratio_crushing=round(T / T_crush, 3),
        ratio_strut_TQ=round(ratio_strut, 3),
        T0_bottom_kNm=round(T0_bot / 1e6, 2),
        T0_top_kNm=round(T0_top / 1e6, 2),
        T0_side_kNm=round(T0_side / 1e6, 2),
        ratio_T_top=round(r_T_top, 3),
        ratio_MT_major=round(r_MT_major, 3),
        ratio_QT_major=round(r_QT_major, 3),
        ratio_MT_minor=round(r_MT_minor, 3),
        ratio_QT_minor=round(r_QT_minor, 3),
        is_overall_safe=not failed,
        status_summary=summary,
    )
