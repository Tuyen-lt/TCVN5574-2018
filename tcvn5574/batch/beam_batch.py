"""Batch processing of multiple beam design rows from tabular data or Excel."""

from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Union

from tcvn5574.flexure.beam_flexure import design_beam_flexure
from tcvn5574.materials.concrete import get_concrete
from tcvn5574.materials.rebar import get_rebar
from tcvn5574.sections.rebar_layout import RebarGroup
from tcvn5574.sections.rectangular import RectangularBeamSection
from tcvn5574.shear.beam_shear import design_beam_shear


@dataclass
class BeamBatchRowResult:
    """Design result for a single beam row in a batch."""

    story: str
    beam_id: str
    location_m: float
    load_combo: str
    b_mm: float
    h_mm: float
    concrete_grade: str
    rebar_grade: str

    # Forces
    M_kNm: float
    V_kN: float
    T_kNm: float

    # Flexural design outputs
    h0_mm: float
    alpha_m: float
    xi: float
    is_double_reinforced: bool
    As_req_cm2: float
    Asc_req_cm2: float
    mu_percent: float

    # Shear design outputs
    stirrup_diameter_mm: float
    n_stirrup_legs: int
    stirrup_spacing_mm: float
    is_shear_safe: bool


def process_beam_batch(
    rows: List[Dict[str, Any]],
    default_concrete: str = "B30",
    default_long_rebar: str = "CB400-V",
    default_stirrup_rebar: str = "CB240-T",
    default_b_mm: float = 300.0,
    default_h_mm: float = 600.0,
    cover_a_mm: float = 40.0,
    stirrup_diameter_mm: float = 8.0,
    n_stirrup_legs: int = 2,
) -> List[BeamBatchRowResult]:
    """Process a list of beam design input rows.

    Each row dict can have:
        'story': str, e.g. "LAU 1"
        'beam': str, e.g. "B1"
        'loc': float, e.g. 0.1 (m)
        'load': str, e.g. "COMB1"
        'M3' or 'M': float (kNm)
        'V2' or 'V': float (kN)
        'T': float (kNm, optional)
        'b': float (mm or cm, optional)
        'h': float (mm or cm, optional)
        'concrete': str (optional)
        'rebar': str (optional)

    Returns:
        List of BeamBatchRowResult
    """
    results: List[BeamBatchRowResult] = []

    for row in rows:
        story = str(row.get("story", row.get("Story", "Story 1")))
        beam_id = str(row.get("beam", row.get("Beam", "B1")))
        loc = float(row.get("loc", row.get("Loc", 0.0)))
        load_combo = str(row.get("load", row.get("Load", "COMB1")))

        M_val = float(row.get("M3", row.get("M", row.get("moment", 0.0))))
        V_val = float(row.get("V2", row.get("V", row.get("shear", 0.0))))
        T_val = float(row.get("T", row.get("torsion", 0.0)))

        # Section dimensions (handle mm or cm)
        b_raw = row.get("b", default_b_mm)
        h_raw = row.get("h", default_h_mm)
        b = float(b_raw) * 10.0 if float(b_raw) < 100.0 else float(b_raw)
        h = float(h_raw) * 10.0 if float(h_raw) < 100.0 else float(h_raw)

        c_grade = str(row.get("concrete", default_concrete))
        r_grade = str(row.get("rebar", default_long_rebar))
        s_grade = str(row.get("stirrup_rebar", default_stirrup_rebar))

        concrete = get_concrete(c_grade)
        rebar = get_rebar(r_grade)
        stirrup_rebar = get_rebar(s_grade)

        # Flexural design
        flex_res = design_beam_flexure(
            M_kNm=M_val,
            b_mm=b,
            h_mm=h,
            concrete=concrete,
            rebar=rebar,
            a_mm=cover_a_mm,
            a_prime_mm=cover_a_mm,
        )

        # Shear design
        # Only geometry matters for shear: a nominal bar group fixes h0 = h - cover_a
        sec_for_shear = RectangularBeamSection(b=b, h=h, tensile_rebar=RebarGroup.from_simple(2, 16.0, cover_a_mm))

        shear_res = design_beam_shear(
            Q_kN=V_val,
            section=sec_for_shear,
            concrete=concrete,
            stirrup_rebar=stirrup_rebar,
            stirrup_diameter_mm=stirrup_diameter_mm,
            n_legs=n_stirrup_legs,
        )

        results.append(
            BeamBatchRowResult(
                story=story,
                beam_id=beam_id,
                location_m=loc,
                load_combo=load_combo,
                b_mm=b,
                h_mm=h,
                concrete_grade=c_grade,
                rebar_grade=r_grade,
                M_kNm=round(M_val, 2),
                V_kN=round(V_val, 2),
                T_kNm=round(T_val, 2),
                h0_mm=flex_res.h0_mm,
                alpha_m=flex_res.alpha_m,
                xi=flex_res.xi,
                is_double_reinforced=flex_res.is_double_reinforced,
                As_req_cm2=flex_res.As_required_cm2,
                Asc_req_cm2=flex_res.Asc_required_cm2,
                mu_percent=flex_res.mu_percent,
                stirrup_diameter_mm=stirrup_diameter_mm,
                n_stirrup_legs=n_stirrup_legs,
                stirrup_spacing_mm=shear_res.s_required_mm,
                is_shear_safe=shear_res.is_section_adequate,
            )
        )

    return results
