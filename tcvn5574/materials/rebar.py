"""Rebar material properties and bar tables according to TCVN 5574-2018."""

import math
from dataclasses import dataclass
from typing import Dict, List, Union

from tcvn5574.constants import RebarGrade, RebarType


@dataclass(frozen=True)
class Rebar:
    """Reinforcement steel material per TCVN 5574-2018.

    Attributes:
        grade: Rebar grade name (e.g. CB400-V, CB240-T, SD390)
        Rs: Design tensile strength for ULS (TTGH I), MPa
        Rsc: Design compressive strength for ULS (TTGH I), MPa
        Rsw: Design shear strength of transverse rebar/stirrups, MPa
        Es: Modulus of elasticity of steel, MPa
        rebar_type: Surface type (plain or deformed)
        gamma_s: Working condition factor for steel (default: 1.0)
    """

    grade: RebarGrade
    Rs: float
    Rsc: float
    Rsw: float
    Es: float
    rebar_type: RebarType
    gamma_s: float = 1.0
    Rs_ser: float = 0.0  # = Rs,n, serviceability strength (TCVN 5574:2018 Bảng 12)

    @property
    def Rs_calc(self) -> float:
        """Effective design tensile strength: gamma_s * Rs (MPa)."""
        return self.gamma_s * self.Rs

    @property
    def Rsc_calc(self) -> float:
        """Effective design compressive strength: gamma_s * Rsc (MPa)."""
        return self.gamma_s * self.Rsc

    @property
    def Rsw_calc(self) -> float:
        """Effective design shear strength: gamma_s * Rsw (MPa)."""
        return self.gamma_s * self.Rsw

    @property
    def epsilon_s_el(self) -> float:
        """Elastic strain limit of reinforcement: Rs / Es."""
        return self.Rs_calc / self.Es


# TCVN 5574:2018 Bảng 13 (Rs, Rsc), Bảng 14 (Rsw); Es = 2.0e5 for all TCVN 1651 bars (6.2.3.3).
# CB500-V: Rsc = 400 MPa when only short-term loads are considered (pass rsc_override=400).
# SD/SR/A-* grades are legacy (not in TCVN 5574:2018).
_REBAR_PROPERTIES: Dict[RebarGrade, Dict[str, Union[float, RebarType]]] = {
    RebarGrade.CB240_T: {
        "Rs": 210.0, "Rsc": 210.0, "Rsw": 170.0, "Es": 200000.0, "Rs_ser": 240.0, "type": RebarType.PLAIN
    },
    RebarGrade.CB300_T: {
        "Rs": 260.0, "Rsc": 260.0, "Rsw": 210.0, "Es": 200000.0, "Rs_ser": 300.0, "type": RebarType.PLAIN
    },
    RebarGrade.CB300_V: {
        "Rs": 260.0, "Rsc": 260.0, "Rsw": 210.0, "Es": 200000.0, "Rs_ser": 300.0, "type": RebarType.DEFORMED
    },
    RebarGrade.CB400_V: {
        "Rs": 350.0, "Rsc": 350.0, "Rsw": 280.0, "Es": 200000.0, "Rs_ser": 400.0, "type": RebarType.DEFORMED
    },
    RebarGrade.CB500_V: {
        "Rs": 435.0, "Rsc": 435.0, "Rsw": 300.0, "Es": 200000.0, "Rs_ser": 500.0, "type": RebarType.DEFORMED
    },
    RebarGrade.SD390: {
        "Rs": 345.0, "Rsc": 345.0, "Rsw": 280.0, "Es": 200000.0, "Rs_ser": 390.0, "type": RebarType.DEFORMED
    },
    RebarGrade.SD490: {
        "Rs": 425.0, "Rsc": 425.0, "Rsw": 300.0, "Es": 190000.0, "Rs_ser": 490.0, "type": RebarType.DEFORMED
    },
    RebarGrade.SR235: {
        "Rs": 213.6, "Rsc": 213.6, "Rsw": 170.0, "Es": 210000.0, "Rs_ser": 235.0, "type": RebarType.PLAIN
    },
    RebarGrade.SR295: {
        "Rs": 268.0, "Rsc": 268.0, "Rsw": 210.0, "Es": 210000.0, "Rs_ser": 295.0, "type": RebarType.DEFORMED
    },
    RebarGrade.A_I: {
        "Rs": 225.0, "Rsc": 225.0, "Rsw": 175.0, "Es": 210000.0, "Rs_ser": 235.0, "type": RebarType.PLAIN
    },
    RebarGrade.A_II: {
        "Rs": 280.0, "Rsc": 280.0, "Rsw": 225.0, "Es": 210000.0, "Rs_ser": 295.0, "type": RebarType.DEFORMED
    },
    RebarGrade.A_III: {
        "Rs": 365.0, "Rsc": 365.0, "Rsw": 280.0, "Es": 200000.0, "Rs_ser": 390.0, "type": RebarType.DEFORMED
    },
    RebarGrade.A_IV: {
        "Rs": 510.0, "Rsc": 450.0, "Rsw": 300.0, "Es": 190000.0, "Rs_ser": 590.0, "type": RebarType.DEFORMED
    },
}

