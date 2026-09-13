# tcvn5574: TCVN 5574:2018 Reinforced Concrete Engine

Python library for design and verification of reinforced concrete beams, columns and walls according to **TCVN 5574:2018**.

Formulas follow the code text (clause / formula numbers noted in the source). Worked examples of
Đoàn Thị Quỳnh Mai, *Hướng dẫn tính toán cấu kiện BTCT theo TCVN 5574:2018*, are used as test benchmarks.

---

## Features

1. **Materials (`tcvn5574.materials`)**
   - Heavy concrete B3.5–B60: $R_b, R_{bt}$ (Bảng 7), $R_{b,ser}, R_{bt,ser}$ (Bảng 6), $E_b$ (Bảng 10), creep $\varphi_{b,cr}$ (Bảng 11), long-term $\varepsilon_{b1,red}$ (Bảng 9). B22.5 is interpolated (not in the 2018 tables).
   - Rebar CB240-T, CB300-T/V, CB400-V, CB500-V (Bảng 13, 14), $E_s = 2.0\cdot10^5$ MPa. SD/SR/A-* grades are legacy.

2. **Flexure (`tcvn5574.flexure`, 8.1.2)**
   - $\xi_R = 0.8/(1+\varepsilon_{s,el}/\varepsilon_{b2})$; singly / doubly reinforced design; capacity check with $x = \xi_R h_0$ when over-reinforced (8.1.2.3.5).
   - T-sections with flange in compression (CT 36–38) in both design (`bf_mm`, `hf_mm`) and check (`RectangularBeamSection(bf=, hf=)`).

3. **Shear (`tcvn5574.shear`, 8.1.3)**
   - $Q \le 0.3 R_b b h_0$ (CT 88).
   - $Q \le \min_C (Q_b + Q_{sw} + q_1 C)$; $Q_b = 1.5 R_{bt} b h_0^2/C \in [0.5; 2.5] R_{bt} b h_0$ (CT 90), CT (97) when $q_{sw} < 0.25 R_{bt} b$; $Q_{sw} = 0.75 q_{sw} C$, $C \in [h_0; 2h_0]$ (CT 91). Optional $q_1$ (distributed load on the inclined section) and `a_load_mm` (distance to the first concentrated load).
   - $s_{w,max} = R_{bt} b h_0^2/Q$ (CT 98); constructive $\le 0.5h_0, 300$ / $\le 0.75h_0, 500$ mm (10.3.4.3).
   - Hanging stirrups at secondary beam supports: $\Sigma R_{sw} A_{sw} \ge P$.

4. **Torsion (`tcvn5574.torsion`, 8.1.4)**
   - $T \le 0.1 R_b b^2 h$ (CT 102), $T/T_0 + Q/Q_0 \le 1$ between spatial sections (8.1.4.4.1).
   - Spatial sections (bottom, top, side faces): $T_0 = \min_C (0.9 q_{sw,1}\delta C Z_2 + 0.9 R_s A_{s,1} Z_1 Z_2/C)$, ratio $q_{sw,1}Z_1/(R_s A_{s,1})$ limited to 0.5–1.5 (CT 103–110).
   - $(T/T_0)^2 + (M/M_0)^2 \le 1$ (CT 114), $T/T_0 + Q/Q_0 \le 1$ (CT 115) for $M_3, V_2, M_2, V_3$.

5. **Serviceability (`tcvn5574.sls`, 8.2)**
   - $M_{crc} = R_{bt,ser} W_{pl}$, $W_{pl} = 1.3 W_{red}$ (CT 158–163).
   - $a_{crc,i} = \varphi_1\varphi_2\varphi_3\psi_s \sigma_s L_s/E_s$ with $\sigma_s = M(h_0-x)\alpha_{s1}/I_{red}$, $\varepsilon_{b1,red} = 0.0015$ (CT 166–176); $a_{crc} = a_{crc,1}+a_{crc,2}-a_{crc,3}$; default limits 0.4 / 0.3 mm (Bảng 17).
   - Curvature: uncracked $D = E_{b1} I_{red}$, $E_{b1} = 0.85E_b$ or $E_b/(1+\varphi_{b,cr})$; cracked $D = E_{b,red} I_{red}$, $\alpha_{s2} = E_{s,red}/E_{b,red}$ (CT 185–204). $f = s L^2 (1/r)$ with $(1/r) = (1/r)_1-(1/r)_2+(1/r)_3$.

6. **Detailing (`tcvn5574.detailing`, 10.3.5–10.3.6)**
   - $l_{0,an} = R_s A_s/(R_{bond} u_s)$, $R_{bond} = \eta_1\eta_2 R_{bt}$.
   - $l_{an} = \alpha_1 l_{0,an} A_{s,cal}/A_{s,ef} \ge \max(0.3 l_{0,an}, 15d_s, 200)$, $\alpha_1$ = 1.0 tension / 0.75 compression.
   - $l_{lap} = \alpha_2 l_{0,an} A_{s,cal}/A_{s,ef} \ge \max(0.4\alpha_2 l_{0,an}, 20d_s, 250)$; $\alpha_2$ = 1.2→2.0 (tension), 0.9→1.2 (compression) between 50 % (25 % plain bars) and 100 % spliced.

