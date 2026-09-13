"""Matplotlib figures of the nonlinear model (limit strain / stress state, M-N diagram) -> PNG bytes."""

from __future__ import annotations

import io
import math

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

RED, BLUE, GREY, GREEN = "#c00000", "#1f49a0", "#5a5a6e", "#008000"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 8})


def _png(fig) -> io.BytesIO:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=200, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


def limit_state_figure(code, result, title: str = "") -> io.BytesIO:
    """Section with neutral axis | strain diagram | stress diagram at the limit state (theta = 0).

    The compressed face is the top for theta = 0 and the bottom for theta = pi. Concrete stress sigma_b(y)
    from the ultimate TCVN diagram, steel bar stresses as horizontal arrows (tension to the left).
    """
    cs = code.concrete_section
    polys = [g.geom for g in cs.concrete_geometries]
    y_top = max(p.bounds[3] for p in polys)
    y_bot = min(p.bounds[1] for p in polys)
    H = y_top - y_bot
    d_n, eps2 = result.d_n, result.eps_b_max
    one_sign = math.isinf(d_n)

    top_compressed = math.cos(result.theta) >= 0
    y_c = y_top if top_compressed else y_bot

    def strain(y):
        return eps2 if one_sign else eps2 * (d_n - abs(y_c - y)) / d_n

    fig, (ax0, ax1, ax2) = plt.subplots(1, 3, figsize=(7.2, 3.3), sharey=True, gridspec_kw={"width_ratios": [1.25, 0.85, 1.1]})

    # --- section
    for p in polys:
        x, y = p.exterior.xy
        ax0.fill(x, y, color="#e6e6e6", ec=BLUE, lw=1.2)
    for g in cs.reinf_geometries_lumped:
        cx, cy = g.calculate_centroid()
        r = math.sqrt(g.calculate_area() / math.pi)
        ax0.add_patch(plt.Circle((cx, cy), r, color=RED))
    xmin = min(p.bounds[0] for p in polys)
    xmax = max(p.bounds[2] for p in polys)
    if not one_sign and d_n < H:
        yna = y_top - d_n if top_compressed else y_bot + d_n
        ax0.plot([xmin - 0.08 * (xmax - xmin), xmax + 0.08 * (xmax - xmin)], [yna, yna], "--", color=GREEN, lw=1)
        ax0.text(xmax, yna, f"  x = {d_n:.1f}", color=GREEN, va="bottom", ha="right", fontsize=7)
    ax0.set_aspect("equal")
    ax0.set_title("Tiết diện", color=GREY)
    ax0.axis("off")

    # --- strain
    ys = [y_bot, y_top]
    es = [strain(y) * 1e3 for y in ys]
    ax1.fill_betweenx(ys, 0, es, color=BLUE, alpha=0.15)
    ax1.plot(es, ys, color=BLUE, lw=1.2)
    ax1.axvline(0, color="black", lw=0.6)
    ax1.text(eps2 * 1e3, y_c, f"εb = {eps2 * 1e3:.2f}‰", ha="center", va="bottom" if top_compressed else "top", color=BLUE, fontsize=7)
    for g in cs.reinf_geometries_lumped:
        cy = g.calculate_centroid()[1]
        ax1.plot(strain(cy) * 1e3, cy, "o", color=RED, ms=3)
    y_far = y_bot if top_compressed else y_top
    ax1.text(strain(y_far) * 1e3, y_far, f"{strain(y_far) * 1e3:.2f}‰", ha="center", va="top" if top_compressed else "bottom", color=BLUE, fontsize=7)
    ax1.set_title("Biến dạng ε (‰)", color=GREY)
    ax1.tick_params(left=False, labelleft=False)
    for s in ("top", "right", "left"):
        ax1.spines[s].set_visible(False)

    # --- stress
    prof = cs.concrete_geometries[0].material.ultimate_stress_strain_profile
    n = 200
    yy = [y_bot + H * i / n for i in range(n + 1)]
    sb = [max(0.0, float(prof.get_stress(strain=strain(y)))) for y in yy]
    ax2.fill_betweenx(yy, 0, sb, color=BLUE, alpha=0.25, step=None)
    ax2.plot(sb, yy, color=BLUE, lw=1.2)
    ax2.axvline(0, color="black", lw=0.6)
    Rb = prof.get_compressive_strength()
    ax2.text(Rb, y_c, f"Rb = {Rb:g}", ha="center", va="bottom" if top_compressed else "top", color=BLUE, fontsize=7)
    smax = max(abs(float(g.material.stress_strain_profile.get_stress(strain=strain(g.calculate_centroid()[1])))) for g in cs.reinf_geometries_lumped) if cs.reinf_geometries_lumped else 1.0
    scale = 1.2 * Rb / smax if smax else 1.0
    seen = set()
    for g in cs.reinf_geometries_lumped:
        cy = g.calculate_centroid()[1]
        s = float(g.material.stress_strain_profile.get_stress(strain=strain(cy)))
        if round(cy, 1) in seen:
            continue
        seen.add(round(cy, 1))
        ax2.annotate("", xy=(s * scale, cy), xytext=(0, cy), arrowprops={"arrowstyle": "-|>", "color": RED, "lw": 1.2})
        ax2.text(s * scale, cy, f" σs = {s:.0f} ", color=RED, va="center", ha="right" if s < 0 else "left", fontsize=7)
    lim = 1.6 * Rb
    ax2.set_xlim(-lim, lim)
    ax2.set_title("Ứng suất (MPa)", color=GREY)
    ax2.tick_params(left=False, labelleft=False)
    for s in ("top", "right", "left"):
        ax2.spines[s].set_visible(False)

    if title:
        fig.suptitle(title, color=RED, fontsize=9, fontweight="bold")
    fig.tight_layout()
    return _png(fig)


