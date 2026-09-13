"""Anchorage and lap splice length calculations according to TCVN 5574-2018 (Điều 10.3.5)."""

import math
from dataclasses import dataclass
from typing import Union

from tcvn5574.constants import RebarType
from tcvn5574.materials.concrete import Concrete
from tcvn5574.materials.rebar import Rebar, bar_area, bar_perimeter


@dataclass
class AnchorageResult:
    """Result of rebar anchorage length calculation per TCVN 5574-2018."""

    diameter_mm: float
    rebar_grade: str
    concrete_grade: str
    is_tension: bool  # True for tension, False for compression

    # Bond characteristics
    eta1: float  # Rebar surface factor (1.5 plain, 2.5 ribbed hot-rolled)
    eta2: float  # Diameter factor (1.0 for d <= 32, 0.9 for d > 32)
    Rbond_MPa: float  # Bond strength = eta1 * eta2 * Rbt

    # Base anchorage
    l0_an_mm: float  # Basic anchorage length l0,an = (Rs * As) / (Rbond * us)
    l0_an_d: float  # In bar diameters (l0,an / ds)

    # Design anchorage
    alpha1: float  # 1.0 tension, 0.75 compression (10.3.5.5)
    ratio_As: float  # As,cal / As,ef
    lan_mm: float  # Required design anchorage length lan
    lan_d: float  # In bar diameters (lan / ds)
    lan_min_code_mm: float  # Code lower bound max(0.3*l0_an, 15*ds, 200mm)


@dataclass
class LapSpliceResult:
    """Result of non-welded lap splice length (nối chồng) per TCVN 5574-2018."""

    diameter_mm: float
    rebar_grade: str
    concrete_grade: str
    is_tension: bool
    spliced_percentage: float  # % of rebar spliced at one section (e.g. 50% or 100%)

    l0_an_mm: float  # Basic anchorage length
    alpha2: float  # Lap factor based on percentage (e.g. 1.2 for 50%, 2.0 for 100%)
    ratio_As: float  # As,cal / As,ef
    llap_mm: float  # Required lap splice length
    llap_d: float  # In bar diameters (llap / ds)
    llap_min_code_mm: float  # Code lower bound max(0.4*alpha2*l0_an, 20*ds, 250mm)


def calculate_anchorage_length(
    diameter_mm: float,
    concrete: Concrete,
    rebar: Rebar,
    is_tension: bool = True,
    ratio_As: float = 1.0,
    rebar_surface: Union[RebarType, str] = None,
) -> AnchorageResult:
    """Calculate basic and design anchorage lengths per TCVN 5574-2018 (Điều 10.3.5.1).

    Args:
        diameter_mm: Bar diameter in mm
        concrete: Concrete material
        rebar: Rebar material
        is_tension: True if bar is in tension, False if in compression
        ratio_As: Ratio of calculated to effective provided steel area (As,cal / As,ef <= 1.0)
        rebar_surface: Surface deformation type (None to infer from rebar)

    Returns:
        AnchorageResult
    """
    Rbt = concrete.Rbt_calc
    Rs = rebar.Rs_calc  # CT (255) uses Rs for both tension and compression

    # eta1: Surface factor
    if rebar_surface is None:
        surf = rebar.rebar_type
    else:
        surf = RebarType(rebar_surface)

    if surf == RebarType.PLAIN:
        eta1 = 1.5
    elif surf == RebarType.COLD_DRAWN_DEFORMED:
        eta1 = 2.0
    else:
        eta1 = 2.5

    # eta2: Diameter factor (1.0 for d <= 32, 0.9 for d > 32)
    eta2 = 1.0 if diameter_mm <= 32.0 else 0.9

    # Rbond = eta1 * eta2 * Rbt
    Rbond = eta1 * eta2 * Rbt

    # As and perimeter us
    As = bar_area(diameter_mm)
    us = bar_perimeter(diameter_mm)

    # l0_an = (Rs * As) / (Rbond * us) = (Rs * diameter) / (4 * Rbond)
    l0_an = (Rs * As) / (Rbond * us) if (Rbond * us > 0) else 0.0

    # alpha1:
    alpha1 = 1.0 if is_tension else 0.75

    ratio_As_clean = max(0.1, min(1.0, ratio_As))
    lan_calc = alpha1 * l0_an * ratio_As_clean

    # Code lower limits: max(0.3 * l0_an, 15 * diameter_mm, 200 mm)
    lan_min_code = max(0.3 * l0_an, 15.0 * diameter_mm, 200.0)
    lan = max(lan_calc, lan_min_code)

    return AnchorageResult(
        diameter_mm=diameter_mm,
        rebar_grade=rebar.grade.value,
        concrete_grade=concrete.grade.value,
        is_tension=is_tension,
        eta1=eta1,
        eta2=eta2,
        Rbond_MPa=round(Rbond, 3),
        l0_an_mm=round(l0_an, 1),
        l0_an_d=round(l0_an / diameter_mm, 1),
        alpha1=alpha1,
        ratio_As=ratio_As_clean,
        lan_mm=round(lan, 1),
        lan_d=round(lan / diameter_mm, 1),
        lan_min_code_mm=round(lan_min_code, 1),
    )


