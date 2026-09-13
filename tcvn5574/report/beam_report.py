"""Beam calculation sheet per TCVN 5574:2018 -> PDF (The Concrete Centre style).

Each add_* function runs the library check and writes its steps with substituted values.
beam_report() assembles the checks for which forces are given.
"""

import math
from typing import Optional

from tcvn5574.constants import CrackRequirement, HumidityCondition
from tcvn5574.detailing.anchorage import calculate_anchorage_length, calculate_lap_splice_length
from tcvn5574.flexure.beam_flexure import check_beam_flexure
from tcvn5574.materials.concrete import Concrete
from tcvn5574.materials.rebar import Rebar, bar_area
from tcvn5574.report.pdf import CalcReport, draw_section, fmt
from tcvn5574.sections.rectangular import RectangularBeamSection
from tcvn5574.shear.beam_shear import check_beam_shear
from tcvn5574.sls.crack import check_beam_cracking
from tcvn5574.sls.deflection import BeamBoundaryCondition, check_beam_deflection
from tcvn5574.torsion.beam_torsion import check_beam_torsion

_S_TEXT = {
    BeamBoundaryCondition.SIMPLY_SUPPORTED_UDL: ("5/48", 5 / 48),
    BeamBoundaryCondition.FIXED_ENDS_UDL: ("1/16", 1 / 16),
    BeamBoundaryCondition.CANTILEVER_UDL: ("1/4", 0.25),
}


def bars_text(group) -> str:
    if not group or not group.layers:
        return "—"
    return " + ".join(f"{l.n_bars}Ø{l.diameter:g}" for l in group.layers)


def add_inputs(r: CalcReport, sec: RectangularBeamSection, concrete: Concrete, rebar: Rebar,
               stirrup: Optional[Rebar] = None, stirrup_text: str = "", forces=()):
    """forces: iterable of (label, symbol, value, unit)."""
    rows = [("Tiết diện", None, None, None), ("Bề rộng", "b", sec.b, "mm"), ("Chiều cao", "h", sec.h, "mm")]
    if sec.has_flange:
        rows += [("Bề rộng cánh", "b'f", sec.bf, "mm"), ("Chiều dày cánh", "h'f", sec.hf, "mm"),
                 ("Vị trí cánh", "", "vùng kéo" if sec.flange_in_tension else "vùng nén", "")]
    rows += [("Thép chịu kéo", "As", f"{bars_text(sec.tensile_rebar)}", f"a = {sec.a:.0f}"),
             ("Thép chịu nén", "A's", f"{bars_text(sec.comp_rebar)}", f"a' = {sec.a_prime:.0f}" if sec.Asc else "")]
    if stirrup_text:
        rows.append(("Cốt đai", "", stirrup_text, ""))
    rows += [("Vật liệu", None, None, None),
             (f"Bê tông {concrete.grade.value}", "Rb", concrete.Rb_calc, "MPa"),
             ("", "Rbt", concrete.Rbt_calc, "MPa"),
             ("", "Rb,ser", concrete.Rb_ser, "MPa"),
             ("", "Rbt,ser", concrete.Rbt_ser, "MPa"),
             ("", "Eb", concrete.Eb, "MPa"),
             (f"Thép dọc {rebar.grade.value}", "Rs = Rsc", f"{rebar.Rs_calc:g} / {rebar.Rsc_calc:g}", "MPa"),
             ("", "Rs,ser", rebar.Rs_ser, "MPa"),
             ("", "Es", rebar.Es, "MPa")]
    if stirrup:
        rows.append((f"Thép đai {stirrup.grade.value}", "Rsw", stirrup.Rsw_calc, "MPa"))
    if forces:
        rows.append(("Nội lực", None, None, None))
        rows += list(forces)
    r.heading("Số liệu đầu vào", "Bảng 6, 7, 10, 13, 14 TCVN 5574:2018")
    r.input_block(rows, sketch=lambda pdf, x, y, w, h: draw_section(pdf, sec, x, y, w, h))


