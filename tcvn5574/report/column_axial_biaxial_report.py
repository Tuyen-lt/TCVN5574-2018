"""Column sheets: concentric compression (8.1.2.4.3) and biaxial eccentric compression (8.1.2.7.6) -> PDF."""

from typing import Optional

from tcvn5574.materials.concrete import Concrete
from tcvn5574.materials.rebar import Rebar
from tcvn5574.report.beam_report import add_inputs
from tcvn5574.report.pdf import CalcReport, fmt
from tcvn5574.sections.rectangular import RectangularBeamSection


# ---------------------------------------------------------------- concentric compression (8.1.2.4.3)
def add_column_axial(r: CalcReport, N_kN: float, sec: RectangularBeamSection, concrete: Concrete, rebar: Rebar, l0_mm: float,
                     long_term: bool = True, h_plane_mm: Optional[float] = None, nonlinear: bool = False):
    from tcvn5574.column.axial import check_column_axial

    As_tot = sec.As + sec.Asc
    res = check_column_axial(N_kN, sec.b, sec.h, As_tot, concrete, rebar, l0_mm, long_term, h_plane_mm=h_plane_mm,
                             nonlinear=nonlinear, section=sec)
    hp = h_plane_mm or min(sec.b, sec.h)
    if nonlinear:
        r.heading("Nén với độ lệch tâm ngẫu nhiên — phi tuyến", "8.1.2.7")
        r.step("Phương pháp", f"Nu = N lớn nhất để (N; N·ea·η) nằm trong biểu đồ M–N phi tuyến;  L0/h = {fmt(l0_mm)}/{fmt(hp)} = {fmt(res.l0_h)}")
    else:
        r.heading("Nén với độ lệch tâm ngẫu nhiên (nén đúng tâm)", "8.1.2.4.3")
        r.step("Điều kiện áp dụng", f"e0 ≤ h/30;  L0/h = {fmt(l0_mm)}/{fmt(hp)} = {fmt(res.l0_h)} ≤ 20")
        r.step("Hệ số φ", (f"Bảng 16 (tải dài hạn, nội suy) → φ = {res.phi:.3f}" if long_term
                           else f"tải ngắn hạn: φ = 0.95 − 0.005·L0/h = {res.phi:.3f}"), "Bảng 16")
        r.step("Khả năng chịu lực", f"Nu = φ(Rb·A + Rsc·As,tot) = {res.phi:.3f}×({concrete.Rb_calc:g}×{fmt(res.A_mm2)} + {rebar.Rsc_calc:g}×{fmt(As_tot)}) "
               f"= {fmt(res.Nu_kN)} kN", "8.1.2.4.3")
    r.result(f"N = {fmt(N_kN)} kN {'≤' if res.is_safe else '>'} Nu = {fmt(res.Nu_kN)} kN   (UR = {res.utilization_ratio:.3f})", res.is_safe)
    return res


def column_axial_report(path: str, section: RectangularBeamSection, concrete: Concrete, rebar: Rebar, N_kN: float, l0_mm: float, *,
                        title: str = "Kiểm tra cột BTCT nén đúng tâm", long_term: bool = True, h_plane_mm: Optional[float] = None,
                        nonlinear: bool = False) -> str:
    r = CalcReport(title)
    r.doc_title(title, "Theo TCVN 5574:2018 — " + ("mô hình biến dạng phi tuyến (8.1.2.7)" if nonlinear else "8.1.2.4.3, Bảng 16"))
    add_inputs(r, section, concrete, rebar, forces=[("Lực dọc (nén +)", "N", N_kN, "kN"), ("Chiều dài tính toán", "L0", l0_mm, "mm")])
    res = add_column_axial(r, N_kN, section, concrete, rebar, l0_mm, long_term, h_plane_mm, nonlinear)
    r.heading("Tổng hợp")
    r.result(f"UR = {res.utilization_ratio:.3f}", res.is_safe, "Nén đúng tâm")
    r.output(path)
    return path


