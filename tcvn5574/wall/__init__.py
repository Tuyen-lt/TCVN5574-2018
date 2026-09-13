"""TCVN 5574-2018 RC Shear Wall and Core Wall Engine.

Provides geometric definitions, fiber section analysis, P-M interaction curves,
demand/capacity (D/C) verification, slenderness & buckling factors, shear calculations,
and analytical solutions according to TCVN 5574:2018 and MOC Guideline (QD 862/QD-BXD).
"""

from tcvn5574.wall.analytical import (
    WallAnalyticalResult,
    check_wall_analytical_flanged,
)
from tcvn5574.wall.buckling import (
    WallBucklingResult,
    calculate_combined_wall_moments,
    calculate_wall_buckling_eta,
    random_eccentricity,
)
from tcvn5574.wall.fiber import (
    PMPoint,
    WallInteractionCurve,
    WallInteractionResult,
    check_wall_interaction_dc,
    concrete_stress_2linear,
    generate_pm_interaction_curve,
    integrate_section_fibers,
    rebar_stress_prandtl,
)
from tcvn5574.wall.section import (
    WallFiber,
    WallRebar,
    WallSection,
    WallSegment,
)
from tcvn5574.wall.shear import (
    WallShearCheckResult,
    WallShearDesignResult,
    calculate_phi_n,
    check_wall_shear,
    design_wall_shear,
)
from tcvn5574.wall.concrete_section import wall_to_concrete_section

__all__ = [
    # Geometry & Mesh
    "WallFiber",
    "WallSegment",
    "WallRebar",
    "WallSection",
    # Buckling & Slenderness
    "WallBucklingResult",
    "random_eccentricity",
    "calculate_wall_buckling_eta",
    "calculate_combined_wall_moments",
    # Shear & Transverse Reinforcement
    "WallShearCheckResult",
    "WallShearDesignResult",
    "calculate_phi_n",
    "check_wall_shear",
    "design_wall_shear",
    # Fiber & P-M Interaction
    "PMPoint",
    "WallInteractionCurve",
    "WallInteractionResult",
    "concrete_stress_2linear",
    "rebar_stress_prandtl",
    "integrate_section_fibers",
    "generate_pm_interaction_curve",
    "check_wall_interaction_dc",
    # Preferred nonlinear section engine (optional concreteproperties dependency)
    "wall_to_concrete_section",
    # Analytical
    "WallAnalyticalResult",
    "check_wall_analytical_flanged",
]