def add_flexure(r: CalcReport, M_kNm: float, sec, concrete, rebar):
    res = check_beam_flexure(M_kNm, sec, concrete, rebar)
    Rb, Rs, Rsc, Es = concrete.Rb_calc, rebar.Rs_calc, rebar.Rsc_calc, rebar.Es
    b, h, h0, As, Asc, a, ap = sec.b, sec.h, sec.h0, sec.As, sec.Asc, sec.a, sec.a_prime
    M = abs(M_kNm)
    r.heading("Uốn — tiết diện thẳng góc", "8.1.2.3")
    r.step("Chiều cao làm việc", f"h0 = h − a = {h:g} − {fmt(a)} = {fmt(h0)} mm")
    r.step("Diện tích thép", f"As = {bars_text(sec.tensile_rebar)} = {fmt(As)} mm²;   A's = {bars_text(sec.comp_rebar)} = {fmt(Asc)} mm²")
    r.step("Giới hạn vùng nén", f"ξR = 0.8/(1 + εs,el/εb2) = 0.8/(1 + {Rs:g}/{Es:g}/0.0035) = {res.xi_R:.3f}", "CT (31), (32)")
    Nf, width = 0.0, b
    if sec.has_compression_flange:
        cap = Rb * sec.bf * sec.hf + Rsc * Asc
        if Rs * As <= cap:
            width = sec.bf
            r.step("Trục trung hòa", f"Rs·As = {fmt(Rs * As / 1e3)} kN ≤ Rb·b'f·h'f + Rsc·A's = {fmt(cap / 1e3)} kN → qua cánh, tính với b'f = {sec.bf:g}", "CT (36)")
        else:
            Nf = Rb * (sec.bf - b) * sec.hf
            r.step("Trục trung hòa", f"Rs·As = {fmt(Rs * As / 1e3)} kN > {fmt(cap / 1e3)} kN → qua sườn", "CT (36)")
    if Nf:
        r.step("Vùng nén", f"x = (Rs·As − Rsc·A's − Rb(b'f − b)h'f)/(Rb·b) = ({Rs:g}×{fmt(As)} − {Rsc:g}×{fmt(Asc)} − {fmt(Nf)})/({Rb:g}×{b:g}) = {fmt(res.x_mm)} mm", "CT (38)")
    else:
        r.step("Vùng nén", f"x = (Rs·As − Rsc·A's)/(Rb·b) = ({Rs:g}×{fmt(As)} − {Rsc:g}×{fmt(Asc)})/({Rb:g}×{width:g}) = {fmt(res.x_mm)} mm", "CT (35)")
    r.step("", f"ξ = x/h0 = {fmt(res.x_mm)}/{fmt(h0)} = {res.xi:.3f} {'≤' if res.xi <= res.xi_R else '>'} ξR = {res.xi_R:.3f}")
    if "x <= 2a'" in res.failure_mode:
        r.step("Khả năng chịu uốn", f"x ≤ 2a' = {fmt(2 * ap)} → Mu = Rs·As·(h0 − a') = {Rs:g}×{fmt(As)}×({fmt(h0)} − {fmt(ap)}) = {fmt(res.Mu_kNm)} kNm", "8.1.2.3.6")
    else:
        x = min(res.x_mm, res.xi_R * h0)
        if "Over" in res.failure_mode:
            r.step("", f"ξ > ξR → lấy x = ξR·h0 = {fmt(x)} mm", "8.1.2.3.5")
        terms = f"{Rb:g}×{width:g}×{fmt(x)}×({fmt(h0)} − {fmt(x / 2)})"
        if Nf:
            terms += f" + {fmt(Nf)}×({fmt(h0)} − {fmt(sec.hf / 2)})"
        if Asc:
            terms += f" + {Rsc:g}×{fmt(Asc)}×({fmt(h0)} − {fmt(ap)})"
        formula = "Rb·b·x(h0 − 0.5x)" + (" + Rb(b'f − b)h'f(h0 − 0.5h'f)" if Nf else "") + (" + Rsc·A's(h0 − a')" if Asc else "")
        r.step("Khả năng chịu uốn", f"Mu = {formula} = {terms} = {fmt(res.Mu_kNm)} kNm", "CT (34), (37)")
    r.result(f"M = {fmt(M)} kNm ≤ Mu = {fmt(res.Mu_kNm)} kNm   (UR = {res.utilization_ratio:.3f})" if res.is_safe
             else f"M = {fmt(M)} kNm > Mu = {fmt(res.Mu_kNm)} kNm   (UR = {res.utilization_ratio:.3f})", res.is_safe)
    r.step("Hàm lượng", f"μ = As/(b·h0) = {fmt(As)}/({b:g}×{fmt(h0)}) = {sec.mu_percent:.3f}% {'≥' if sec.mu_percent >= 0.1 else '<'} μmin = 0.10%", "10.3.3.1")
    return res