# ---------------------------------------------------------------- biaxial eccentric compression (8.1.2.7.6)
def add_column_biaxial(r: CalcReport, N_kN: float, Mx_kNm: float, My_kNm: float, column, concrete: Concrete, rebar: Rebar,
                       l0x_mm: float, l0y_mm: Optional[float] = None, N_long_kN: Optional[float] = None,
                       Mx_long_kNm: Optional[float] = None, My_long_kNm: Optional[float] = None,
                       statically_indeterminate: bool = True, n_points: int = 24):
    import math

    from tcvn5574.column.biaxial import check_column_biaxial
    from tcvn5574.nonlinear import column_to_concrete_section
    from tcvn5574.report.figures import biaxial_figure

    res = check_column_biaxial(N_kN, Mx_kNm, My_kNm, column, concrete, rebar, l0x_mm, l0y_mm, N_long_kN=N_long_kN,
                               Mx_long_kNm=Mx_long_kNm, My_long_kNm=My_long_kNm, statically_indeterminate=statically_indeterminate)
    r.heading("Độ lệch tâm và uốn dọc theo hai phương", "8.1.2.2.4, 8.1.2.4.2")
    for name, pl in (("x (Mx, cạnh h)", res.x), ("y (My, cạnh b)", res.y)):
        detail = (f";  φL = {pl.phi_L:.3f}, δe = {pl.delta_e:.3f}, kb = {pl.kb:.4f}, D = {fmt(pl.D_Nmm2)} N·mm², "
                  f"Ncr = {fmt(pl.Ncr_kN)} kN, η = {pl.eta:.3f}") if pl.l0_i > 14 else " ≤ 14 → η = 1"
        r.step(f"Phương {name}", f"ea = {fmt(pl.ea_mm)} mm;  e0 = {fmt(pl.e0_mm)} mm;  L0/i = {fmt(pl.l0_i)}{detail}", "CT (44)–(48)")
        if math.isfinite(pl.eta):
            r.step("", f"M* = N·e0·η = {fmt(N_kN)}×{fmt(pl.e0_mm / 1e3)}×{pl.eta:.3f} = {fmt(pl.M_design_kNm)} kNm")
    r.heading("Nén lệch tâm xiên — mô hình biến dạng phi tuyến", "8.1.2.7.6")
    r.step("Phương pháp", "TCVN 5574:2018 không có công thức gần đúng cho nén lệch tâm xiên (8.1.2.1.1); giải hệ (72)–(74) với bê tông "
           "3 đoạn, thép 2 đoạn, điều kiện (70), (71), (86). Góc trục trung hòa được tìm để vector [M] song song với (Mx*; My*).", "8.1.2.7.6")
    if math.isinf(res.M_kNm):
        r.result("N ≥ Ncr ở một phương → mất ổn định", False)
        return res
    r.step("Khả năng chịu lực", f"|M*| = √(Mx*² + My*²) = {fmt(res.M_kNm)} kNm;  [M] cùng phương = {fmt(res.Mu_kNm)} kNm")
    r.result(f"|M*| = {fmt(res.M_kNm)} kNm {'≤' if res.is_safe else '>'} [M] = {fmt(res.Mu_kNm)} kNm   (UR = {res.utilization_ratio:.3f})", res.is_safe)
    code, _ = column_to_concrete_section(column, concrete.grade.value, rebar.grade.value, gamma_b=concrete.gamma_b)
    r.figure(biaxial_figure(code, N_kN * 1e3, res.x.M_design_kNm * 1e6, res.y.M_design_kNm * 1e6, res.theta, n_points), 0.98,
             f"Trạng thái giới hạn và biểu đồ tương tác Mx–My tại N = {fmt(N_kN)} kN")
    return res


def column_biaxial_report(path: str, column, concrete: Concrete, rebar: Rebar, N_kN: float, Mx_kNm: float, My_kNm: float, l0x_mm: float, *,
                          l0y_mm: Optional[float] = None, title: str = "Kiểm tra cột BTCT nén lệch tâm xiên", N_long_kN: Optional[float] = None,
                          Mx_long_kNm: Optional[float] = None, My_long_kNm: Optional[float] = None,
                          statically_indeterminate: bool = True, n_points: int = 24) -> str:
    r = CalcReport(title)
    r.doc_title(title, "Theo TCVN 5574:2018 — mô hình biến dạng phi tuyến (8.1.2.7.6)")
    rows = [("Tiết diện", None, None, None), ("Cạnh theo x", "b", column.b, "mm"), ("Cạnh theo y", "h", column.h, "mm"),
            ("Số thanh", "n", f"{len(column.bars)}", ""),
            ("Tổng diện tích thép", "As", fmt(column.As_total), f"mm², μ = {column.mu_total_percent:.2f}%"),
            ("Vật liệu", None, None, None), (f"Bê tông {concrete.grade.value}", "Rb", concrete.Rb_calc, "MPa"), ("", "Eb", concrete.Eb, "MPa"),
            (f"Thép {rebar.grade.value}", "Rs = Rsc", f"{rebar.Rs_calc:g} / {rebar.Rsc_calc:g}", "MPa"), ("", "Es", rebar.Es, "MPa"),
            ("Nội lực", None, None, None), ("Lực dọc (nén +)", "N", N_kN, "kN"), ("Mô men phương x", "Mx", Mx_kNm, "kNm"),
            ("Mô men phương y", "My", My_kNm, "kNm"), ("Chiều dài tính toán", "L0x / L0y", f"{fmt(l0x_mm)} / {fmt(l0y_mm or l0x_mm)}", "mm")]
    r.heading("Số liệu đầu vào")

    def sketch(pdf, x, y, w, h):
        k = min((w - 16) / column.b, (h - 16) / column.h)
        ox, oy = x + (w - column.b * k) / 2, y + 8
        pdf.set_draw_color(31, 73, 160)
        pdf.set_line_width(0.5)
        pdf.rect(ox, oy, column.b * k, column.h * k)
        pdf.set_fill_color(192, 0, 0)
        for bx, by, d in column.bars:
            rr = max(0.6, d * k / 2)
            pdf.ellipse(ox + bx * k - rr, oy + (column.h - by) * k - rr, 2 * rr, 2 * rr, style="F")

    r.input_block(rows, sketch=sketch)
    res = add_column_biaxial(r, N_kN, Mx_kNm, My_kNm, column, concrete, rebar, l0x_mm, l0y_mm, N_long_kN, Mx_long_kNm, My_long_kNm,
                             statically_indeterminate, n_points)
    r.heading("Tổng hợp")
    r.result(f"UR = {res.utilization_ratio:.3f}", res.is_safe, "Nén lệch tâm xiên")
    r.output(path)
    return path
