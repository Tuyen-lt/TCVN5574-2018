"""Build a concreteproperties ConcreteSection from a tcvn5574 RectangularBeamSection."""

from __future__ import annotations

from concreteproperties.concrete_section import ConcreteSection
from concreteproperties.pre import add_bar
from sectionproperties.pre.library import rectangular_section

from tcvn5574.constants import HumidityCondition
from tcvn5574.materials.rebar import bar_area
from tcvn5574.nonlinear.design_code import TCVN5574
from tcvn5574.sections.rectangular import RectangularBeamSection


def to_concrete_section(
    section: RectangularBeamSection,
    concrete_grade: str,
    rebar_grade: str,
    gamma_b: float = 1.0,
    long_term: bool = False,
    humidity: HumidityCondition = HumidityCondition.MEDIUM,
    three_linear: bool = True,
    n_circle: int = 16,
) -> tuple[TCVN5574, ConcreteSection]:
    """Return (design_code, concrete_section) with the code already assigned.

    Coordinates: web from (0, 0) to (b, h); the tensile_rebar face is at y = 0, so a positive m_x
    (theta = 0) compresses the comp_rebar face. A compression flange sits at the top, a tension flange
    at the bottom. Bars of a layer are spaced evenly between x = c and b - c, c = smallest layer
    distance of the section (corner bars at the stirrup corners).
    """
    code = TCVN5574()
    conc = code.create_concrete_material(concrete_grade, gamma_b, long_term, humidity, three_linear)
    steel = code.create_steel_material(rebar_grade)

    b, h = section.b, section.h
    geom = rectangular_section(d=h, b=b, material=conc)
    if section.has_flange:
        o = (section.bf - b) / 2.0
        y0 = 0.0 if section.flange_in_tension else h - section.hf
        for x0 in (-o, b):
            geom = geom + rectangular_section(d=section.hf, b=o, material=conc).shift_section(x_offset=x0, y_offset=y0)

    layers = [(l, False) for l in (section.tensile_rebar.layers if section.tensile_rebar else [])]
    layers += [(l, True) for l in (section.comp_rebar.layers if section.comp_rebar else [])]
    c = min((l.distance_from_edge for l, _ in layers), default=40.0)
    for layer, top in layers:
        y = h - layer.distance_from_edge if top else layer.distance_from_edge
        n = layer.n_bars
        for i in range(n):
            x = b / 2 if n == 1 else c + (b - 2 * c) * i / (n - 1)
            geom = add_bar(geometry=geom, area=bar_area(layer.diameter), material=steel, x=x, y=y, n=n_circle)

    cs = ConcreteSection(geom)
    code.assign_concrete_section(cs)
    return code, cs


def column_to_concrete_section(
    column,
    concrete_grade: str,
    rebar_grade: str,
    gamma_b: float = 1.0,
    long_term: bool = False,
    humidity: HumidityCondition = HumidityCondition.MEDIUM,
    three_linear: bool = True,
    n_circle: int = 16,
) -> tuple[TCVN5574, ConcreteSection]:
    """(design_code, concrete_section) for a RectangularColumnSection (bars at their (x, y) positions)."""
    code = TCVN5574()
    conc = code.create_concrete_material(concrete_grade, gamma_b, long_term, humidity, three_linear)
    steel = code.create_steel_material(rebar_grade)
    geom = rectangular_section(d=column.h, b=column.b, material=conc)
    for x, y, d in column.bars:
        geom = add_bar(geometry=geom, area=bar_area(d), material=steel, x=x, y=y, n=n_circle)
    cs = ConcreteSection(geom)
    code.assign_concrete_section(cs)
    return code, cs