7. **Nonlinear deformation model (`tcvn5574.nonlinear`, 8.1.2.7)** — `TCVN5574` design code for
   [concreteproperties](https://github.com/robbievanleeuwen/concrete-properties) (installed automatically):
   - Concrete three-linear (default) / two-linear diagrams (6.1.4, CT 8-13), long-term strains from Bảng 9; steel two-linear with Rs / Rsc, $\varepsilon_{s,u} = 0.025$.
   - Failure criteria CT (70), (71): $\varepsilon_{b,max} = \varepsilon_{b2}$ or $\varepsilon_{s,max} = 0.025$ (steel-governed sections handled); one-sign strain diagrams use $\varepsilon_{b,u} = \varepsilon_{b2} - (\varepsilon_{b2} - \varepsilon_{b0})\varepsilon_1/\varepsilon_2$ (CT 86), so the M-N diagram is correct up to the squash load.
   - Ultimate bending with N, M-N interaction, biaxial bending, and everything else of concreteproperties (moment-curvature, stresses) on arbitrary sections.
   - `to_concrete_section(section, "B25", "CB400-V")` converts a `RectangularBeamSection` (incl. T flange).

8. **Columns — eccentric compression (`tcvn5574.column`, 8.1.2.4)**
   - Random eccentricity $e_a = \max(l/600, h/30, 10)$ and $e_0$ for statically indeterminate / determinate members (8.1.2.2.4).
   - Slenderness: $\eta = 1/(1 - N/N_{cr})$, $N_{cr} = \pi^2 D/L_0^2$, $D = k_b E_b I + 0.7 E_s I_s$, $k_b = 0.15/(\varphi_L(0.3+\delta_e))$ (CT 44–48), ignored for $L_0/i \le 14$.
   - Limit-force method: $N e \le R_b b x (h_0 - 0.5x) + R_{sc} A'_s (h_0 - a')$ with large (CT 42) / small (CT 43) eccentricity; $x < 2a'$ by moments about $A'_s$.
   - `design_column_symmetric(...)`: required $A_s = A'_s$.
   - `nonlinear=True`: the same $\eta$, then the point $(N, N\eta e_0)$ is checked inside the nonlinear M–N envelope.
   - Concentric compression (8.1.2.4.3, $e_0 \le h/30$, $L_0/h \le 20$): `check_column_axial` / `design_column_axial`, $N_u = \varphi(R_b A + R_{sc} A_{s,tot})$, $\varphi$ from Bảng 16 (long-term) or $0.95 - 0.005 L_0/h$ (short-term); `nonlinear=True` gives the largest N with $(N, N e_a \eta)$ inside the nonlinear envelope.
   - Biaxial eccentric compression (8.1.2.7.6): `check_column_biaxial(N, Mx, My, RectangularColumnSection.perimeter(...), ...)`. TCVN 5574:2018 allows only the nonlinear model here (no approximate formula), so `nonlinear=False` raises. $e_a$, $e_0$, $\eta$ per plane; the neutral-axis angle is solved so the capacity vector is parallel to $(M_x^*, M_y^*)$.
   - Reports: `column_report`, `column_axial_report`, `column_biaxial_report` (section with skew neutral axis + $M_x$–$M_y$ contour at N).

9. **Batch (`tcvn5574.batch`)**: envelope rows (Story, Beam, Loc, M, V) → required As and stirrup spacing.

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

Do not create a virtualenv inside OneDrive; use a Python outside it (e.g. `py -3.13`) and install the project with its development extra:

```bash
py -3.13 -m pip install -e ".[dev]"
py -3.13 -m pytest -q
```

Benchmarks:
- Đoàn Thị Quỳnh Mai: VD 2.1–2.8 (flexure, T-section), 2.9–2.12 (nonlinear model), 4.4–4.9 (columns), 3.1–3.4 (shear), 5.7–5.9 (torsion), 6.1–6.5 (crack, curvature).
- TCVN 5574:2018 tables (materials).
- `02.RC BEAM TCVN 5574-2018.xlsm` (flexure) and `05. TINH CHIEU DAI NEO THEP THEO TCVN 5574-2018.xlsx` (anchorage).

The `02.TIES BAR`, `02.TORSION BEAM` and `02.FLEXURALCRACK CONTROL` spreadsheets use TCVN 5574:2012
formulas (φb2 = 2.0, φb3, φn, φw1·φb1, old Wpl) and are **not** used as references
(except the hanging-stirrup rule $A = P/R_{sw}$).

Where the book deviates from the code text, the library follows the code:
- VD 5.9 checks $T \le T_0\sqrt{1-Q/Q_0}$; CT (115) is $T \le T_0(1-Q/Q_0)$. VD 5.9 also stops $C$ at the optimum in $[h_0; 2h_0]$; the library scans up to $3h_0$ (as VD 3.2).
- VD 6.4 uses $I_{red} = bh^3/12$ without the steel terms of CT (189).
- Chapter 4 ignores buckling for $l_0/h \le 8$ (TCVN 5574:2012); TCVN 5574:2018 8.1.2.1.2 uses $L_0/i \le 14$. The book takes $\varphi_L$ moments about $h/2$ instead of the tension bar ($h/2 - a$), ~1%. VD 4.8 uses approximate symmetric design formulas (783 mm² vs exact 719 mm²).
- At high axial force (VD 4.9, N ≈ 0.77 N_ult) the nonlinear model gives ~11% less than the limit-force small-eccentricity formula CT (43) (confirmed by independent fibre integration).

Concentric compression benchmarks: Đoàn Thị Quỳnh Mai VD 4.1 (954.05 kN), VD 4.2 (1176.5 mm²), Bùi Quốc Bảo (concrete alone), Lê Bá Huệ (short-term, net area, 1137.8 kN). No book contains a numerical biaxial example; the biaxial check is verified by an independent 2D grid integration, symmetry and the uniaxial limit.

Simplifications (conservative):
- Deflection uses the maximum-moment curvature over the whole span (VD 6.6 integrates uncracked end zones).
- Shear check compares $Q$ at the support with $\min_C$; $q_1 = 0$ by default.
- Nonlinear model: limit strain states per CT (70), (71), (86) — one-sign states use the reduced eps_b,u; checked against an independent fibre integration and the limit-force method (large eccentricity).