def add_shear(r: CalcReport, Q_kN, sec, concrete, stirrup, d_sw, n_legs, s, q1_kN_per_m=0.0, a_load_mm=None):
    res = check_beam_shear(Q_kN, sec, concrete, stirrup, d_sw, n_legs, s, q1_kN_per_m, a_load_mm)
    Rb, Rbt, b, h0 = concrete.Rb_calc, concrete.Rbt_calc, sec.b, sec.h0
    Q = abs(Q_kN)
    Asw = n_legs * bar_area(d_sw)
    C, qsw = res.C_mm, res.qsw_N_per_mm
    r.heading("Cắt — tiết diện nghiêng", "8.1.3")
    r.step("Dải nén giữa vết nứt", f"0.3·Rb·b·h0 = 0.3×{Rb:g}×{b:g}×{fmt(h0)} = {fmt(res.Q_max_strut_kN)} kN {'≥' if res.is_strut_safe else '<'} Q = {fmt(Q)} kN", "CT (88)")
    r.step("Cốt đai", f"{n_legs}Ø{d_sw:g} a{s:g}: Asw = {fmt(Asw)} mm²,  qsw = Rsw·Asw/sw = {stirrup.Rsw_calc:g}×{fmt(Asw)}/{s:g} = {fmt(qsw)} N/mm", "CT (92)")
    r.step("", f"0.25·Rbt·b = 0.25×{Rbt:g}×{b:g} = {fmt(0.25 * Rbt * b)} N/mm {'≤' if res.is_qsw_min_ok else '>'} qsw"
           + ("" if res.is_qsw_min_ok else " → Qb theo CT (97)"), "CT (96)")
    load = f"q1 = {q1_kN_per_m:g} kN/m" + (f", a = {a_load_mm:g} mm" if a_load_mm else "")
    r.step("Tiết diện nguy hiểm", f"C = argmin[Qb(C) + Qsw(C) + q1·C] với C ≤ min(3h0{', a' if a_load_mm else ''}); {load} → C = {fmt(C)} mm", "8.1.3.3.1")
    Qb_raw = 1.5 * (Rbt * b if res.is_qsw_min_ok else 4 * qsw) * h0**2 / C / 1e3 if C > 0 else float("inf")
    base = f"1.5×{Rbt:g}×{b:g}" if res.is_qsw_min_ok else f"6×{fmt(qsw)}"
    r.step("Bê tông chịu cắt", f"Qb = {'1.5·Rbt·b' if res.is_qsw_min_ok else '6·qsw'}·h0²/C = {base}×{fmt(h0)}²/{fmt(C)} = {fmt(Qb_raw)} kN; "
           f"[{fmt(0.5 * Rbt * b * h0 / 1e3)}; {fmt(2.5 * Rbt * b * h0 / 1e3)}] → Qb = {fmt(res.Qb_kN)} kN", "CT (90)")
    C0 = min(max(C, h0), 2 * h0)
    r.step("Cốt đai chịu cắt", f"Qsw = 0.75·qsw·C0 = 0.75×{fmt(qsw)}×{fmt(C0)} = {fmt(res.Qsw_kN)} kN  (h0 ≤ C0 ≤ 2h0)", "CT (91)")
    r.step("Khả năng chịu cắt", f"Qu = Qb + Qsw + q1·C = {fmt(res.Qb_kN)} + {fmt(res.Qsw_kN)} + {q1_kN_per_m:g}×{fmt(C / 1e3)} = {fmt(res.Qu_kN)} kN", "CT (89)")
    r.result(f"Q = {fmt(Q)} kN {'≤' if res.is_safe else '>'} Qu = {fmt(res.Qu_kN)} kN   (UR = {res.utilization_ratio:.3f})", res.is_safe)
    smax = min(res.s_max_calc_mm, res.s_max_constructive_mm)
    r.step("Bước đai", f"sw,max = Rbt·b·h0²/Q = {Rbt:g}×{b:g}×{fmt(h0)}²/{fmt(Q * 1e3)} = {fmt(res.s_max_calc_mm)} mm;  cấu tạo ≤ {fmt(res.s_max_constructive_mm)} mm", "CT (98), 10.3.4.3")
    r.result(f"sw = {s:g} mm {'≤' if res.is_spacing_ok else '>'} {fmt(smax)} mm", res.is_spacing_ok)
    return res


