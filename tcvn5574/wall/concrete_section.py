"""Adapter from :mod:`tcvn5574.wall` geometry to ``concreteproperties``.

``concreteproperties`` is the preferred nonlinear section solver for walls.  It
provides meshing, arbitrary geometry, M-N interaction and biaxial capacity;
``TCVN5574`` supplies the TCVN 5574:2018 material diagrams and limit strains.
The dependency remains optional so the analytical, buckling and shear modules
can still be used without it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tcvn5574.constants import HumidityCondition
from tcvn5574.wall.section import WallSection

if TYPE_CHECKING:
    from concreteproperties.concrete_section import ConcreteSection
    from tcvn5574.nonlinear.design_code import TCVN5574


def wall_to_concrete_section(
    section: WallSection,
    concrete_grade: str,
    rebar_grade: str = "CB400-V",
    gamma_b: float = 1.0,
    gamma_s: float = 1.0,
    long_term: bool = False,
    humidity: HumidityCondition = HumidityCondition.MEDIUM,
    three_linear: bool = True,
    n_circle: int = 16,
) -> tuple["TCVN5574", "ConcreteSection"]:
    """Build the main nonlinear TCVN section engine for a wall.

    Wall coordinates are preserved: ``x`` and ``y`` are plan coordinates in
    millimetres.  Each :class:`WallSegment` is converted to a polygon and every
    :class:`WallRebar` becomes a lumped bar that displaces concrete.

    Returns the assigned ``(TCVN5574, ConcreteSection)`` pair.  Use
    ``code.ultimate_bending_capacity()``, ``code.moment_interaction_diagram()``
    or ``code.biaxial_check()`` for section resistance.
    """
    if not section.segments:
        raise ValueError("section must contain at least one concrete segment")
    if n_circle < 8:
        raise ValueError("n_circle must be at least 8")

    try:
        from concreteproperties.concrete_section import ConcreteSection
        from concreteproperties.pre import add_bar
        from sectionproperties.pre.library import rectangular_section
        from tcvn5574.nonlinear.design_code import TCVN5574
    except ImportError as exc:  # pragma: no cover - exercised without optional extra
        raise ImportError(
            "wall nonlinear analysis requires concreteproperties; install "
            "the 'nonlinear' optional dependency"
        ) from exc

    code = TCVN5574()
    concrete = code.create_concrete_material(
        concrete_grade,
        gamma_b=gamma_b,
        long_term=long_term,
        humidity=humidity,
        three_linear=three_linear,
    )
    steel = code.create_steel_material(rebar_grade, gamma_s=gamma_s)

    geometry = None
    for segment in section.segments:
        part = rectangular_section(
            d=segment.thickness,
            b=segment.length,
            material=concrete,
        ).shift_section(x_offset=segment.x0, y_offset=segment.y0)
        if segment.angle_deg:
            part = part.rotate_section(
                angle=segment.angle_deg,
                rot_point=(segment.x0, segment.y0),
            )
        geometry = part if geometry is None else geometry + part

    assert geometry is not None
    for bar in section.rebars:
        geometry = add_bar(
            geometry=geometry,
            area=bar.area or 0.0,
            material=steel,
            x=bar.x,
            y=bar.y,
            n=n_circle,
        )

    concrete_section = ConcreteSection(geometry)
    code.assign_concrete_section(concrete_section)
    return code, concrete_section
