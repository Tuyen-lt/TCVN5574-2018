"""Calculation-sheet PDF writer in 'The Concrete Centre' style, built on fpdf2.

Layout: INPUT block (symbol / unit / value) with the section sketch beside it, then an OUTPUT list of
formula lines: italic label or clause on the left, substituted formula = result on the right,
key results in bold red.
"""

import os

from fpdf import FPDF

_FONT_DIRS = [os.path.join(os.path.dirname(__file__), "fonts"), r"C:\Windows\Fonts", "/usr/share/fonts/truetype/dejavu"]

RED = (192, 0, 0)
BLUE = (31, 73, 160)
GREY = (90, 90, 110)
BLACK = (20, 20, 20)
GREEN = (0, 128, 0)


def _find_font(name: str) -> str:
    for d in _FONT_DIRS:
        p = os.path.join(d, name)
        if os.path.exists(p):
            return p
    raise FileNotFoundError(f"{name} not found; put DejaVuSans*.ttf into {_FONT_DIRS[0]}")


def fmt(v, nd=None) -> str:
    """Engineering number: 3-4 significant digits, scientific for very large/small."""
    if isinstance(v, str):
        return v
    if v == 0:
        return "0"
    if nd is None and float(v).is_integer() and abs(v) < 1e7:
        return f"{int(v)}"
    a = abs(v)
    if a >= 1e7 or a < 1e-3:
        m, e = f"{v:.3e}".split("e")
        return f"{m}E{int(e)}"
    if nd is None:
        nd = 0 if a >= 1000 else 1 if a >= 100 else 2 if a >= 1 else 3 if a >= 0.1 else 4
    return f"{v:.{nd}f}"