def add_torsion(r: CalcReport, T_kNm, M3_kNm, V2_kN, sec, concrete, rebar, stirrup, d_sw, s, n_legs, M2_kNm=0.0, V3_kN=0.0, side_As=0.0):
    t = check_beam_torsion(T_kNm, M3_kNm, V2_kN, sec, concrete, rebar, stirrup, d_sw, s, n_legs, M2_kNm, V3_kN, side_As)
    Rb, b, h = concrete.Rb_calc, min(sec.b, sec.h), max(sec.b, sec.h)
    T = abs(T_kNm)
    qsw1 = stirrup.Rsw_calc * bar_area(d_sw) / s
    r.heading("Xoắn", "8.1.4")
    r.step("Nén giữa tiết diện không gian", f"0.1·Rb·b²·h = 0.1×{Rb:g}×{b:g}²×{h:g} = {fmt(t.T_max_crushing_kNm)} kNm", "CT (102)")
    r.step("", f"T/T0 + Q/(0.3Rb·b·h0) = {t.ratio_strut_TQ:.3f} {'≤' if t.ratio_strut_TQ <= 1.001 else '>'} 1", "8.1.4.4.1")
    r.step("Tiết diện không gian", f"qsw,1 = Rsw·asw/sw = {stirrup.Rsw_calc:g}×{fmt(bar_area(d_sw))}/{s:g} = {fmt(qsw1)} N/mm;  "
           f"T0 = min_C[0.9·qsw,1·δ·C·Z2 + 0.9·Rs·As,1·Z1·Z2/C], δ = Z1/(2Z2 + Z1), 0.5 ≤ qsw,1·Z1/(Rs·As,1) ≤ 1.5", "CT (103)–(110)")
    r.step("", f"Biên dưới: T0 = {fmt(t.T0_bottom_kNm)} kNm;  biên trên: T0 = {fmt(t.T0_top_kNm)} kNm;  biên bên: T0 = {fmt(t.T0_side_kNm)} kNm")
    r.step("Xoắn thuần túy", f"T/T0,trên = {fmt(T)}/{fmt(t.T0_top_kNm)} = {t.ratio_T_top:.3f}", "8.1.4.2.2")
    r.step("Uốn + xoắn", f"(T/T0)² + (M/M0)² = {t.ratio_MT_major:.3f}", "CT (114)")
    r.step("Cắt + xoắn", f"T/T0 + Q/Q0 = {t.ratio_QT_major:.3f}", "CT (115)")
    if M2_kNm or V3_kN:
        r.step("Phương phụ", f"M2 + T: {t.ratio_MT_minor:.3f};   V3 + T: {t.ratio_QT_minor:.3f}")
    worst = max(t.ratio_crushing, t.ratio_strut_TQ, t.ratio_T_top, t.ratio_MT_major, t.ratio_QT_major, t.ratio_MT_minor, t.ratio_QT_minor)
    r.result(f"Tỉ số lớn nhất = {worst:.3f} {'≤' if t.is_overall_safe else '>'} 1", t.is_overall_safe)
    return t


