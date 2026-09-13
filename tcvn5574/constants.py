"""Constants and enumerations according to TCVN 5574-2018."""

from enum import Enum


class ConcreteGrade(str, Enum):
    B3_5 = "B3.5"
    B5 = "B5"
    B7_5 = "B7.5"
    B10 = "B10"
    B12_5 = "B12.5"
    B15 = "B15"
    B20 = "B20"
    B22_5 = "B22.5"
    B25 = "B25"
    B30 = "B30"
    B35 = "B35"
    B40 = "B40"
    B45 = "B45"
    B50 = "B50"
    B55 = "B55"
    B60 = "B60"


class RebarGrade(str, Enum):
    CB240_T = "CB240-T"
    CB300_T = "CB300-T"
    CB300_V = "CB300-V"
    CB400_V = "CB400-V"
    CB500_V = "CB500-V"
    SD390 = "SD390"
    SD490 = "SD490"
    SR235 = "SR235"
    SR295 = "SR295"
    A_I = "A-I"
    A_II = "A-II"
    A_III = "A-III"
    A_IV = "A-IV"


class HumidityCondition(str, Enum):
    """Ambient relative humidity condition W (Table 11 TCVN 5574-2018)."""
    HIGH = ">75%"
    MEDIUM = "40-75%"
    LOW = "<40%"


class RebarType(str, Enum):
    """Surface deformation type of reinforcement for anchorage."""
    PLAIN = "plain"  # Cốt thép thanh trơn (CB240-T, A-I)
    DEFORMED = "deformed"  # Cốt thép có gân cán nóng hoặc cơ nhiệt
    COLD_DRAWN_DEFORMED = "cold_drawn_deformed"  # Thép kéo (hoặc cán) nguội có gân


# Ultimate compressive concrete strain under short-term loading (Điều 6.1.4.2)
EPSILON_B2_SHORT_TERM: float = 0.0035

# Minimum longitudinal reinforcement ratio for flexural members (Điều 10.3.1.1)
MU_MIN_PERCENT: float = 0.1  # 0.1%

# Relative strain eps_b1,red of concrete under long-term loading (TCVN 5574:2018 Bảng 9)
EPS_B1_RED_LONG = {
    HumidityCondition.HIGH: 0.0024,
    HumidityCondition.MEDIUM: 0.0028,
    HumidityCondition.LOW: 0.0034,
}


class CrackRequirement(str, Enum):
    """Crack width limit basis (TCVN 5574:2018 Bảng 17), bar reinforcement CB240-T..CB600-V."""
    INTEGRITY = "integrity"  # đảm bảo an toàn cho cốt thép: 0.4 short / 0.3 long
    IMPERMEABILITY = "impermeability"  # hạn chế thấm: 0.3 short / 0.2 long


# (a_crc,ult short, a_crc,ult long) in mm
CRACK_LIMITS = {
    CrackRequirement.INTEGRITY: (0.4, 0.3),
    CrackRequirement.IMPERMEABILITY: (0.3, 0.2),
}
