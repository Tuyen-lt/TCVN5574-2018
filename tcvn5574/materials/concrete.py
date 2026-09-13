"""Concrete material properties according to TCVN 5574-2018."""

from dataclasses import dataclass
from typing import Dict, Union

from tcvn5574.constants import ConcreteGrade, HumidityCondition


@dataclass(frozen=True)
class Concrete:
    """Heavy concrete material (Bê tông nặng) per TCVN 5574-2018.

    Attributes:
        grade: Concrete grade (e.g. ConcreteGrade.B25 or 'B25')
        Rb: Design compressive strength for ULS (TTGH I), MPa
        Rbt: Design tensile strength for ULS (TTGH I), MPa
        Rb_ser: Standard compressive strength for SLS (TTGH II), MPa
        Rbt_ser: Standard tensile strength for SLS (TTGH II), MPa
        Eb: Initial static modulus of elasticity, MPa
        gamma_b: Working condition factor for concrete (default: 1.0)
    """

    grade: ConcreteGrade
    Rb: float
    Rbt: float
    Rb_ser: float
    Rbt_ser: float
    Eb: float
    gamma_b: float = 1.0

    @property
    def Rb_calc(self) -> float:
        """Effective design compressive strength: gamma_b * Rb (MPa)."""
        return self.gamma_b * self.Rb

    @property
    def Rbt_calc(self) -> float:
        """Effective design tensile strength: gamma_b * Rbt (MPa)."""
        return self.gamma_b * self.Rbt

    def get_creep_coefficient(
        self, humidity: Union[HumidityCondition, str] = HumidityCondition.MEDIUM
    ) -> float:
        """Get creep coefficient phi_b,cr per Table 11 TCVN 5574-2018."""
        h_cond = HumidityCondition(humidity)
        return _CREEP_TABLE[h_cond].get(self.grade, _CREEP_TABLE[h_cond][ConcreteGrade.B10])

    def get_reduced_modulus(
        self, humidity: Union[HumidityCondition, str] = HumidityCondition.MEDIUM
    ) -> float:
        """Effective modulus of elasticity under sustained loads: Eb1 = Eb / (1 + phi_b,cr)."""
        phi_cr = self.get_creep_coefficient(humidity)
        return self.Eb / (1.0 + phi_cr)


# TCVN 5574:2018 Bảng 7 (Rb, Rbt), Bảng 6 (Rb,ser = Rb,n; Rbt,ser = Rbt,n), Bảng 10 (Eb), MPa.
# B3.5 and Eb = 9500 MPa are tabulated for heavy concrete in TCVN 5574:2018 Table 10.
# B22.5 is not in TCVN 5574:2018 tables: linearly interpolated between B20 and B25.
_CONCRETE_PROPERTIES: Dict[ConcreteGrade, Dict[str, float]] = {
    ConcreteGrade.B3_5: {"Rb": 2.1, "Rbt": 0.26, "Rb_ser": 2.7, "Rbt_ser": 0.39, "Eb": 9500.0},
    ConcreteGrade.B5: {"Rb": 2.8, "Rbt": 0.37, "Rb_ser": 3.5, "Rbt_ser": 0.55, "Eb": 13000.0},
    ConcreteGrade.B7_5: {"Rb": 4.5, "Rbt": 0.48, "Rb_ser": 5.5, "Rbt_ser": 0.70, "Eb": 16000.0},
    ConcreteGrade.B10: {"Rb": 6.0, "Rbt": 0.56, "Rb_ser": 7.5, "Rbt_ser": 0.85, "Eb": 19000.0},
    ConcreteGrade.B12_5: {"Rb": 7.5, "Rbt": 0.66, "Rb_ser": 9.5, "Rbt_ser": 1.00, "Eb": 21500.0},
    ConcreteGrade.B15: {"Rb": 8.5, "Rbt": 0.75, "Rb_ser": 11.0, "Rbt_ser": 1.10, "Eb": 24000.0},
    ConcreteGrade.B20: {"Rb": 11.5, "Rbt": 0.90, "Rb_ser": 15.0, "Rbt_ser": 1.35, "Eb": 27500.0},
    ConcreteGrade.B22_5: {"Rb": 13.0, "Rbt": 0.975, "Rb_ser": 16.75, "Rbt_ser": 1.45, "Eb": 28750.0},
    ConcreteGrade.B25: {"Rb": 14.5, "Rbt": 1.05, "Rb_ser": 18.5, "Rbt_ser": 1.55, "Eb": 30000.0},
    ConcreteGrade.B30: {"Rb": 17.0, "Rbt": 1.15, "Rb_ser": 22.0, "Rbt_ser": 1.75, "Eb": 32500.0},
    ConcreteGrade.B35: {"Rb": 19.5, "Rbt": 1.30, "Rb_ser": 25.5, "Rbt_ser": 1.95, "Eb": 34500.0},
    ConcreteGrade.B40: {"Rb": 22.0, "Rbt": 1.40, "Rb_ser": 29.0, "Rbt_ser": 2.10, "Eb": 36000.0},
    ConcreteGrade.B45: {"Rb": 25.0, "Rbt": 1.50, "Rb_ser": 32.0, "Rbt_ser": 2.25, "Eb": 37000.0},
    ConcreteGrade.B50: {"Rb": 27.5, "Rbt": 1.60, "Rb_ser": 36.0, "Rbt_ser": 2.45, "Eb": 38000.0},
    ConcreteGrade.B55: {"Rb": 30.0, "Rbt": 1.70, "Rb_ser": 39.5, "Rbt_ser": 2.60, "Eb": 39000.0},
    ConcreteGrade.B60: {"Rb": 33.0, "Rbt": 1.80, "Rb_ser": 43.0, "Rbt_ser": 2.75, "Eb": 39500.0},
}

