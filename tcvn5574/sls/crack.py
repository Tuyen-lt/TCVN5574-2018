"""Crack formation and crack width of flexural members per TCVN 5574:2018 (Điều 8.2.2)."""

import math
from dataclasses import dataclass
from typing import Optional

from tcvn5574.constants import CRACK_LIMITS, CrackRequirement, RebarType
from tcvn5574.materials.concrete import Concrete
from tcvn5574.materials.rebar import Rebar
from tcvn5574.sections.rectangular import RectangularBeamSection

EPS_B1_RED_SHORT = 0.0015  # CT (169)


@dataclass
class CrackWidthDetail:
    """All intermediate values of one crack width a_crc,i (CT 166-176)."""

    M_kNm: float
    phi1: float
    phi2: float
    phi3: float
    Eb_red: float  # Rb,ser / 0.0015 (CT 169)
    alpha_s1: float  # Es / Eb,red (CT 168)
    x_mm: float  # compression zone of the cracked section (CT 196/197, alpha_s2 = alpha_s1)
    Ired_mm4: float  # CT (193) with alpha_s2 = alpha_s1
    sigma_s_calc: float  # M (h0 - x) alpha_s1 / Ired (CT 167)
    sigma_s: float  # min(sigma_s_calc, Rs,ser)
    yt_mm: float  # tension zone height used for Abt, within [2a, 0.5h]
    Abt_mm2: float
    ds_mm: float
    Ls_calc_mm: float  # 0.5 Abt/As ds (CT 174)
    Ls_mm: float  # limited to [max(10ds,100), min(40ds,400)]
    psi_s: float  # 1 - 0.8 Mcrc/M (CT 176)
    acrc_mm: float


@dataclass
class CrackCheckResult:
    """Result of crack width verification per TCVN 5574:2018."""

    M_short_kNm: float  # total service moment (permanent + all variable loads)
    M_long_kNm: float  # permanent + long-term variable service loads
    Mcrc_kNm: float  # CT (158)
    Wpl_mm3: float
    gamma: float
    is_cracked: bool

    acrc1_mm: float  # long-term action of long-term loads (phi1 = 1.4)
    acrc2_mm: float  # short-term action of all loads (phi1 = 1.0)
    acrc3_mm: float  # short-term action of long-term loads (phi1 = 1.0)
    detail1: Optional[CrackWidthDetail]
    detail2: Optional[CrackWidthDetail]
    detail3: Optional[CrackWidthDetail]

    acrc_short_mm: float  # acrc1 + acrc2 - acrc3 (CT 157)
    acrc_long_mm: float  # acrc1 (CT 156)
    acrc_short_allowable_mm: float
    acrc_long_allowable_mm: float

    is_short_term_safe: bool
    is_long_term_safe: bool
    is_safe: bool


def cracking_moment(section: RectangularBeamSection, concrete: Concrete, rebar: Rebar) -> float:
    """Mcrc = Rbt,ser * Wpl, Wpl = gamma Wred, alpha = Es/Eb (CT 158-164), N.mm."""
    return concrete.Rbt_ser * section.get_transformed_properties(rebar.Es / concrete.Eb)["Wpl"]


def cracked_section(section: RectangularBeamSection, alpha_s1: float, alpha_s2: float):
    """Neutral axis x_m (CT 195-197) and Ired = Ib + alpha_s2 Is + alpha_s1 I's (CT 193) of the
    cracked section, tension concrete ignored. Returns (x_m, Ired) in mm, mm^4."""
    b, h0, a_p = section.b, section.h0, section.a_prime
    As, Asc = section.As, section.Asc
    bf, hf = (section.bf, section.hf) if section.has_compression_flange else (b, 0.0)

    def x_of(width, Af):
        mu, mu_c, mu_f = As / (width * h0), Asc / (width * h0), Af / (width * h0)
        k = mu * alpha_s2 + mu_c * alpha_s1 + mu_f
        return h0 * (math.sqrt(k**2 + 2.0 * (mu * alpha_s2 + mu_c * alpha_s1 * a_p / h0 + mu_f * hf / (2.0 * h0))) - k)

    x = x_of(bf, 0.0)  # neutral axis inside the flange: rectangle of width bf
    if hf > 0 and bf > b and x > hf:
        x = x_of(b, (bf - b) * hf)  # CT (197)
        Ib = b * x**3 / 3.0 + (bf - b) * hf**3 / 12.0 + (bf - b) * hf * (x - hf / 2.0) ** 2
    else:
        Ib = bf * x**3 / 3.0
    Ired = Ib + alpha_s2 * As * (h0 - x) ** 2 + alpha_s1 * Asc * (x - a_p) ** 2
    return x, Ired