def add_cracking(r: CalcReport, M_short_kNm, M_long_kNm, sec, concrete, rebar, requirement=CrackRequirement.INTEGRITY):
    res = check_beam_cracking(M_short_kNm, M_long_kNm, sec, concrete, rebar, requirement)
    Es, Eb = rebar.Es, concrete.Eb
    alpha = Es / Eb
    tp = sec.get_transformed_properties(alpha)
    r.heading("Vết nứt thẳng góc", "8.2.2")
    r.step("Nội lực tiêu chuẩn", f"M = {fmt(abs(M_short_kNm))} kNm (toàn bộ tải);  Ml = {fmt(abs(M_long_kNm))} kNm (thường xuyên + tạm thời dài hạn)")
    r.step("Tiết diện quy đổi", f"α = Es/Eb = {Es:g}/{Eb:g} = {alpha:.2f};  Ared = A + α(As + A's) = {fmt(tp['Ared'])} mm²;  yt = St,red/Ared = {fmt(tp['yt'])} mm", "CT (163), (164)")
    r.step("", f"Ired = {fmt(tp['Ired'])} mm⁴;  Wred = Ired/yt = {fmt(tp['Wred'])} mm³;  Wpl = γ·Wred = {tp['gamma']:g}×{fmt(tp['Wred'])} = {fmt(tp['Wpl'])} mm³",
           "CT (159), (160)" + (", Bảng L.1" if sec.flange_in_tension else ""))
    r.step("Mô men gây nứt", f"Mcrc = Rbt,ser·Wpl = {concrete.Rbt_ser:g}×{fmt(tp['Wpl'])} = {fmt(res.Mcrc_kNm)} kNm", "CT (158)")
    if not res.is_cracked:
        r.result(f"M = {fmt(abs(M_short_kNm))} kNm ≤ Mcrc = {fmt(res.Mcrc_kNm)} kNm → không hình thành vết nứt", True)
        return res
    names = {1: ("acrc,1", "Ml, dài hạn"), 2: ("acrc,2", "M, ngắn hạn"), 3: ("acrc,3", "Ml, ngắn hạn")}
    first = next(d for d in (res.detail2, res.detail1, res.detail3) if d)
    r.step("Hệ số quy đổi", f"Eb,red = Rb,ser/εb1,red = {concrete.Rb_ser:g}/0.0015 = {fmt(first.Eb_red)} MPa;  αs1 = αs2 = Es/Eb,red = {first.alpha_s1:.2f}", "CT (168), (169)")
    r.step("Tiết diện nứt", f"x = h0[√((μs·αs2 + μ's·αs1)² + 2(μs·αs2 + μ's·αs1·a'/h0)) − (μs·αs2 + μ's·αs1)] = {fmt(first.x_mm)} mm;  "
           f"Ired = Ib + αs2·Is + αs1·I's = {fmt(first.Ired_mm4)} mm⁴", "CT (193), (196)")
    r.step("Khoảng cách vết nứt", f"yt = {fmt(first.yt_mm)} mm ∈ [2a; 0.5h] = [{fmt(2 * sec.a)}; {fmt(0.5 * sec.h)}];  Abt = {fmt(first.Abt_mm2)} mm²;  ds = {fmt(first.ds_mm)} mm", "8.2.2.3.3")
    r.step("", f"Ls = 0.5·Abt·ds/As = 0.5×{fmt(first.Abt_mm2)}×{fmt(first.ds_mm)}/{fmt(sec.As)} = {fmt(first.Ls_calc_mm)} → "
           f"[max(10ds; 100); min(40ds; 400)] → Ls = {fmt(first.Ls_mm)} mm", "CT (174)")
    for i, d in ((1, res.detail1), (2, res.detail2), (3, res.detail3)):
        name, desc = names[i]
        if d is None:
            r.step(f"{name} ({desc})", f"{desc.split(',')[0]} ≤ Mcrc → {name} = 0")
            continue
        cap = f" → σs = Rs,ser = {fmt(d.sigma_s)}" if d.sigma_s < d.sigma_s_calc else ""
        r.step(f"{name} ({desc})", f"σs = M(h0 − x)αs1/Ired = {fmt(d.M_kNm)}E6×({fmt(sec.h0)} − {fmt(d.x_mm)})×{d.alpha_s1:.2f}/{fmt(d.Ired_mm4)} = {fmt(d.sigma_s_calc)} MPa{cap};  "
               f"ψs = 1 − 0.8×{fmt(res.Mcrc_kNm)}/{fmt(d.M_kNm)} = {d.psi_s:.3f}", "CT (167), (176)")
        r.step("", f"{name} = φ1·φ2·φ3·ψs·σs·Ls/Es = {d.phi1:g}×{d.phi2:g}×{d.phi3:g}×{d.psi_s:.3f}×{fmt(d.sigma_s)}×{fmt(d.Ls_mm)}/{Es:g} = {d.acrc_mm:.3f} mm", "CT (166)")
    req = "an toàn cốt thép" if CrackRequirement(requirement) == CrackRequirement.INTEGRITY else "hạn chế thấm"
    r.step("Giới hạn", f"acrc,ult = {res.acrc_short_allowable_mm} mm (ngắn hạn), {res.acrc_long_allowable_mm} mm (dài hạn) — {req}", "Bảng 17")
    r.result(f"acrc,1 = {res.acrc_long_mm:.3f} mm {'≤' if res.is_long_term_safe else '>'} {res.acrc_long_allowable_mm} mm", res.is_long_term_safe, "Dài hạn")
    r.result(f"acrc = {res.acrc1_mm:.3f} + {res.acrc2_mm:.3f} − {res.acrc3_mm:.3f} = {res.acrc_short_mm:.3f} mm "
             f"{'≤' if res.is_short_term_safe else '>'} {res.acrc_short_allowable_mm} mm", res.is_short_term_safe, "Ngắn hạn  CT (157)")
    return res