def mn_figure(branches, design_points=(), title: str = "") -> io.BytesIO:
    """M-N interaction envelope (kNm, kN; compression +, signed M).

    branches: MomentInteractionResults for theta = 0 (M >= 0 side) and theta = pi, each ordered by decreasing N.
    design_points: [(N_kN, M_kNm, label, ok), ...].
    """
    pts = []
    for i, mi in enumerate(branches):
        n, m = mi.get_results_lists("m_x")
        seg = [(v / 1e6, u / 1e3) for u, v in zip(n, m)]
        pts += seg if i % 2 == 0 else seg[::-1]  # walk around the envelope
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    fig, ax = plt.subplots(figsize=(5.4, 4.0))
    ax.fill(xs, ys, color=BLUE, alpha=0.08)
    ax.plot(xs + xs[:1], ys + ys[:1], "-", color=BLUE, lw=1.5, label="Biểu đồ tương tác [M]–[N]")
    ax.plot(xs, ys, "o", color=BLUE, ms=2.5)
    for N, M, label, ok in design_points:
        c = GREEN if ok else RED
        ax.plot(M, N, "s", color=c, ms=6, zorder=5)
        right = M > 0.3 * max(abs(v) for v in xs)
        ax.annotate(f"{label}\n(M = {M:.1f}; N = {N:.1f})", (M, N), textcoords="offset points", xytext=(-8 if right else 8, 8),
                    ha="right" if right else "left", color=c, fontsize=7)
    ax.axhline(0, color="black", lw=0.6)
    ax.axvline(0, color="black", lw=0.6)
    ax.set_xlabel("M (kNm)")
    ax.set_ylabel("N (kN), nén +")
    ax.grid(True, lw=0.3, alpha=0.6)
    ax.legend(loc="upper right", fontsize=7, frameon=False)
    if title:
        ax.set_title(title, color=RED, fontsize=9, fontweight="bold")
    fig.tight_layout()
    return _png(fig)