def crack_width(
    M_Nmm: float,
    phi1: float,
    section: RectangularBeamSection,
    concrete: Concrete,
    rebar: Rebar,
    Mcrc_Nmm: float,
) -> Optional[CrackWidthDetail]:
    """a_crc,i = phi1 phi2 phi3 psi_s sigma_s/Es Ls (CT 166). None if M <= Mcrc (no crack)."""
    As = section.As
    if M_Nmm <= Mcrc_Nmm or As <= 0:
        return None
    Es = rebar.Es

    # 8.2.2.3.2: sigma_s with alpha_s2 = alpha_s1, eps_b1,red = 0.0015, sigma_s <= Rs,ser
    Eb_red = concrete.Rb_ser / EPS_B1_RED_SHORT
    alpha_s1 = Es / Eb_red
    x, Ired = cracked_section(section, alpha_s1, alpha_s1)
    sigma_calc = M_Nmm * (section.h0 - x) / Ired * alpha_s1
    sigma_s = min(sigma_calc, rebar.Rs_ser) if rebar.Rs_ser > 0 else sigma_calc

    # 8.2.2.3.3: Abt over the tension zone height yt of the uncracked section (CT 164), in [2a, 0.5h]
    yt = section.get_transformed_properties(Es / concrete.Eb)["yt"]
    yt = min(max(yt, 2.0 * section.a), 0.5 * section.h)
    Abt = section.tension_concrete_area(yt)
    ds = section.tensile_rebar.nominal_diameter
    Ls_calc = 0.5 * Abt / As * ds
    Ls = min(max(Ls_calc, 10.0 * ds, 100.0), 40.0 * ds, 400.0)

    psi_s = 1.0 - 0.8 * Mcrc_Nmm / M_Nmm  # CT (176), < 1 because M > Mcrc
    phi2 = 0.8 if rebar.rebar_type == RebarType.PLAIN else 0.5
    phi3 = 1.0  # flexural members
    acrc = phi1 * phi2 * phi3 * psi_s * sigma_s / Es * Ls

    return CrackWidthDetail(
        M_kNm=M_Nmm / 1e6, phi1=phi1, phi2=phi2, phi3=phi3, Eb_red=Eb_red, alpha_s1=alpha_s1,
        x_mm=x, Ired_mm4=Ired, sigma_s_calc=sigma_calc, sigma_s=sigma_s, yt_mm=yt, Abt_mm2=Abt,
        ds_mm=ds, Ls_calc_mm=Ls_calc, Ls_mm=Ls, psi_s=psi_s, acrc_mm=acrc,
    )


def check_beam_cracking(
    M_short_kNm: float,
    M_long_kNm: float,
    section: RectangularBeamSection,
    concrete: Concrete,
    rebar: Rebar,
    requirement: CrackRequirement = CrackRequirement.INTEGRITY,
    acrc_short_allowable_mm: float = None,
    acrc_long_allowable_mm: float = None,
) -> CrackCheckResult:
    """Check crack width per TCVN 5574:2018 (8.2.2.1.3-8.2.2.3).

    M_short_kNm: moment from all service loads; M_long_kNm: permanent + long-term variable part.
    Limits from Bảng 17 by `requirement` unless given explicitly.
    """
    if M_short_kNm < 0.0 or M_long_kNm < 0.0:
        raise ValueError("service moments must be non-negative magnitudes")
    if M_long_kNm > M_short_kNm + 1e-12:
        raise ValueError(
            "M_long_kNm must be the long-term component of M_short_kNm "
            "and therefore cannot exceed it"
        )
    lim_short, lim_long = CRACK_LIMITS[CrackRequirement(requirement)]
    lim_short = acrc_short_allowable_mm if acrc_short_allowable_mm is not None else lim_short
    lim_long = acrc_long_allowable_mm if acrc_long_allowable_mm is not None else lim_long

    M_s, M_l = M_short_kNm * 1e6, M_long_kNm * 1e6
    props = section.get_transformed_properties(rebar.Es / concrete.Eb)
    Mcrc = concrete.Rbt_ser * props["Wpl"]

    d1 = crack_width(M_l, 1.4, section, concrete, rebar, Mcrc)
    d2 = crack_width(M_s, 1.0, section, concrete, rebar, Mcrc)
    d3 = crack_width(M_l, 1.0, section, concrete, rebar, Mcrc)
    a1, a2, a3 = (d.acrc_mm if d else 0.0 for d in (d1, d2, d3))
    acrc_short = a1 + a2 - a3
    short_ok = acrc_short <= lim_short + 1e-6
    long_ok = a1 <= lim_long + 1e-6

    return CrackCheckResult(
        M_short_kNm=M_short_kNm,
        M_long_kNm=M_long_kNm,
        Mcrc_kNm=round(Mcrc / 1e6, 2),
        Wpl_mm3=props["Wpl"],
        gamma=props["gamma"],
        is_cracked=max(M_s, M_l) > Mcrc,
        acrc1_mm=round(a1, 3),
        acrc2_mm=round(a2, 3),
        acrc3_mm=round(a3, 3),
        detail1=d1,
        detail2=d2,
        detail3=d3,
        acrc_short_mm=round(acrc_short, 3),
        acrc_long_mm=round(a1, 3),
        acrc_short_allowable_mm=lim_short,
        acrc_long_allowable_mm=lim_long,
        is_short_term_safe=short_ok,
        is_long_term_safe=long_ok,
        is_safe=short_ok and long_ok,
    )