# Alias mapping for flexible input
_REBAR_ALIASES: Dict[str, RebarGrade] = {
    "CB240": RebarGrade.CB240_T,
    "CB240T": RebarGrade.CB240_T,
    "CB300": RebarGrade.CB300_V,
    "CB300T": RebarGrade.CB300_T,
    "CB300V": RebarGrade.CB300_V,
    "CB400": RebarGrade.CB400_V,
    "CB400V": RebarGrade.CB400_V,
    "CB500": RebarGrade.CB500_V,
    "CB500V": RebarGrade.CB500_V,
    "AI": RebarGrade.A_I,
    "A1": RebarGrade.A_I,
    "A-1": RebarGrade.A_I,
    "AII": RebarGrade.A_II,
    "A2": RebarGrade.A_II,
    "A-2": RebarGrade.A_II,
    "AIII": RebarGrade.A_III,
    "A3": RebarGrade.A_III,
    "A-3": RebarGrade.A_III,
    "AIV": RebarGrade.A_IV,
    "A4": RebarGrade.A_IV,
    "A-4": RebarGrade.A_IV,
}

STANDARD_DIAMETERS: List[int] = [6, 8, 10, 12, 14, 16, 18, 20, 22, 25, 28, 30, 32, 36, 40]


def bar_area(diameter_mm: float) -> float:
    """Cross-sectional area of a single round bar in mm²: pi * d² / 4."""
    return math.pi * (diameter_mm**2) / 4.0


def total_bar_area(n_bars: int, diameter_mm: float) -> float:
    """Total area of n bars of given diameter in mm²."""
    return n_bars * bar_area(diameter_mm)


def bar_perimeter(diameter_mm: float) -> float:
    """Perimeter (chu vi) of a single round bar in mm: pi * d."""
    return math.pi * diameter_mm


def get_rebar(
    grade: Union[RebarGrade, str],
    gamma_s: float = 1.0,
    rs_override: float = None,
    rsc_override: float = None,
    rsw_override: float = None,
) -> Rebar:
    """Factory function to get Rebar instance by grade name.

    Args:
        grade: Rebar grade, e.g. "CB400-V", "CB400", "SD390", "A-III"
        gamma_s: Steel working condition factor (default: 1.0)
        rs_override: Optional custom Rs value (MPa)
        rsc_override: Optional custom Rsc value (MPa)
        rsw_override: Optional custom Rsw value (MPa)
    """
    if gamma_s <= 0.0:
        raise ValueError("gamma_s must be positive")
    for name, value in (
        ("rs_override", rs_override),
        ("rsc_override", rsc_override),
        ("rsw_override", rsw_override),
    ):
        if value is not None and value <= 0.0:
            raise ValueError(f"{name} must be positive")

    if isinstance(grade, str):
        clean_name = grade.upper().strip().replace(" ", "")
        if clean_name in _REBAR_ALIASES:
            grade_key = _REBAR_ALIASES[clean_name]
        else:
            try:
                grade_key = RebarGrade(grade.strip())
            except ValueError:
                # Try finding in enum values
                matched = [g for g in RebarGrade if g.value.upper() == clean_name]
                if matched:
                    grade_key = matched[0]
                else:
                    raise ValueError(
                        f"Unsupported rebar grade: {grade}. Available: {[g.value for g in RebarGrade]}"
                    )
    else:
        grade_key = grade

    props = _REBAR_PROPERTIES[grade_key]
    rs = rs_override if rs_override is not None else float(props["Rs"])
    rsc = rsc_override if rsc_override is not None else float(props["Rsc"])
    rsw = rsw_override if rsw_override is not None else float(props["Rsw"])

    return Rebar(
        grade=grade_key,
        Rs=rs,
        Rsc=rsc,
        Rsw=rsw,
        Es=float(props["Es"]),
        rebar_type=props["type"],
        gamma_s=gamma_s,
        Rs_ser=float(props["Rs_ser"]),
    )