def add_deflection(r: CalcReport, span_mm, M_short_kNm, M_long_kNm, sec, concrete, rebar,
                   boundary=BeamBoundaryCondition.SIMPLY_SUPPORTED_UDL, humidity=HumidityCondition.MEDIUM, f_allowable_ratio=250.0):
    d = check_beam_deflection(span_mm, M_short_kNm, M_long_kNm, sec, concrete, rebar, boundary, humidity, f_allowable_ratio)
    s_txt, s_val = _S_TEXT[BeamBoundaryCondition(boundary)]
    phi = concrete.get_creep_coefficient(humidity)
    r.heading("Độ võng", "8.2.3")
    r.step("Thông số", f"L = {span_mm:g} mm;  s = {s_txt};  W = {HumidityCondition(humidity).value} → φb,cr = {phi:g};  Mcrc = {fmt(d.Mcrc_kNm)} kNm", "Bảng 11")
    if d.is_cracked:
        r.step("Có vết nứt", "D = Eb,red·Ired;  Eb,red = Rb,ser/εb1,red (0.0015 ngắn hạn, Bảng 9 dài hạn);  αs1 = Es/Eb,red,  αs2 = Es/(ψs·Eb,red)", "CT (193)–(204)")
        r.step("", f"(1/r)1 = M/D (ngắn hạn, toàn bộ tải) = {fmt(d.curvature_1)} 1/mm")
        r.step("", f"(1/r)2 = Ml/D (ngắn hạn, tải dài hạn) = {fmt(d.curvature_2)} 1/mm")
        r.step("", f"(1/r)3 = Ml/D (dài hạn, tải dài hạn) = {fmt(d.curvature_3)} 1/mm")
        r.step("Độ cong toàn phần", f"1/r = {fmt(d.curvature_1)} − {fmt(d.curvature_2)} + {fmt(d.curvature_3)} = {fmt(d.curvature_total)} 1/mm", "CT (186)")
    else:
        r.step("Không nứt", f"D = Eb1·Ired, α = Es/Eb1;  Eb1 = 0.85Eb = {fmt(0.85 * concrete.Eb)} MPa (ngắn hạn), Eb/(1 + φb,cr) = {fmt(concrete.Eb / (1 + phi))} MPa (dài hạn)", "CT (188)–(192)")
        r.step("Độ cong toàn phần", f"1/r = (M − Ml)/D1 + Ml/D2 = {fmt(d.curvature_1)} + {fmt(d.curvature_2)} = {fmt(d.curvature_total)} 1/mm", "CT (185)")
    r.step("Độ võng", f"f = s·L²·(1/r) = {s_txt}×{span_mm:g}²×{fmt(d.curvature_total)} = {d.f_mm:.2f} mm", "CT (180)")
    r.result(f"f = {d.f_mm:.2f} mm {'≤' if d.is_safe else '>'} [f] = L/{f_allowable_ratio:g} = {d.f_allowable_mm:.2f} mm", d.is_safe)
    return d


def add_anchorage(r: CalcReport, diameter_mm, concrete, rebar, spliced_percentage=50.0):
    t = calculate_anchorage_length(diameter_mm, concrete, rebar, True)
    c = calculate_anchorage_length(diameter_mm, concrete, rebar, False)
    r.heading(f"Neo và nối thép Ø{diameter_mm:g}", "10.3.5, 10.3.6")
    r.step("Bám dính", f"Rbond = η1·η2·Rbt = {t.eta1:g}×{t.eta2:g}×{concrete.Rbt_calc:g} = {t.Rbond_MPa:.3f} MPa", "CT (256)")
    r.step("Neo cơ sở", f"l0,an = Rs·ds/(4·Rbond) = {rebar.Rs_calc:g}×{diameter_mm:g}/(4×{t.Rbond_MPa:.3f}) = {fmt(t.l0_an_mm)} mm = {t.l0_an_d:.1f}d", "CT (255)")
    r.result(f"lan (kéo) = max(1.0·l0,an; 0.3l0,an; 15d; 200) = {fmt(t.lan_mm)} mm ({t.lan_d:.1f}d);   lan (nén) = {fmt(c.lan_mm)} mm ({c.lan_d:.1f}d)", label="CT (257)")
    lk = calculate_lap_splice_length(diameter_mm, concrete, rebar, True, spliced_percentage)
    ln_ = calculate_lap_splice_length(diameter_mm, concrete, rebar, False, spliced_percentage)
    r.result(f"llap (kéo, α2 = {lk.alpha2:g}) = {fmt(lk.llap_mm)} mm ({lk.llap_d:.1f}d);   llap (nén, α2 = {ln_.alpha2:g}) = {fmt(ln_.llap_mm)} mm ({ln_.llap_d:.1f}d)",
             label=f"CT (259), {spliced_percentage:g}% nối")


