"""Column calculation sheet (eccentric compression, TCVN 5574:2018 8.1.2.4) -> PDF.

nonlinear=False: limit-force method CT (40)-(43). nonlinear=True: nonlinear deformation model (8.1.2.7) with
limit-state figure and M-N diagram. Slenderness (eta) is shared by both.
"""

from typing import Optional

from tcvn5574.column.eccentric import check_column
from tcvn5574.materials.concrete import Concrete
from tcvn5574.materials.rebar import Rebar
from tcvn5574.report.beam_report import add_inputs, add_nonlinear, bars_text
from tcvn5574.report.pdf import CalcReport, fmt
from tcvn5574.sections.rectangular import RectangularBeamSection


def add_column(
    r: CalcReport,
    N_kN: float,
    M_kNm: float,
    sec: RectangularBeamSection,
    concrete: Concrete,
    rebar: Rebar,
    l0_mm: float,
    l_mm: Optional[float] = None,
    N_long_kN: Optional[float] = None,
    M_long_kNm: Optional[float] = None,
    statically_indeterminate: bool = True,
    nonlinear: bool = False,
    mn_points: int = 24,
):
    res = check_column(N_kN, M_kNm, sec, concrete, rebar, l0_mm, l_mm, N_long_kN, M_long_kNm, statically_indeterminate, nonlinear)
    b, h, h0, a, ap = sec.b, sec.h, sec.h0, sec.a, sec.a_prime
    if M_kNm < 0:  # check_column flips the section; report the face roles accordingly
        a, ap = ap, a
        h0 = h - a
    N, M = N_kN, abs(M_kNm)

    r.heading("Độ lệch tâm và uốn dọc", "8.1.2.2.4, 8.1.2.4.2")
    r.step("Độ lệch tâm ngẫu nhiên", f"ea = max(l/600; h/30; 10) = max({fmt((l_mm or l0_mm) / 600)}; {fmt(h / 30)}; 10) = {fmt(res.ea_mm)} mm", "8.1.2.2.4")
    e1 = M * 1e3 / N
    rule = f"e0 = max(M/N; ea) = max({fmt(e1)}; {fmt(res.ea_mm)})" if statically_indeterminate else f"e0 = M/N + ea = {fmt(e1)} + {fmt(res.ea_mm)}"
    r.step("Độ lệch tâm ban đầu", f"{rule} = {fmt(res.e0_mm)} mm  ({'siêu tĩnh' if statically_indeterminate else 'tĩnh định'})", "8.1.2.2.4")
    r.step("Độ mảnh", f"L0/i = {fmt(l0_mm)}/{fmt(h / 12 ** 0.5)} = {fmt(res.l0_i)} {'>' if res.consider_buckling else '≤'} 14"
           + ("" if res.consider_buckling else " → bỏ qua uốn dọc, η = 1"), "8.1.2.1.2")
    if res.consider_buckling:
        r.step("Hệ số dài hạn", f"φL = 1 + M1L/M1 = {res.phi_L:.3f} ≤ 2  (mô men đối với trọng tâm thép chịu kéo nhiều nhất)", "CT (48)")
        r.step("Độ lệch tâm tương đối", f"δe = e0/h = {fmt(res.e0_mm)}/{fmt(h)} → {res.delta_e:.3f} ∈ [0.15; 1.5]")
        r.step("Độ cứng", f"kb = 0.15/(φL(0.3 + δe)) = {res.kb:.4f};  ks = 0.7;  D = kb·Eb·I + ks·Es·Is = {fmt(res.D_Nmm2)} N·mm²", "CT (46), (47)")
        r.step("Lực tới hạn", f"Ncr = π²D/L0² = {fmt(res.Ncr_kN)} kN", "CT (45)")
        if res.eta == float("inf"):
            r.result(f"N = {fmt(N)} kN ≥ Ncr → cấu kiện mất ổn định", False)
            return res
        r.step("Hệ số uốn dọc", f"η = 1/(1 − N/Ncr) = 1/(1 − {fmt(N)}/{fmt(res.Ncr_kN)}) = {res.eta:.3f}", "CT (44)")
    r.step("Mô men thiết kế", f"M* = N·η·e0 = {fmt(N)}×{res.eta:.3f}×{fmt(res.e0_mm / 1e3)} = {fmt(res.M_design_kNm)} kNm")

    if nonlinear:
        sign = 1 if M_kNm >= 0 else -1
        _, ok, ur = add_nonlinear(r, sign * res.M_design_kNm, sec, concrete, rebar, N, mn_points)
        return res

    r.heading("Nén lệch tâm — nội lực giới hạn", "8.1.2.4.1")
    Rb, Rs, Rsc = concrete.Rb_calc, rebar.Rs_calc, rebar.Rsc_calc
    As, Asc = (sec.As, sec.Asc) if M_kNm >= 0 else (sec.Asc, sec.As)
    r.step("Cốt thép", f"As = {fmt(As)} mm²;  A's = {fmt(Asc)} mm²;  h0 = {fmt(h0)} mm;  ξR = {res.xi_R:.3f}", "CT (31)")
    r.step("Khoảng cách e", f"e = η·e0 + (h0 − a')/2 = {res.eta:.3f}×{fmt(res.e0_mm)} + ({fmt(h0)} − {fmt(ap)})/2 = {fmt(res.e_mm)} mm", "CT (41)")
    x_large = (N * 1e3 + Rs * As - Rsc * Asc) / (Rb * b)
    r.step("Vùng nén (giả thiết lệch tâm lớn)", f"x = (N + Rs·As − Rsc·A's)/(Rb·b) = ({fmt(N * 1e3)} + {Rs:g}×{fmt(As)} − {Rsc:g}×{fmt(Asc)})/({Rb:g}×{b:g}) = {fmt(x_large)} mm "
           f"{'≤' if x_large <= res.xi_R * h0 else '>'} ξR·h0 = {fmt(res.xi_R * h0)} mm", "CT (42)")
    if "small" in res.case:
        r.step("Lệch tâm bé", f"x = (N + Rs·As(1 + ξR)/(1 − ξR) − Rsc·A's)/(Rb·b + 2Rs·As/(h0(1 − ξR))) = {fmt(res.x_mm)} mm;  σs = {fmt(res.sigma_s)} MPa", "CT (43)")
    if "2a'" in res.case:
        r.step("x < 2a'", f"lấy mô men với A's: N·(η·e0 − (h0 − a')/2) ≤ Rs·As·(h0 − a') = {fmt(res.capacity_kNm)} kNm")
        r.result(f"UR = {res.utilization_ratio:.3f}", res.is_safe)
        return res
    r.step("Khả năng chịu lực", f"Rb·b·x(h0 − 0.5x) + Rsc·A's(h0 − a') = {Rb:g}×{b:g}×{fmt(res.x_mm)}×({fmt(h0)} − {fmt(res.x_mm / 2)}) + {Rsc:g}×{fmt(Asc)}×({fmt(h0)} − {fmt(ap)}) "
           f"= {fmt(res.capacity_kNm)} kNm", "CT (40)")
    Ne = N * res.e_mm / 1e3
    r.result(f"N·e = {fmt(N)}×{fmt(res.e_mm / 1e3)} = {fmt(Ne)} kNm {'≤' if res.is_safe else '>'} {fmt(res.capacity_kNm)} kNm   (UR = {res.utilization_ratio:.3f})", res.is_safe)
    return res


