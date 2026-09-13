# tcvn5574: TCVN 5574:2018 Reinforced Concrete Engine

Python library for design and verification of reinforced concrete beams, columns and walls according to **TCVN 5574:2018**.

Formulas follow the code text (clause / formula numbers noted in the source). Worked examples of
Đoàn Thị Quỳnh Mai, *Hướng dẫn tính toán cấu kiện BTCT theo TCVN 5574:2018*, are used as test benchmarks.

---

## Features

- **Materials:** concrete grades B3.5–B60 and common TCVN/legacy reinforcement grades.
- **Beams:** flexural design and capacity checks for rectangular and T-sections, including singly and doubly reinforced sections.
- **Shear and torsion:** stirrup design, section checks, combined actions and hanging reinforcement at secondary-beam supports.
- **Serviceability:** crack-width, curvature and deflection checks for short- and long-term loading.
- **Detailing:** anchorage and lap-splice length calculations.
- **Columns:** axial, uniaxial eccentric and biaxial compression checks, including slenderness effects and symmetric reinforcement design.
- **Walls:** analytical and fibre-based wall-section checks, shear and buckling utilities.
- **Nonlinear analysis:** strain-compatible section analysis, moment–curvature response and interaction diagrams through `concreteproperties`.
- **Reports and batch tools:** PDF calculation sheets plus batch processing of beam force envelopes.

---

## Quick start

Requires Python 3.12 or newer. From the project directory, install once with:

```bash
python -m pip install .
```

`pip` automatically installs `concreteproperties` and `fpdf2` when they are
missing. For development and testing, use `python -m pip install -e ".[dev]"`.
Importing `tcvn5574` itself never changes the active Python environment.

```python
from tcvn5574 import *

concrete = get_concrete("B25")
rebar = get_rebar("CB400-V")
stirrup = get_rebar("CB240-T")

design = design_beam_flexure(M_kNm=150.0, b_mm=250.0, h_mm=500.0, concrete=concrete, rebar=rebar, a_mm=40.0)
print(f"As = {design.As_required_cm2:.2f} cm2")

section = RectangularBeamSection(b=250.0, h=500.0, tensile_rebar=RebarGroup.from_simple(3, 22.0, 45.0))
print(check_beam_flexure(150.0, section, concrete, rebar).Mu_kNm)

# shear at support, with q1 = 30 kN/m acting on the inclined section
sh = check_beam_shear(180.0, section, concrete, stirrup, stirrup_diameter_mm=8, n_legs=2, s_mm=100, q1_kN_per_m=30)
print(sh.Qu_kN, sh.is_safe)

crack = check_beam_cracking(M_short_kNm=120.0, M_long_kNm=90.0, section=section, concrete=concrete, rebar=rebar)
defl = check_beam_deflection(6000, 120.0, 90.0, section, concrete, rebar)
print(crack.acrc_short_mm, crack.acrc_long_mm, defl.f_mm)

anc = calculate_anchorage_length(25.0, get_concrete("B30"), rebar)
lap = calculate_lap_splice_length(25.0, get_concrete("B30"), rebar, spliced_percentage=100.0)
print(anc.lan_mm, lap.llap_mm)
```

See `example_beam_demo.py` for a full run.

### Limit-force vs nonlinear: one switch

Every bending / eccentric-compression entry point takes `nonlinear: bool = False`:

```python
check_beam_flexure(M_kNm, section, concrete, rebar)                          # 8.1.2.3 limit force
check_beam_flexure(M_kNm, section, concrete, rebar, nonlinear=True, N_kN=0)  # 8.1.2.7 nonlinear model

col = check_column(750, 220, section, concrete, rebar, l0_mm=3600, N_long_kN=562.5, M_long_kNm=99)
col_nl = check_column(750, 220, section, concrete, rebar, l0_mm=3600, N_long_kN=562.5, M_long_kNm=99, nonlinear=True)

beam_report("B1.pdf", section, concrete, rebar, M_kNm=320, nonlinear=False)   # formulas CT (34)-(38)
column_report("C1.pdf", section, concrete, rebar, 750, 220, 3600, nonlinear=True)  # figure + M-N diagram
```

### Nonlinear model / arbitrary sections

```python
from tcvn5574.nonlinear import TCVN5574, to_concrete_section

code, cs = to_concrete_section(section, "B25", "CB400-V")
r = code.ultimate_bending_capacity(n=0)            # r.m_x (N.mm), r.d_n, r.governing, r.eps_s_max
mi = code.moment_interaction_diagram(n_points=24)  # M-N diagram, CT (86) for one-sign strain states
cs.plot_section()

# any shape: build the geometry with sectionproperties / concreteproperties.pre using
# code.create_concrete_material("B30") and code.create_steel_material("CB400-V"), then
# code.assign_concrete_section(ConcreteSection(geom))
```

### PDF calculation sheet

```python
from tcvn5574.report import beam_report

beam_report("B1.pdf", section, concrete, rebar, stirrup_rebar=stirrup, stirrup_diameter_mm=8, n_legs=2, s_mm=150,
            M_kNm=150, Q_kN=180, q1_kN_per_m=30, M_short_kNm=120, M_long_kNm=90, span_mm=6000,
            anchorage_diameter_mm=22,
            nonlinear=True, N_kN=150)   # 8.1.2.7: limit strain/stress figure + M-N diagram (needs concreteproperties)
```

With `nonlinear=True` the sheet adds the nonlinear deformation model: material diagrams, limit strain state
(x, εb,max, εs,max, governing criterion), a figure of section / strain / stress at the limit state, and the
closed M–N envelope (θ = 0 and θ = π branches, moments about the section centroid) with the design point.
`TCVN5574.check_point(N, M)` returns `(ok, Mu_neg(N), Mu_pos(N))`.

Every check whose forces are given is written as a list of substituted formulas with clause numbers, the
section sketch beside the input block (The Concrete Centre style). For custom sheets use `CalcReport` with
`add_inputs`, `add_flexure`, `add_shear`, `add_torsion`, `add_cracking`, `add_deflection`, `add_anchorage`.
Fonts: DejaVu Sans (found in Windows Fonts; otherwise copy the TTFs into `tcvn5574/report/fonts/`).

---

## Testing

The library currently includes **112 automated tests** covering materials, beams, columns, walls, flexure, shear, torsion, serviceability, detailing, nonlinear analysis, batch processing and PDF reports. Results are cross-checked against TCVN 5574:2018 tables, published worked examples and independent numerical calculations.

Run the test suite with:

```bash
py -3.13 -m pip install -e ".[dev]"
py -3.13 -m pytest -q
```

> **Engineering disclaimer:** This library is provided for reference and calculation assistance only. A qualified structural engineer must independently review the inputs, assumptions and results and remains responsible for all final engineering decisions.
