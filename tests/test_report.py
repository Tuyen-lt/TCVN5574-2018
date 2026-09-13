"""Smoke test: the PDF calculation sheet builds for every check, including cracked / uncracked branches."""

import pytest
from conftest import grp
from tcvn5574 import RectangularBeamSection, get_concrete, get_rebar

pytest.importorskip("fpdf")
from tcvn5574.report import beam_report  # noqa: E402


@pytest.mark.parametrize("flange_in_tension, M_short", [(False, 240), (True, 20)])
def test_beam_report_pdf(tmp_path, flange_in_tension, M_short):
    sec = RectangularBeamSection(300, 600, bf=900, hf=120, tensile_rebar=grp((4, 22, 45), (2, 20, 90)),
                                 comp_rebar=grp((2, 18, 40)), flange_in_tension=flange_in_tension)
    out = beam_report(str(tmp_path / "beam.pdf"), sec, get_concrete("B30"), get_rebar("CB400-V"),
                      stirrup_rebar=get_rebar("CB240-T"), M_kNm=320, Q_kN=210, q1_kN_per_m=25, T_kNm=12,
                      M_short_kNm=M_short, M_long_kNm=0.75 * M_short, span_mm=7200, anchorage_diameter_mm=22)
    data = open(out, "rb").read()
    assert data.startswith(b"%PDF") and len(data) > 20000


@pytest.mark.parametrize("M, N", [(320, 150), (-180, 800)])
def test_beam_report_nonlinear(tmp_path, M, N):
    pytest.importorskip("concreteproperties")
    sec = RectangularBeamSection(300, 600, bf=900, hf=120, tensile_rebar=grp((4, 22, 45), (2, 20, 90)), comp_rebar=grp((2, 18, 40)))
    out = beam_report(str(tmp_path / "nl.pdf"), sec, get_concrete("B30"), get_rebar("CB400-V"), M_kNm=M, nonlinear=True, N_kN=N, mn_points=6)
    data = open(out, "rb").read()
    assert data.startswith(b"%PDF") and len(data) > 80000  # two embedded figures


@pytest.mark.parametrize("nonlinear", [False, True])
def test_column_report(tmp_path, nonlinear):
    if nonlinear:
        pytest.importorskip("concreteproperties")
    from tcvn5574.report import column_report

    sec = RectangularBeamSection(400, 400, tensile_rebar=grp((3, 25, 37.5)), comp_rebar=grp((3, 25, 37.5)))
    out = column_report(str(tmp_path / "col.pdf"), sec, get_concrete("B25", gamma_b=0.85), get_rebar("CB400-V"), 750, 220, 3600,
                        N_long_kN=562.5, M_long_kNm=99, nonlinear=nonlinear, mn_points=6)
    data = open(out, "rb").read()
    assert data.startswith(b"%PDF") and (len(data) > 80000) == nonlinear  # figures only with nonlinear=True


def test_beam_report_toggle_switches_method(tmp_path):
    """nonlinear=False: limit-force text only (no figures); True replaces it by the nonlinear part with figures."""
    pytest.importorskip("concreteproperties")
    sec = RectangularBeamSection(300, 600, tensile_rebar=grp((4, 22, 45)), comp_rebar=grp((2, 18, 40)))
    kw = dict(M_kNm=250, mn_points=6)
    off = open(beam_report(str(tmp_path / "off.pdf"), sec, get_concrete("B30"), get_rebar("CB400-V"), **kw), "rb").read()
    on = open(beam_report(str(tmp_path / "on.pdf"), sec, get_concrete("B30"), get_rebar("CB400-V"), nonlinear=True, **kw), "rb").read()
    assert len(off) < 80000 < len(on)


def test_column_axial_report(tmp_path):
    from tcvn5574.report import column_axial_report

    sec = RectangularBeamSection(250, 300, tensile_rebar=grp((2, 20, 25)), comp_rebar=grp((2, 20, 25)))
    out = column_axial_report(str(tmp_path / "ax.pdf"), sec, get_concrete("B20", gamma_b=0.85), get_rebar("CB300-V"), 900, 3000, h_plane_mm=300)
    assert open(out, "rb").read().startswith(b"%PDF")


def test_column_biaxial_report(tmp_path):
    pytest.importorskip("concreteproperties")
    from tcvn5574.report import column_biaxial_report
    from tcvn5574.sections.column import RectangularColumnSection

    col = RectangularColumnSection.perimeter(400, 600, 45, 3, 4, 22)
    out = column_biaxial_report(str(tmp_path / "bi.pdf"), col, get_concrete("B25"), get_rebar("CB400-V"), 1200, 180, 120, 4200, n_points=8)
    data = open(out, "rb").read()
    assert data.startswith(b"%PDF") and len(data) > 60000  # includes the biaxial figure