class CalcReport(FPDF):
    LABEL_W = 42.0  # left column (labels, clauses)

    def __init__(self, title: str):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.title_text = title
        self.add_font("DejaVu", "", _find_font("DejaVuSans.ttf"))
        self.add_font("DejaVu", "B", _find_font("DejaVuSans-Bold.ttf"))
        self.add_font("DejaVu", "I", _find_font("DejaVuSans-Oblique.ttf"))
        self.set_margins(14, 14, 14)
        self.set_auto_page_break(True, 16)
        self.alias_nb_pages()
        self.add_page()

    def footer(self):
        self.set_y(-11)
        self._font("I", 7, GREY)
        self.cell(0, 5, f"{self.title_text} — TCVN 5574:2018 — {self.page_no()}/{{nb}}", align="C")

    def _font(self, style="", size=9.0, color=BLACK):
        self.set_font("DejaVu", style, size)
        self.set_text_color(*color)

    # ---- blocks
    def doc_title(self, text: str, subtitle: str = ""):
        self._font("B", 14, BLACK)
        self.cell(0, 8, text, new_x="LMARGIN", new_y="NEXT")
        if subtitle:
            self._font("", 8.5, GREY)
            self.cell(0, 5, subtitle, new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(*RED)
        self.line(self.l_margin, self.get_y() + 1, self.w - self.r_margin, self.get_y() + 1)
        self.ln(3)

    def heading(self, text: str, right: str = ""):
        """Red section heading (like INPUT / OUTPUT)."""
        if self.will_page_break(14):
            self.add_page()
        self.ln(2)
        self._font("B", 10.5, RED)
        self.cell(self.epw * 0.7, 6.5, text.upper())
        self._font("I", 8, GREY)
        self.cell(self.epw * 0.3, 6.5, right, align="R", new_x="LMARGIN", new_y="NEXT")

    def input_block(self, rows, sketch=None, sketch_w: float = 62.0):
        """rows: (label, symbol, value, unit). sketch: callable(pdf, x, y, w, h) drawn on the right."""
        y0 = self.get_y()
        widths = (46.0, 20.0, 30.0, 14.0)
        for label, sym, val, unit in rows:
            if label and sym is None:  # sub-heading row
                self._font("B", 8.5, GREY)
                self.cell(sum(widths), 5, label, new_x="LMARGIN", new_y="NEXT")
                continue
            self._font("I", 8.5, GREY)
            self.cell(widths[0], 5, label, align="R")
            self._font("", 9, BLACK)
            self.cell(widths[1], 5, f"{sym} =" if sym else "", align="R")
            self._font("", 9, BLUE)
            self.cell(widths[2], 5, fmt(val) if not isinstance(val, str) else val, align="R")
            self._font("", 8, GREY)
            self.cell(widths[3], 5, f" {unit}", new_x="LMARGIN", new_y="NEXT")
        y1 = self.get_y()
        if sketch:
            x = self.w - self.r_margin - sketch_w
            h = max(y1 - y0, 55.0)
            sketch(self, x, y0, sketch_w, h)
            self.set_y(max(y1, y0 + h))
        self.ln(2)

    def step(self, label: str = "", expr: str = "", clause: str = "", bold: bool = False, color=BLACK):
        """One OUTPUT line: italic label/clause on the left, expression on the right."""
        left = label if label else clause
        sub = clause if (label and clause) else ""
        rw = self.epw - self.LABEL_W - 2
        self._font("B" if bold else "", 9, color)
        n_right = len(self.multi_cell(rw, 4.8, expr, align="L", dry_run=True, output="LINES"))
        n_left = (1 if left else 0) + (1 if sub else 0)
        h = 4.8 * max(n_right, n_left, 1) + 0.6
        if self.will_page_break(h):
            self.add_page()
        x, y = self.l_margin, self.get_y()
        if left:
            self._font("I", 8.5, GREY)
            self.set_xy(x, y)
            self.cell(self.LABEL_W, 4.8, left, align="R")
        if sub:
            self._font("I", 7, GREY)
            self.set_xy(x, y + 4.8)
            self.cell(self.LABEL_W, 4.0, sub, align="R")
        self._font("B" if bold else "", 9, color)
        self.set_xy(x + self.LABEL_W + 2, y)
        self.multi_cell(rw, 4.8, expr, align="L")
        self.set_xy(self.l_margin, y + h)

    def result(self, text: str, ok: bool = None, label: str = ""):
        """Bold red key result; ok=True/False appends a coloured verdict."""
        color = RED if ok is None else (GREEN if ok else RED)
        verdict = "" if ok is None else ("  → ĐẠT" if ok else "  → KHÔNG ĐẠT")
        self.step(label, text + verdict, bold=True, color=color)

    def figure(self, png, width_ratio: float = 0.95, caption: str = ""):
        """Centered image (PNG bytes / path), moved to a new page if it does not fit."""
        from PIL import Image

        if hasattr(png, "seek"):
            png.seek(0)
        w_px, h_px = Image.open(png).size
        if hasattr(png, "seek"):
            png.seek(0)
        w = self.epw * width_ratio
        h = w * h_px / w_px
        if self.will_page_break(h + 8):
            self.add_page()
        self.image(png, x=self.l_margin + (self.epw - w) / 2, y=self.get_y() + 1, w=w)
        self.set_y(self.get_y() + h + 2)
        if caption:
            self._font("I", 8, GREY)
            self.cell(0, 4.5, caption, align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(1)

    def note(self, text: str):
        self.step("", text, color=GREY)


# ---------------------------------------------------------------- section sketch
def draw_section(pdf: FPDF, sec, x: float, y: float, w: float, h: float, stirrup_d: float = 8.0):
    """Scaled cross-section: concrete outline (T flange if any), stirrup, bars, dimensions."""
    b, H = sec.b, sec.h
    bf = sec.bf if sec.has_flange else b
    pad = 8.0
    k = min((w - 2 * pad) / max(b, bf), (h - 2 * pad) / H)
    cx = x + w / 2
    top = y + pad
    tension_top = sec.flange_in_tension  # support section: slab and tension bars at the top

    pdf.set_draw_color(*BLUE)
    pdf.set_line_width(0.5)
    web_x = cx - b * k / 2
    if sec.has_flange:
        pdf.rect(cx - bf * k / 2, top, bf * k, sec.hf * k)
        pdf.rect(web_x, top + sec.hf * k, b * k, (H - sec.hf) * k)
        # hide the joint line under the web
        pdf.set_draw_color(255, 255, 255)
        pdf.line(web_x + 0.3, top + sec.hf * k, web_x + b * k - 0.3, top + sec.hf * k)
        pdf.set_draw_color(*BLUE)
    else:
        pdf.rect(web_x, top, b * k, H * k)

    def layer_y(dist, from_tension):
        at_top = tension_top if from_tension else not tension_top
        return top + dist * k if at_top else top + (H - dist) * k

    cover_side = None
    for group, from_tension in ((sec.tensile_rebar, True), (sec.comp_rebar, False)):
        if group:
            for l in group.layers:
                cover_side = min(cover_side or 1e9, l.distance_from_edge)
    cover_side = cover_side or 40.0

    # stirrup
    pdf.set_draw_color(0, 150, 100)
    pdf.set_line_width(0.3)
    s_in = (cover_side - 12.0) * k
    pdf.rect(web_x + s_in, top + s_in, b * k - 2 * s_in, H * k - 2 * s_in, round_corners=True, corner_radius=1.0)

    pdf.set_fill_color(*RED)
    for group, from_tension in ((sec.tensile_rebar, True), (sec.comp_rebar, False)):
        if not group:
            continue
        for l in group.layers:
            r = max(0.6, l.diameter * k / 2)
            yy = layer_y(l.distance_from_edge, from_tension)
            x0, x1 = web_x + cover_side * k, web_x + (b - cover_side) * k
            n = l.n_bars
            for i in range(n):
                xx = (x0 + x1) / 2 if n == 1 else x0 + (x1 - x0) * i / (n - 1)
                pdf.ellipse(xx - r, yy - r, 2 * r, 2 * r, style="F")

    # dimensions
    pdf.set_line_width(0.2)
    pdf.set_draw_color(*GREY)
    pdf.set_font("DejaVu", "", 7)
    pdf.set_text_color(*GREY)
    yb = top + H * k + 2.5
    pdf.line(web_x, yb, web_x + b * k, yb)
    pdf.set_xy(web_x, yb)
    pdf.cell(b * k, 3.5, f"b = {b:g}", align="C")
    xr = cx + max(b, bf) * k / 2 + 2.5
    pdf.line(xr, top, xr, top + H * k)
    pdf.set_xy(xr + 0.5, top + H * k / 2 - 2)
    pdf.cell(12, 3.5, f"h = {H:g}")
    if sec.has_flange:
        pdf.set_xy(cx - bf * k / 2, top - 4.5)
        pdf.cell(bf * k, 3.5, f"b'f = {bf:g}, h'f = {sec.hf:g}", align="C")
    pdf.set_text_color(*BLACK)