# Creep coefficients phi_b,cr (TCVN 5574:2018 Bảng 11, identical to SP 63.13330.2018 Table 6.12).
# Grades below B10 use B10 values (conservative); B12.5 / B22.5 interpolated.
_CREEP_TABLE: Dict[HumidityCondition, Dict[ConcreteGrade, float]] = {
    HumidityCondition.HIGH: {
        ConcreteGrade.B10: 2.8, ConcreteGrade.B12_5: 2.6, ConcreteGrade.B15: 2.4, ConcreteGrade.B20: 2.0,
        ConcreteGrade.B22_5: 1.9, ConcreteGrade.B25: 1.8, ConcreteGrade.B30: 1.6, ConcreteGrade.B35: 1.5,
        ConcreteGrade.B40: 1.4, ConcreteGrade.B45: 1.3, ConcreteGrade.B50: 1.2,
        ConcreteGrade.B55: 1.1, ConcreteGrade.B60: 1.0,
    },
    HumidityCondition.MEDIUM: {
        ConcreteGrade.B10: 3.9, ConcreteGrade.B12_5: 3.65, ConcreteGrade.B15: 3.4, ConcreteGrade.B20: 2.8,
        ConcreteGrade.B22_5: 2.65, ConcreteGrade.B25: 2.5, ConcreteGrade.B30: 2.3, ConcreteGrade.B35: 2.1,
        ConcreteGrade.B40: 1.9, ConcreteGrade.B45: 1.8, ConcreteGrade.B50: 1.6,
        ConcreteGrade.B55: 1.5, ConcreteGrade.B60: 1.4,
    },
    HumidityCondition.LOW: {
        ConcreteGrade.B10: 5.6, ConcreteGrade.B12_5: 5.2, ConcreteGrade.B15: 4.8, ConcreteGrade.B20: 4.0,
        ConcreteGrade.B22_5: 3.8, ConcreteGrade.B25: 3.6, ConcreteGrade.B30: 3.2, ConcreteGrade.B35: 3.0,
        ConcreteGrade.B40: 2.8, ConcreteGrade.B45: 2.6, ConcreteGrade.B50: 2.4,
        ConcreteGrade.B55: 2.2, ConcreteGrade.B60: 2.0,
    },
}


def get_concrete(
    grade: Union[ConcreteGrade, str],
    gamma_b: float = 1.0,
    rbt_override: float = None,
    rbt_ser_override: float = None,
) -> Concrete:
    """Factory function to get Concrete instance by grade name.

    Args:
        grade: Concrete grade, e.g. "B25" or ConcreteGrade.B25
        gamma_b: Working condition coefficient (default: 1.0)
        rbt_override: Optional custom Rbt value (MPa)
        rbt_ser_override: Optional custom Rbt,ser value (MPa)
    """
    if gamma_b <= 0.0:
        raise ValueError("gamma_b must be positive")
    if rbt_override is not None and rbt_override <= 0.0:
        raise ValueError("rbt_override must be positive")
    if rbt_ser_override is not None and rbt_ser_override <= 0.0:
        raise ValueError("rbt_ser_override must be positive")

    if isinstance(grade, str):
        grade_key = ConcreteGrade(grade.upper().strip())
    else:
        grade_key = grade

    if grade_key not in _CONCRETE_PROPERTIES:
        raise ValueError(f"Unsupported concrete grade: {grade}. Available: {[g.value for g in ConcreteGrade]}")

    props = _CONCRETE_PROPERTIES[grade_key]
    rbt = rbt_override if rbt_override is not None else props["Rbt"]
    rbt_ser = rbt_ser_override if rbt_ser_override is not None else props["Rbt_ser"]

    return Concrete(
        grade=grade_key,
        Rb=props["Rb"],
        Rbt=rbt,
        Rb_ser=props["Rb_ser"],
        Rbt_ser=rbt_ser,
        Eb=props["Eb"],
        gamma_b=gamma_b,
    )