def calculate_lap_splice_length(
    diameter_mm: float,
    concrete: Concrete,
    rebar: Rebar,
    is_tension: bool = True,
    spliced_percentage: float = 100.0,
    ratio_As: float = 1.0,
    rebar_surface: Union[RebarType, str] = None,
) -> LapSpliceResult:
    """Calculate lap splice length (chiều dài nối chồng buộc) per TCVN 5574-2018 (Điều 10.3.5.2).

    Args:
        diameter_mm: Bar diameter in mm
        concrete: Concrete material
        rebar: Rebar material
        is_tension: True if tension splice, False if compression splice
        spliced_percentage: Percentage of total rebar spliced at the same section (e.g. 50 or 100)
        ratio_As: Ratio As,cal / As,ef <= 1.0
        rebar_surface: Surface deformation type

    Returns:
        LapSpliceResult
    """
    an_res = calculate_anchorage_length(
        diameter_mm=diameter_mm,
        concrete=concrete,
        rebar=rebar,
        is_tension=is_tension,
        ratio_As=1.0,
        rebar_surface=rebar_surface,
    )
    l0_an = an_res.l0_an_mm

    # alpha2 (10.3.6.2): base value up to 50% (ribbed) / 25% (plain) of bars spliced in one
    # section, 2.0 (tension) / 1.2 (compression) at 100%, linear in between.
    surf = rebar.rebar_type if rebar_surface is None else RebarType(rebar_surface)
    p0 = 25.0 if surf == RebarType.PLAIN else 50.0
    a_base, a_full = (1.2, 2.0) if is_tension else (0.9, 1.2)
    pct = max(p0, min(100.0, spliced_percentage))
    alpha2 = a_base + (pct - p0) / (100.0 - p0) * (a_full - a_base)

    ratio_As_clean = max(0.1, min(1.0, ratio_As))
    llap_calc = alpha2 * l0_an * ratio_As_clean

    # Code lower limits: max(0.4 * alpha2 * l0_an, 20 * diameter_mm, 250 mm)
    llap_min_code = max(0.4 * alpha2 * l0_an, 20.0 * diameter_mm, 250.0)
    llap = max(llap_calc, llap_min_code)

    return LapSpliceResult(
        diameter_mm=diameter_mm,
        rebar_grade=rebar.grade.value,
        concrete_grade=concrete.grade.value,
        is_tension=is_tension,
        spliced_percentage=spliced_percentage,
        l0_an_mm=round(l0_an, 1),
        alpha2=round(alpha2, 3),
        ratio_As=ratio_As_clean,
        llap_mm=round(llap, 1),
        llap_d=round(llap / diameter_mm, 1),
        llap_min_code_mm=round(llap_min_code, 1),
    )
