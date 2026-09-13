"""TCVN 5574:2018 design code for concreteproperties (nonlinear deformation model, 8.1.2.7).

Arbitrary sections, ultimate bending with axial force, M-N interaction and biaxial bending, moment-curvature
and cracked / service stresses, with TCVN material diagrams:

- Concrete (6.1.4, Bảng 9): three-linear diagram sigma_b1 = 0.6 Rb at eps_b1 = sigma_b1/Eb, Rb at eps_b0,
  plateau to eps_b2 (CT 8-10); tension analogous with Rbt, eps_bt0, eps_bt2 (service profile only).
  Two-linear option: Eb,red = Rb/eps_b1,red (CT 11-13).
- Steel: two-linear, Rs in tension, Rsc in compression, eps_s,u = 0.025.
- Failure (8.1.2.7.5, 8.1.2.7.11): eps_b,max = eps_b,u or eps_s,max = eps_s,u, whichever governs;
  eps_b,u = eps_b2 for two-sign strain diagrams, eps_b2 - (eps_b2 - eps_b0) eps_1/eps_2 (CT 86) for one-sign.

Design strengths (Rb, Rs incl. gamma_b, gamma_s) are used for ULS; no capacity reduction factor.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from scipy.optimize import brentq

import concreteproperties.results as res
import concreteproperties.stress_strain_profile as ssp
import concreteproperties.concrete_section as _ccs
from concreteproperties import utils
from concreteproperties.analysis_section import AnalysisSection as _AnalysisSection
from concreteproperties.design_codes.design_code import DesignCode
from concreteproperties.material import Concrete as CPConcrete
from concreteproperties.material import SteelBar
from concreteproperties.post import DEFAULT_UNITS, si_n_mm

from tcvn5574.constants import HumidityCondition
from tcvn5574.materials.concrete import get_concrete
from tcvn5574.materials.rebar import get_rebar

EPS_S_ULT = 0.025


class _NullSection:
    """Stand-in for a zero-area strain-split sliver: no contribution to N, Mx, My."""

    def ultimate_analysis(self, *args, **kwargs):
        return 0.0, 0.0, 0.0


class _SafeAnalysisSection(_AnalysisSection):
    """Skips degenerate (zero-area / collinear) split polygons.

    ponytail: concreteproperties sends them to the triangle mesher, which overflows the C stack and kills the
    process (skewed neutral axes through bar holes); used only inside TCVN5574.section_actions.
    """

    def __new__(cls, geometry):
        if geometry.geom.area <= 1e-9 or len(geometry.points) < 3:
            return _NullSection()
        return super().__new__(cls)

# Bảng 9: (eps_b0, eps_b2, eps_b1_red, eps_bt0, eps_bt2, eps_bt1_red); "short" = short-term loading
CONCRETE_STRAINS = {
    "short": (0.0020, 0.0035, 0.0015, 0.00010, 0.00015, 0.00008),
    HumidityCondition.HIGH: (0.0030, 0.0042, 0.0024, 0.00021, 0.00027, 0.00019),
    HumidityCondition.MEDIUM: (0.0034, 0.0048, 0.0028, 0.00024, 0.00031, 0.00022),
    HumidityCondition.LOW: (0.0040, 0.0056, 0.0034, 0.00028, 0.00036, 0.00026),
}


def _diagram(R: float, Rt: float, E: float, strains: tuple, three_linear: bool, tension: bool):
    """Piecewise points (compression positive) of the TCVN concrete diagram."""
    eb0, eb2, eb1r, ebt0, ebt2, ebt1r = strains
    if three_linear:
        comp = [(0.6 * R / E, 0.6 * R), (eb0, R), (eb2, R)]
        tens = [(0.6 * Rt / E, 0.6 * Rt), (ebt0, Rt), (ebt2, Rt)]
    else:
        comp = [(eb1r, R), (eb2, R)]
        tens = [(ebt1r, Rt), (ebt2, Rt)]
    if tension:
        pts = [(-1.0, 0.0), (-ebt2 * 1.0001, 0.0)] + [(-e, -s) for e, s in reversed(tens)]  # cracked beyond eps_bt2
    else:
        pts = [(-ebt2, 0.0)]
    pts += [(0.0, 0.0)] + comp
    return [p[0] for p in pts], [p[1] for p in pts]


class _FastLinear:
    """np.interp instead of building a scipy interp1d on every call (same piecewise-linear result).

    Strains outside the tabulated range take the end stress (all TCVN diagrams end on a plateau or at zero).
    """

    def get_stress(self, strain):
        return np.interp(strain, self.strains, self.stresses)


@dataclass
class TCVNConcreteService(_FastLinear, ssp.ConcreteServiceProfile):
    """Service-state TCVN concrete diagram (Rb,ser / Rbt,ser), with tension branch."""

    strains: list[float] = field(default_factory=list)
    stresses: list[float] = field(default_factory=list)
    ultimate_strain: float = 0.0035


@dataclass
class TCVNConcreteUltimate(_FastLinear, ssp.ConcreteUltimateProfile):
    """Ultimate TCVN concrete diagram (Rb), tension ignored."""

    strains: list[float] = field(default_factory=list)
    stresses: list[float] = field(default_factory=list)
    compressive_strength: float = 0.0
    ultimate_strain: float = 0.0035  # eps_b2
    eps_b0: float = 0.002  # strain at Rb, limit for uniform compression (CT 86)


@dataclass
class TCVNSteel(_FastLinear, ssp.SteelProfile):
    """Two-linear steel diagram with Rs (tension) and Rsc (compression)."""

    strains: list[float] = field(default_factory=list)
    stresses: list[float] = field(default_factory=list)
    yield_strength: float = 0.0
    elastic_modulus: float = 200000.0
    fracture_strain: float = EPS_S_ULT


class TCVN5574(DesignCode):
    """Design code class for TCVN 5574:2018 (lumped SteelBar reinforcement only)."""

    def __init__(self) -> None:
        super().__init__()

    def assign_concrete_section(self, concrete_section) -> None:
        self.concrete_section = concrete_section
        if concrete_section.reinf_geometries_meshed:
            raise ValueError("Meshed reinforcement is not supported in this design code.")
        if concrete_section.default_units is DEFAULT_UNITS:
            concrete_section.default_units = si_n_mm
            concrete_section.gross_properties.default_units = si_n_mm
        self.squash_load, self.tensile_load = self.squash_tensile_load()

    # ------------------------------------------------------------------ materials
    def create_concrete_material(  # pyright: ignore [reportIncompatibleMethodOverride]
        self,
        grade: str,
        gamma_b: float = 1.0,
        long_term: bool = False,
        humidity: HumidityCondition = HumidityCondition.MEDIUM,
        three_linear: bool = True,
        colour: str = "lightgrey",
    ) -> CPConcrete:
        """Concrete material from TCVN 5574:2018 tables.

        Ultimate profile uses gamma_b*Rb; service profile Rb,ser / Rbt,ser with tension.
        long_term: Eb,tau = Eb/(1 + phi_b,cr) and Bảng 9 strains for the humidity.
        flexural_tensile_strength = 1.3 Rbt,ser (Wpl = 1.3 Wred, CT 159) for the elastic cracking moment.
        """
        c = get_concrete(grade, gamma_b=gamma_b)
        strains = CONCRETE_STRAINS[HumidityCondition(humidity)] if long_term else CONCRETE_STRAINS["short"]
        E = c.Eb / (1.0 + c.get_creep_coefficient(humidity)) if long_term else c.Eb
        us, ust = _diagram(c.Rb_calc, c.Rbt_calc, E, strains, three_linear, tension=False)
        ss, sst = _diagram(c.Rb_ser, c.Rbt_ser, E, strains, three_linear, tension=True)
        return CPConcrete(
            name=f"{c.grade.value} (TCVN 5574:2018{', dài hạn' if long_term else ''})",
            density=2.5e-6,
            stress_strain_profile=TCVNConcreteService(strains=ss, stresses=sst, ultimate_strain=strains[1]),
            ultimate_stress_strain_profile=TCVNConcreteUltimate(
                strains=us, stresses=ust, compressive_strength=c.Rb_calc, ultimate_strain=strains[1], eps_b0=strains[0]
            ),
            flexural_tensile_strength=1.3 * c.Rbt_ser,
            colour=colour,
        )

    def create_steel_material(  # pyright: ignore [reportIncompatibleMethodOverride]
        self, grade: str = "CB400-V", gamma_s: float = 1.0, colour: str = "grey"
    ) -> SteelBar:
        r = get_rebar(grade, gamma_s=gamma_s)
        Rs, Rsc, Es = r.Rs_calc, r.Rsc_calc, r.Es
        return SteelBar(
            name=f"{r.grade.value} (TCVN 5574:2018)",
            density=7.85e-6,
            stress_strain_profile=TCVNSteel(
                strains=[-EPS_S_ULT, -Rs / Es, 0.0, Rsc / Es, EPS_S_ULT],
                stresses=[-Rs, -Rs, 0.0, Rsc, Rsc],
                yield_strength=Rs,
                elastic_modulus=Es,
                fracture_strain=EPS_S_ULT,
            ),
            colour=colour,
        )

    # ------------------------------------------------------------------ ULS
    def _eps_limits(self) -> tuple[float, float]:
        """(eps_b0, eps_b2) of the concrete (smallest over all concrete geometries)."""
        profs = [g.material.ultimate_stress_strain_profile for g in self.concrete_section.concrete_geometries]
        return min(getattr(p, "eps_b0", 0.002) for p in profs), min(p.get_ultimate_compressive_strain() for p in profs)

    def _depth(self, theta: float) -> float:
        return utils.calculate_extreme_fibre(points=self.concrete_section.compound_geometry.points, theta=theta)[1]

    def squash_tensile_load(self) -> tuple[float, float]:
        """N_c = sum(Rb A) + sum(sigma_s(eps_b0) As) (uniform strain eps_b0);  N_t = -sum(Rs As)."""
        cs = self.concrete_section
        eps_b0, _ = self._eps_limits()
        squash = tensile = 0.0
        for g in cs.concrete_geometries:
            squash += g.calculate_area() * float(g.material.ultimate_stress_strain_profile.get_stress(strain=eps_b0))
        for g in cs.reinf_geometries_lumped:
            p = g.material.stress_strain_profile
            squash += g.calculate_area() * float(p.get_stress(strain=eps_b0))
            tensile -= g.calculate_area() * p.get_yield_strength()
        return squash, tensile

    def limit_strain_state(self, d_n: float, theta: float = 0.0) -> tuple[float, str]:
        """Extreme compressive fibre strain eps_2 of the limit state for neutral axis depth d_n.

        - d_n > D (one-sign, whole section compressed): eps_1/eps_2 = (d_n - D)/d_n and CT (86)
          gives eps_2 = eps_b2 - (eps_b2 - eps_b0)(1 - D/d_n); d_n = inf -> eps_b0.
        - d_n <= D (two-sign): eps_2 = eps_b2 (CT 70), reduced so that the extreme bar strain
          eps_2 (d0 - d_n)/d_n does not exceed eps_s,u = 0.025 (CT 71).
        Returns (eps_2, governing) with governing in {"concrete", "steel", "one-sign"}.
        """
        cs = self.concrete_section
        eps_b0, eps_b2 = self._eps_limits()
        if math.isinf(d_n):
            return eps_b0, "one-sign"
        D = self._depth(theta)
        if d_n > D:
            return eps_b2 - (eps_b2 - eps_b0) * (1.0 - D / d_n), "one-sign"
        if cs.reinf_geometries_lumped:
            d0, _ = cs.extreme_bar(theta=theta)
            if d0 > d_n and eps_b2 * (d0 - d_n) / d_n > EPS_S_ULT:
                return EPS_S_ULT * d_n / (d0 - d_n), "steel"
        return eps_b2, "concrete"

    def section_actions(self, d_n: float, theta: float = 0.0) -> res.UltimateBendingResults:
        """N, Mx, My at the limit strain state for neutral axis depth d_n (see limit_strain_state).

        Result has extra attributes eps_b_max, eps_s_max (extreme bar, tension +) and governing.
        """
        cs = self.concrete_section
        gp = cs.gross_properties
        eps2, governing = self.limit_strain_state(d_n, theta)
        saved = gp.conc_ultimate_strain
        try:
            gp.conc_ultimate_strain = eps2
            _ccs.AnalysisSection = _SafeAnalysisSection
            r = cs.calculate_ultimate_section_actions(
                d_n=d_n, ultimate_results=res.UltimateBendingResults(default_units=cs.default_units, theta=theta)
            )
        finally:
            _ccs.AnalysisSection = _AnalysisSection
            gp.conc_ultimate_strain = saved
        d0 = cs.extreme_bar(theta=theta)[0] if cs.reinf_geometries_lumped else 0.0
        r.eps_b_max = eps2
        r.eps_s_max = -eps2 if math.isinf(d_n) else eps2 * (d0 - d_n) / d_n
        r.governing = governing
        return r

    def ultimate_bending_capacity(  # pyright: ignore [reportIncompatibleMethodOverride]
        self, theta: float = 0.0, n: float = 0.0
    ) -> res.UltimateBendingResults:
        """Ultimate moment for axial force n (compression +, N) per 8.1.2.7.

        Solves N(d_n) = n over the limit strain states of limit_strain_state(). Result has attributes
        eps_b_max, eps_s_max and governing ("concrete" / "steel" / "one-sign").
        """
        if not self.tensile_load < n < self.squash_load:
            raise ValueError(f"n = {n:.4g} N outside ({self.tensile_load:.4g}, {self.squash_load:.4g})")
        D = self._depth(theta)

        def f(d_n):
            return self.section_actions(d_n, theta).n - n

        lo, hi = 1e-6 * D, D
        while f(hi) < 0:  # N(d_n) increases with d_n and tends to the squash load
            lo, hi = hi, hi * 4.0
        d_n = brentq(f, lo, hi, xtol=1e-7 * D, rtol=1e-12)
        return self.section_actions(d_n, theta)

    def _end_point(self, theta: float, compression: bool) -> res.UltimateBendingResults:
        """Squash (uniform eps_b0) or pure-tension (all bars at -Rs) point with its moment about the centroid."""
        cs = self.concrete_section
        if compression:
            r = self.section_actions(math.inf, theta)
            r.n = self.squash_load
            return r
        cx, cy = cs.moment_centroid
        m_x = m_y = 0.0
        for g in cs.reinf_geometries_lumped:
            f = -g.calculate_area() * g.material.stress_strain_profile.get_yield_strength()
            x, y = g.calculate_centroid()
            m_x += f * (y - cy)
            m_y += f * (x - cx)
        return res.UltimateBendingResults(
            default_units=cs.default_units, theta=theta, d_n=0, k_u=0, n=self.tensile_load, m_x=m_x, m_y=m_y, m_xy=math.hypot(m_x, m_y)
        )

    def moment_interaction_diagram(  # pyright: ignore [reportIncompatibleMethodOverride]
        self, theta: float = 0.0, n_points: int = 24
    ) -> res.MomentInteractionResults:
        """M-N diagram for neutral-axis angle theta with TCVN limit strain states (incl. CT 86), decreasing N.

        n_points axial forces equally spaced strictly between squash and tensile loads, plus both end points
        (with their true moments about the section centroid, non-zero for unsymmetric sections).
        theta = 0: top face compressed (m_x >= 0 branch); theta = pi: bottom face compressed.
        """
        mi = res.MomentInteractionResults(default_units=self.concrete_section.default_units)
        mi.results.append(self._end_point(theta, True))
        for n in np.linspace(self.squash_load, self.tensile_load, n_points + 2)[1:-1]:
            mi.results.append(self.ultimate_bending_capacity(theta=theta, n=float(n)))
        mi.results.append(self._end_point(theta, False))
        return mi

    def check_point(self, n: float, m_x: float, n_points: int = 24) -> tuple[bool, float, float]:
        """Is (n, m_x) inside the M-N envelope? Returns (ok, Mu_neg(n), Mu_pos(n)) in N.mm.

        Uses the theta = 0 and theta = pi branches: Mu_neg <= m_x <= Mu_pos.
        """
        if not self.tensile_load < n < self.squash_load:
            return False, 0.0, 0.0
        mu_pos = self.ultimate_bending_capacity(theta=0.0, n=n).m_x
        mu_neg = self.ultimate_bending_capacity(theta=math.pi, n=n).m_x
        return mu_neg <= m_x <= mu_pos, mu_neg, mu_pos

    def biaxial_check(self, n: float, m_x: float, m_y: float) -> tuple[bool, float, float, float]:
        """Biaxial check at axial force n: capacity along the direction of the applied moment (m_x, m_y).

        Finds the neutral-axis angle theta whose ultimate moment vector is parallel to (m_x, m_y) and returns
        (ok, Mu (N.mm, resultant), utilization |M|/Mu, theta).
        """
        target = math.atan2(m_y, m_x)
        M = math.hypot(m_x, m_y)
        if not self.tensile_load < n < self.squash_load:
            return False, 0.0, math.inf, 0.0
        if M == 0:
            return True, math.inf, 0.0, 0.0

        def diff(theta):
            r = self.ultimate_bending_capacity(theta=theta, n=n)
            d = math.atan2(r.m_y, r.m_x) - target
            return (d + math.pi) % (2 * math.pi) - math.pi

        # theta = 0 -> +m_x, theta = -pi/2 -> +m_y, i.e. moment angle ~ -theta: diff decreases with theta
        t0 = -target
        step = math.pi / 24
        a, fa = t0, diff(t0)
        theta = t0
        if abs(fa) > 1e-9:
            for k in range(1, 25):
                b = t0 + step * k * math.copysign(1.0, fa)
                fb = diff(b)
                if fa * fb <= 0:
                    theta = brentq(diff, min(a, b), max(a, b), xtol=1e-7)
                    break
                a, fa = b, fb
            else:
                raise RuntimeError("biaxial_check: no neutral-axis angle found for the moment direction")
        r = self.ultimate_bending_capacity(theta=theta, n=n)
        Mu = math.hypot(r.m_x, r.m_y)
        return M <= Mu * (1 + 1e-9), Mu, M / Mu, theta

    def biaxial_bending_diagram(  # pyright: ignore [reportIncompatibleMethodOverride]
        self, n: float = 0.0, n_points: int = 48
    ) -> res.BiaxialBendingResults:
        bb = res.BiaxialBendingResults(default_units=self.concrete_section.default_units, n=n)
        d = 2 * np.pi / n_points
        for th in np.linspace(-np.pi, np.pi - d, n_points):
            bb.results.append(self.ultimate_bending_capacity(theta=th, n=n))
        bb.results.append(bb.results[0])
        return bb