def biaxial_figure(code, n: float, mx: float, my: float, theta: float, n_points: int = 24, title: str = "") -> io.BytesIO:
    """Section with the skew neutral axis and compressed zone | Mx-My interaction contour at N with the design point.

    n in N, mx / my in N.mm, theta = governing neutral-axis angle (concreteproperties convention).
    """
    from concreteproperties import utils
    from shapely.geometry import Polygon

    cs = code.concrete_section
    r = code.ultimate_bending_capacity(theta=theta, n=n)
    fig, (ax0, ax1) = plt.subplots(1, 2, figsize=(7.4, 3.6), gridspec_kw={"width_ratios": [1.0, 1.25]})

    polys = [g.geom for g in cs.concrete_geometries]
    for p in polys:
        x, y = p.exterior.xy
        ax0.fill(x, y, color="#e6e6e6", ec=BLUE, lw=1.2)
    pts = [pt for p in polys for pt in p.exterior.coords]
    v_max = max(utils.global_to_local(theta, x, y)[1] for x, y in pts)
    if math.isfinite(r.d_n):
        # compressed zone: local v >= v_max - d_n, clipped to the section
        big = 1e5
        u_dir = utils.local_to_global(theta, 1.0, 0.0)
        v_dir = utils.local_to_global(theta, 0.0, 1.0)
        c0 = (v_max - r.d_n) * v_dir[0], (v_max - r.d_n) * v_dir[1]
        half = Polygon([
            (c0[0] - big * u_dir[0], c0[1] - big * u_dir[1]), (c0[0] + big * u_dir[0], c0[1] + big * u_dir[1]),
            (c0[0] + big * u_dir[0] + big * v_dir[0], c0[1] + big * u_dir[1] + big * v_dir[1]),
            (c0[0] - big * u_dir[0] + big * v_dir[0], c0[1] - big * u_dir[1] + big * v_dir[1]),
        ])
        for p in polys:
            zone = Polygon(p.exterior).intersection(half)
            if not zone.is_empty and zone.geom_type == "Polygon":
                zx, zy = zone.exterior.xy
                ax0.fill(zx, zy, color=BLUE, alpha=0.25, lw=0)
        ax0.plot([c0[0] - big * u_dir[0], c0[0] + big * u_dir[0]], [c0[1] - big * u_dir[1], c0[1] + big * u_dir[1]], "--", color=GREEN, lw=1)
    for g in cs.reinf_geometries_lumped:
        cx, cy = g.calculate_centroid()
        ax0.add_patch(plt.Circle((cx, cy), math.sqrt(g.calculate_area() / math.pi), color=RED))
    xs0 = [p.bounds[0] for p in polys] + [p.bounds[2] for p in polys]
    ys0 = [p.bounds[1] for p in polys] + [p.bounds[3] for p in polys]
    pad = 0.08 * max(max(xs0) - min(xs0), max(ys0) - min(ys0))
    ax0.set_xlim(min(xs0) - pad, max(xs0) + pad)
    ax0.set_ylim(min(ys0) - pad, max(ys0) + pad)
    ax0.set_aspect("equal")
    ax0.axis("off")
    ax0.set_title(f"Vùng nén: x = {r.d_n:.0f} mm, εb = {r.eps_b_max * 1e3:.2f}‰", color=GREY, fontsize=8)

    bb = code.biaxial_bending_diagram(n=n, n_points=n_points)
    cx_ = [res.m_x / 1e6 for res in bb.results]
    cy_ = [res.m_y / 1e6 for res in bb.results]
    ax1.fill(cx_, cy_, color=BLUE, alpha=0.08)
    ax1.plot(cx_, cy_, "-o", color=BLUE, lw=1.4, ms=2.5, label=f"[Mx]–[My] tại N = {n / 1e3:.0f} kN")
    M, Mu = math.hypot(mx, my), math.hypot(r.m_x, r.m_y)
    ok = M <= Mu * (1 + 1e-9)
    c = GREEN if ok else RED
    ax1.plot([0, r.m_x / 1e6], [0, r.m_y / 1e6], ":", color=GREY, lw=1)
    ax1.plot(r.m_x / 1e6, r.m_y / 1e6, "o", color=GREY, ms=4)
    ax1.plot(mx / 1e6, my / 1e6, "s", color=c, ms=6, zorder=5)
    ax1.annotate(f"(Mx; My) = ({mx / 1e6:.1f}; {my / 1e6:.1f})\nUR = {M / Mu:.3f}", (mx / 1e6, my / 1e6), textcoords="offset points",
                 xytext=(8, -18), color=c, fontsize=7)
    ax1.axhline(0, color="black", lw=0.6)
    ax1.axvline(0, color="black", lw=0.6)
    ax1.set_xlabel("Mx (kNm)")
    ax1.set_ylabel("My (kNm)")
    ax1.set_aspect("equal", adjustable="datalim")
    ax1.grid(True, lw=0.3, alpha=0.6)
    ax1.legend(loc="upper right", fontsize=7, frameon=False)
    if title:
        fig.suptitle(title, color=RED, fontsize=9, fontweight="bold")
    fig.tight_layout()
    return _png(fig)
