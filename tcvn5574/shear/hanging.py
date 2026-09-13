"""Hanging reinforcement (cốt treo) design for secondary-to-main beam connections."""

import math
from dataclasses import dataclass
from typing import Optional

from tcvn5574.materials.rebar import Rebar, bar_area


@dataclass
class HangingReinforcementResult:
    """Result of hanging reinforcement calculation at beam intersection."""

    P_kN: float  # Concentrated reaction from secondary beam in kN
    h_main_mm: float  # Main beam depth (hdc) in mm
    b_main_mm: float  # Main beam width (bdc) in mm
    h_sec_mm: float  # Secondary beam depth (hdp) in mm
    b_sec_mm: float  # Secondary beam width (bdp) in mm
    Fs_kN: float  # Force carried by hanging steel Fs = P (kN)
    Atr_required_mm2: float  # Required hanging steel area (mm²)
    Atr_required_cm2: float  # Required hanging steel area (cm²)

    # Stirrup arrangement
    stirrup_diameter_mm: float
    n_legs: int
    n_stirrups_total: int  # Total number of additional stirrups required
    n_stirrups_each_side: int  # Number of stirrups placed on each side of the intersection
    distribution_length_mm: float  # Length on which stirrups are placed (mm)
    recommended_spacing_mm: float  # Spacing of hanging stirrups (mm)

    # Bent-up bars (cốt xiên) option if used
    bent_bar_area_mm2: float = 0.0
    bent_bar_diameter_mm: float = 0.0
    n_bent_bars: int = 0


def design_hanging_reinforcement(
    P_kN: float,
    h_main_mm: float,
    b_main_mm: float,
    h_sec_mm: float,
    b_sec_mm: float,
    stirrup_rebar: Rebar,
    stirrup_diameter_mm: float = 8.0,
    n_legs: int = 2,
    bent_bar_diameter_mm: Optional[float] = None,
    n_bent_bars: int = 0,
) -> HangingReinforcementResult:
    """Calculate hanging reinforcement at intersection where a secondary beam frames into a main beam.

    The whole reaction is hung up by closed stirrups: sum(Rsw * Asw) >= P
    (Bùi Quốc Bảo, TK kết cấu BTCT theo TCVN 5574-2018, ch.7 "Dầm trực giao"; same as the
    '02.TIES BAR' Stirrup Puncture sheet). TCVN 5574:2018 gives no reduction factor.

    Args:
        P_kN: Concentrated vertical load from secondary beam into main beam (kN)
        h_main_mm: Main beam depth (mm)
        b_main_mm: Main beam width (mm)
        h_sec_mm: Secondary beam depth (mm)
        b_sec_mm: Secondary beam width (mm)
        stirrup_rebar: Transverse steel material
        stirrup_diameter_mm: Diameter of hanging stirrups (mm)
        n_legs: Number of legs per stirrup (e.g. 2 or 4)
        bent_bar_diameter_mm: Optional diameter for bent bars (cốt xiên)
        n_bent_bars: Optional number of bent bars

    Returns:
        HangingReinforcementResult
    """
    Rsw = stirrup_rebar.Rsw_calc
    P_N = abs(P_kN) * 1e3

    Fs_N = P_N

    Fs_kN = Fs_N / 1e3
    Atr_req_mm2 = (Fs_N / Rsw) if Rsw > 0 else 0.0

    # Bent-up bar contribution if provided (angle = 45 deg, sin(45) = 0.7071)
    bent_area_mm2 = 0.0
    Fs_carried_by_bent = 0.0
    if bent_bar_diameter_mm and n_bent_bars > 0:
        bent_area_mm2 = n_bent_bars * bar_area(bent_bar_diameter_mm)
        Fs_carried_by_bent = bent_area_mm2 * Rsw * math.sin(math.radians(45))

    Fs_rem_N = max(0.0, Fs_N - Fs_carried_by_bent)
    Atr_stirrups_req = Fs_rem_N / Rsw if Rsw > 0 else 0.0

    # Stirrup calculation
    asw = bar_area(stirrup_diameter_mm)
    Asw_per_stirrup = n_legs * asw

    if Asw_per_stirrup > 0 and Atr_stirrups_req > 0:
        n_stirrups_exact = Atr_stirrups_req / Asw_per_stirrup
        n_each = math.ceil(n_stirrups_exact / 2.0)
        n_total = 2 * n_each
    else:
        n_each = 0
        n_total = 0

    # Distribution length along main beam centered at secondary beam:
    # L = b_sec + 2 * (h_main - h_sec)
    dist_len = b_sec_mm + 2.0 * max(50.0, h_main_mm - h_sec_mm)

    # Spacing on each side
    if n_each > 0:
        side_len = (h_main_mm - h_sec_mm)
        spacing = max(50.0, side_len / n_each)
        # Round to convenient spacing
        spacing_round = math.floor(spacing / 10.0) * 10.0
    else:
        spacing_round = 100.0

    return HangingReinforcementResult(
        P_kN=abs(P_kN),
        h_main_mm=h_main_mm,
        b_main_mm=b_main_mm,
        h_sec_mm=h_sec_mm,
        b_sec_mm=b_sec_mm,
        Fs_kN=round(Fs_kN, 2),
        Atr_required_mm2=round(Atr_req_mm2, 1),
        Atr_required_cm2=round(Atr_req_mm2 / 100.0, 2),
        stirrup_diameter_mm=stirrup_diameter_mm,
        n_legs=n_legs,
        n_stirrups_total=n_total,
        n_stirrups_each_side=n_each,
        distribution_length_mm=round(dist_len, 1),
        recommended_spacing_mm=max(50.0, spacing_round),
        bent_bar_area_mm2=round(bent_area_mm2, 1),
        bent_bar_diameter_mm=bent_bar_diameter_mm or 0.0,
        n_bent_bars=n_bent_bars,
    )