def add_nonlinear(r: CalcReport, M_kNm: float, sec, concrete, rebar, N_kN: float = 0.0, n_points: int = 24):
    """Nonlinear deformation model (8.1.2.7): limit state figure and M-N diagram (needs concreteproperties)."""
    from tcvn5574.nonlinear import to_concrete_section
    from tcvn5574.report.figures import limit_state_figure, mn_figure

    code, cs = to_concrete_section(sec, concrete.grade.value, rebar.grade.value, gamma_b=concrete.gamma_b)
    Rb, Eb, Rs, Rsc, Es = concrete.Rb_calc, concrete.Eb, rebar.Rs_calc, rebar.Rsc_calc, rebar.Es
    M, N = abs(M_kNm), N_kN
    r.heading("Mô hình biến dạng phi tuyến", "8.1.2.7")
    r.step("Biểu đồ bê tông", f"3 đoạn thẳng: σb1 = 0.6Rb = {fmt(0.6 * Rb)} MPa tại εb1 = σb1/Eb = {0.6 * Rb / Eb * 1e3:.3f}‰;  "
           f"Rb = {Rb:g} MPa tại εb0 = 2.0‰;  εb2 = 3.5‰;  không kể bê tông chịu kéo", "CT (8)–(10)")
    r.step("Biểu đồ cốt thép", f"2 đoạn thẳng: εs0 = Rs/Es = {Rs:g}/{Es:g} = {Rs / Es * 1e3:.3f}‰;  Rs = {Rs:g}, Rsc = {Rsc:g} MPa;  εs,u = 25‰", "6.2.4, CT (15)")
    r.step("Điều kiện giới hạn", "|εb,max| ≤ εb,u;  εs,max ≤ εs,u = 0.025;  εb,u = εb2 (biến dạng hai dấu), "
           "εb,u = εb2 − (εb2 − εb0)·ε1/ε2 (biến dạng một dấu)", "CT (70), (71), (86)")
    r.step("Lực dọc giới hạn", f"Nc = Σ Rb·Ab + Σ σs(εb0)·As = {fmt(code.squash_load / 1e3)} kN;  Nt = −Σ Rs·As = {fmt(code.tensile_load / 1e3)} kN")
    theta = 0.0 if M_kNm >= 0 else math.pi
    res = code.ultimate_bending_capacity(theta=theta, n=N * 1e3)
    gov = {"concrete": "bê tông vùng nén đạt εb2", "steel": "cốt thép chịu kéo đạt εs,u", "one-sign": "biến dạng một dấu (CT 86)"}[res.governing]
    x_txt = "∞" if math.isinf(res.d_n) else f"{fmt(res.d_n)} mm"
    face = "thớ trên chịu nén" if theta == 0 else "thớ dưới chịu nén"
    r.step("Trạng thái giới hạn", f"N = {fmt(N)} kN, {face} → chiều cao vùng nén x = {x_txt};  εb,max = {res.eps_b_max * 1e3:.3f}‰;  "
           f"εs,max = {res.eps_s_max * 1e3:.3f}‰;  quyết định bởi: {gov}", "cân bằng ΣN = N")
    ok, mu_neg, mu_pos = code.check_point(N * 1e3, M_kNm * 1e6)
    Mu = abs(res.m_x) / 1e6
    r.step("Khả năng chịu uốn", f"Mgh⁺(N) = {fmt(mu_pos / 1e6)} kNm;  Mgh⁻(N) = {fmt(mu_neg / 1e6)} kNm  (mô men lấy với trọng tâm tiết diện)")
    r.result(f"Mgh⁻ = {fmt(mu_neg / 1e6)} ≤ M = {fmt(M_kNm)} ≤ Mgh⁺ = {fmt(mu_pos / 1e6)} kNm   (UR = {M / Mu:.3f})" if ok
             else f"M = {fmt(M_kNm)} kNm nằm ngoài [{fmt(mu_neg / 1e6)}; {fmt(mu_pos / 1e6)}] kNm", ok)
    r.figure(limit_state_figure(code, res), 0.98, f"Trạng thái giới hạn tại N = {fmt(N)} kN ({face})")
    branches = [code.moment_interaction_diagram(theta=0.0, n_points=n_points), code.moment_interaction_diagram(theta=math.pi, n_points=n_points)]
    r.figure(mn_figure(branches, [(N, M_kNm, "Nội lực thiết kế", ok)]), 0.75, "Biểu đồ tương tác M–N (mô hình biến dạng phi tuyến)")
    return res, ok, M / Mu if Mu > 0 else float("inf")