def column_report(
    path: str,
    section: RectangularBeamSection,
    concrete: Concrete,
    rebar: Rebar,
    N_kN: float,
    M_kNm: float,
    l0_mm: float,
    *,
    title: str = "Kiểm tra cột BTCT nén lệch tâm",
    subtitle: str = "",
    l_mm: Optional[float] = None,
    N_long_kN: Optional[float] = None,
    M_long_kNm: Optional[float] = None,
    statically_indeterminate: bool = True,
    nonlinear: bool = False,
    mn_points: int = 24,
) -> str:
    """PDF sheet for a rectangular column (bars on the faces perpendicular to h, M in the plane of h)."""
    r = CalcReport(title)
    method = "mô hình biến dạng phi tuyến (8.1.2.7)" if nonlinear else "phương pháp nội lực giới hạn (8.1.2.4)"
    r.doc_title(title, subtitle or f"Theo TCVN 5574:2018 — {method}")
    forces = [("Lực dọc (nén +)", "N", N_kN, "kN"), ("Mô men", "M", M_kNm, "kNm"), ("Chiều dài tính toán", "L0", l0_mm, "mm")]
    if N_long_kN is not None:
        forces.append(("Lực dọc dài hạn", "NL", N_long_kN, "kN"))
    if M_long_kNm is not None:
        forces.append(("Mô men dài hạn", "ML", M_long_kNm, "kNm"))
    add_inputs(r, section, concrete, rebar, forces=forces)
    res = add_column(r, N_kN, M_kNm, section, concrete, rebar, l0_mm, l_mm, N_long_kN, M_long_kNm,
                     statically_indeterminate, nonlinear, mn_points)
    r.heading("Tổng hợp")
    r.result(f"UR = {res.utilization_ratio:.3f}  ({'phi tuyến' if nonlinear else 'nội lực giới hạn'})", res.is_safe, "Nén lệch tâm")
    r.output(path)
    return path
