"""TCVN 5574-2018 Structural Reinforced Concrete Calculation Library.

A backend engineering engine for reinforced concrete beams and detailing
according to Vietnam Standard TCVN 5574-2018.
"""

__version__ = "1.0.0"

from tcvn5574.batch import BeamBatchRowResult, process_beam_batch
from tcvn5574.column import (
    AxialCheckResult,
    BiaxialCheckResult,
    ColumnCheckResult,
    check_column,
    check_column_axial,
    check_column_biaxial,
    design_column_axial,
    design_column_symmetric,
)
from tcvn5574.sections.column import RectangularColumnSection
from tcvn5574.constants import (
    ConcreteGrade,
    CrackRequirement,
    HumidityCondition,
    RebarGrade,
    RebarType,
)
from tcvn5574.detailing import (
    AnchorageResult,
    LapSpliceResult,
    calculate_anchorage_length,
    calculate_lap_splice_length,
)
from tcvn5574.flexure import (
    FlexureCheckResult,
    FlexureDesignResult,
    calculate_alpha_R,
    calculate_xi_R,
    check_beam_flexure,
    design_beam_flexure,
)
from tcvn5574.materials import (
    Concrete,
    Rebar,
    bar_area,
    bar_perimeter,
    get_concrete,
    get_rebar,
    total_bar_area,
)
from tcvn5574.sections import (
    RebarGroup,
    RebarLayer,
    RectangularBeamSection,
)
from tcvn5574.shear import (
    HangingReinforcementResult,
    ShearCheckResult,
    ShearDesignResult,
    check_beam_shear,
    design_beam_shear,
    design_hanging_reinforcement,
)
from tcvn5574.sls import (
    BeamBoundaryCondition,
    CrackCheckResult,
    DeflectionCheckResult,
    check_beam_cracking,
    check_beam_deflection,
)
from tcvn5574.torsion import TorsionCheckResult, check_beam_torsion

__all__ = [
    # Materials
    "Concrete",
    "get_concrete",
    "ConcreteGrade",
    "Rebar",
    "get_rebar",
    "RebarGrade",
    "RebarType",
    "HumidityCondition",
    "CrackRequirement",
    "bar_area",
    "bar_perimeter",
    "total_bar_area",
    # Sections
    "RectangularBeamSection",
    "RebarGroup",
    "RebarLayer",
    # Flexure
    "design_beam_flexure",
    "check_beam_flexure",
    "calculate_xi_R",
    "calculate_alpha_R",
    "FlexureDesignResult",
    "FlexureCheckResult",
    # Shear & Hanging
    "check_beam_shear",
    "design_beam_shear",
    "design_hanging_reinforcement",
    "ShearCheckResult",
    "ShearDesignResult",
    "HangingReinforcementResult",
    # Torsion
    "check_beam_torsion",
    "TorsionCheckResult",
    # SLS (Crack & Deflection)
    "check_beam_cracking",
    "check_beam_deflection",
    "CrackCheckResult",
    "DeflectionCheckResult",
    "BeamBoundaryCondition",
    # Detailing (Anchorage & Lap Splice)
    "calculate_anchorage_length",
    "calculate_lap_splice_length",
    "AnchorageResult",
    "LapSpliceResult",
    # Column (eccentric compression)
    "check_column",
    "design_column_symmetric",
    "ColumnCheckResult",
    "check_column_axial",
    "design_column_axial",
    "AxialCheckResult",
    "check_column_biaxial",
    "BiaxialCheckResult",
    "RectangularColumnSection",
    # Batch
    "process_beam_batch",
    "BeamBatchRowResult",
]