def beam_report(
    path: str,
    section: RectangularBeamSection,
    concrete: Concrete,
    rebar: Rebar,
    *,
    title: str = "Kiểm tra dầm BTCT",
    subtitle: str = "",
    stirrup_rebar: Optional[Rebar] = None,
    stirrup_diameter_mm: float = 8.0,
    n_legs: int = 2,
    s_mm: float = 150.0,
    M_kNm: Optional[float] = None,
    Q_kN: Optional[float] = None,
    q1_kN_per_m: float = 0.0,
    a_load_mm: Optional[float] = None,
    T_kNm: Optional[float] = None,
    M_short_kNm: Optional[float] = None,
    M_long_kNm: Optional[float] = None,
    requirement: CrackRequirement = CrackRequirement.INTEGRITY,
    span_mm: Optional[float] = None,
    boundary: BeamBoundaryCondition = BeamBoundaryCondition.SIMPLY_SUPPORTED_UDL,
    humidity: HumidityCondition = HumidityCondition.MEDIUM,
    f_allowable_ratio: float = 250.0,
    anchorage_diameter_mm: Optional[float] = None,
    nonlinear: bool = False,
    N_kN: float = 0.0,
    mn_points: int = 24,
) -> str:
    """Write a PDF calculation sheet with every check whose forces are given. Returns path.

    nonlinear=False: bending by the limit-force method (8.1.2.3). nonlinear=True: bending by the nonlinear
    deformation model (8.1.2.7) with axial force N_kN, limit state figure and M-N diagram.
    """
    r = CalcReport(title)
    r.doc_title(title, subtitle or "Theo TCVN 5574:2018")

    forces = []
    if M_kNm is not None:
        forces.append(("Mô men tính toán", "M", abs(M_kNm), "kNm"))
    if Q_kN is not None:
        forces.append(("Lực cắt tính toán", "Q", abs(Q_kN), "kN"))
    if N_kN:
        forces.append(("Lực dọc (nén +)", "N", N_kN, "kN"))
    if T_kNm:
        forces.append(("Mô men xoắn", "T", abs(T_kNm), "kNm"))
    if M_short_kNm is not None:
        forces.append(("Mô men tiêu chuẩn", "Mn", abs(M_short_kNm), "kNm"))
        forces.append(("Phần dài hạn", "Ml", abs(M_long_kNm if M_long_kNm is not None else M_short_kNm), "kNm"))
    if span_mm:
        forces.append(("Nhịp", "L", span_mm, "mm"))
    st_text = f"{n_legs}Ø{stirrup_diameter_mm:g} a{s_mm:g}" if stirrup_rebar else ""
    add_inputs(r, section, concrete, rebar, stirrup_rebar, st_text, forces)

    summary = []
    if M_kNm is not None:
        if nonlinear:  # 8.1.2.7 nonlinear deformation model (with N)
            _, ok_nl, ur_nl = add_nonlinear(r, M_kNm, section, concrete, rebar, N_kN, mn_points)
            summary.append(("Uốn (phi tuyến)", ur_nl, ok_nl))
        else:  # 8.1.2.3 limit-force method
            f = add_flexure(r, M_kNm, section, concrete, rebar)
            if N_kN:
                r.note(f"Phương pháp nội lực giới hạn không kể lực dọc N = {N_kN:g} kN; dùng nonlinear=True hoặc column_report.")
            summary.append(("Uốn", f.utilization_ratio, f.is_safe))
    if Q_kN is not None and stirrup_rebar:
        sh = add_shear(r, Q_kN, section, concrete, stirrup_rebar, stirrup_diameter_mm, n_legs, s_mm, q1_kN_per_m, a_load_mm)
        summary.append(("Cắt", sh.utilization_ratio, sh.is_safe and sh.is_spacing_ok))
    if T_kNm and stirrup_rebar:
        t = add_torsion(r, T_kNm, M_kNm or 0.0, Q_kN or 0.0, section, concrete, rebar, stirrup_rebar, stirrup_diameter_mm, s_mm, n_legs)
        summary.append(("Xoắn", max(t.ratio_crushing, t.ratio_strut_TQ, t.ratio_T_top, t.ratio_MT_major, t.ratio_QT_major), t.is_overall_safe))
    if M_short_kNm is not None:
        Ml = M_long_kNm if M_long_kNm is not None else M_short_kNm
        c = add_cracking(r, M_short_kNm, Ml, section, concrete, rebar, requirement)
        summary.append(("Vết nứt", max(c.acrc_short_mm / c.acrc_short_allowable_mm, c.acrc_long_mm / c.acrc_long_allowable_mm), c.is_safe))
        if span_mm:
            d = add_deflection(r, span_mm, M_short_kNm, Ml, section, concrete, rebar, boundary, humidity, f_allowable_ratio)
            summary.append(("Độ võng", d.f_mm / d.f_allowable_mm, d.is_safe))
    if anchorage_diameter_mm:
        add_anchorage(r, anchorage_diameter_mm, concrete, rebar)

    if summary:
        r.heading("Tổng hợp")
        for name, ur, ok in summary:
            r.result(f"UR = {ur:.3f}", ok, name)
    r.output(path)
    return path
