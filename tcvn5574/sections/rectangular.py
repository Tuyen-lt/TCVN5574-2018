"""Beam section geometry and transformed section properties."""

import math
from dataclasses import dataclass
from typing import Optional

from tcvn5574.sections.rebar_layout import RebarGroup


@dataclass
class RectangularBeamSection:
    """Rectangular or T-shaped reinforced concrete beam section.

    All dimensions are in millimeters (mm).

    Attributes:
        b: Web width in mm (bề rộng dầm)
        h: Total height in mm (chiều cao dầm)
        bf: Flange width in mm (bề rộng cánh, default = b)
        hf: Flange thickness in mm (chiều dày cánh, default = 0)
        flange_in_tension: True when the flange is on the tension side (e.g. continuous beam
            with slab at the support, tensile_rebar = top bars). The flange is then ignored in
            strength and cracked-section calculations but included in Mcrc and Abt.
        tensile_rebar: RebarGroup for tensile reinforcement (cốt thép chịu kéo)
        comp_rebar: RebarGroup for compressive reinforcement (cốt thép chịu nén)
    """

    b: float
    h: float
    bf: Optional[float] = None
    hf: float = 0.0
    tensile_rebar: Optional[RebarGroup] = None
    comp_rebar: Optional[RebarGroup] = None
    flange_in_tension: bool = False

    @property
    def has_flange(self) -> bool:
        return self.hf > 0 and self.bf > self.b

    @property
    def has_compression_flange(self) -> bool:
        return self.has_flange and not self.flange_in_tension

    def __post_init__(self):
        if self.bf is None or self.bf < self.b:
            self.bf = self.b
        if self.hf <= 0.0 or self.bf == self.b:
            self.hf = 0.0
            self.bf = self.b

    @property
    def gross_area(self) -> float:
        """Gross concrete area Ac in mm²."""
        if self.hf > 0 and self.bf > self.b:
            return self.b * self.h + (self.bf - self.b) * self.hf
        return self.b * self.h

    @property
    def As(self) -> float:
        """Tensile rebar area in mm²."""
        return self.tensile_rebar.total_area if self.tensile_rebar else 0.0

    @property
    def As_cm2(self) -> float:
        """Tensile rebar area in cm²."""
        return self.As / 100.0

    @property
    def Asc(self) -> float:
        """Compressive rebar area in mm²."""
        return self.comp_rebar.total_area if self.comp_rebar else 0.0

    @property
    def Asc_cm2(self) -> float:
        """Compressive rebar area in cm²."""
        return self.Asc / 100.0

    @property
    def a(self) -> float:
        """Distance from tensile edge to centroid of tensile rebar in mm."""
        return self.tensile_rebar.centroid_distance if self.tensile_rebar else 0.0

    @property
    def a_prime(self) -> float:
        """Distance from compressive edge to centroid of compressive rebar in mm."""
        return self.comp_rebar.centroid_distance if self.comp_rebar else 0.0

    @property
    def h0(self) -> float:
        """Effective depth h0 = h - a in mm."""
        return max(0.0, self.h - self.a)

    @property
    def h0_cm(self) -> float:
        """Effective depth in cm."""
        return self.h0 / 10.0

    @property
    def mu_percent(self) -> float:
        """Tensile reinforcement ratio: mu = As / (b * h0) * 100%."""
        if self.b > 0 and self.h0 > 0:
            return (self.As / (self.b * self.h0)) * 100.0
        return 0.0

    @property
    def mu_c_percent(self) -> float:
        """Compressive reinforcement ratio: mu' = Asc / (b * h0) * 100%."""
        if self.b > 0 and self.h0 > 0:
            return (self.Asc / (self.b * self.h0)) * 100.0
        return 0.0

    def get_transformed_properties(self, alpha: float) -> dict:
        """Calculate transformed (reduced / tính đổi) section properties.

        Args:
            alpha: Modular ratio alpha = Es / Eb (or Es / Eb1)

        Returns:
            dict containing:
                Ared: Transformed area (mm²)
                Sred: Static moment about top (compressive) edge (mm³)
                x0: Distance from top edge to centroid of transformed section (mm)
                Ired: Moment of inertia of transformed section about neutral axis (mm⁴)
                Wred: Elastic resistance moment for tension edge: Ired / (h - x0) (mm³)
                Wpl: Wpl = 1.3 * Wred (TCVN 5574:2018 CT 159) (mm³)
                yt: Distance from tension edge to centroid (mm)
        """
        # Flange overhang (bf - b) * hf, at the compressed or the tensioned edge
        flange_area = (self.bf - self.b) * self.hf if self.has_flange else 0.0
        yf = self.h - self.hf / 2.0 if self.flange_in_tension else self.hf / 2.0
        web_area = self.b * self.h

        # Transformed area: Ared = A + alpha * As + alpha * A's (CT 163)
        As_tot = self.As
        Asc_tot = self.Asc
        Ared = web_area + flange_area + alpha * (As_tot + Asc_tot)

        # Static moment about the compressive edge
        Sred = web_area * self.h / 2.0 + flange_area * yf + alpha * As_tot * (self.h - self.a) + alpha * Asc_tot * self.a_prime
        x0 = Sred / Ared if Ared > 0 else self.h / 2.0

        # Moment of inertia about the centroidal axis x0
        I_web = (self.b * self.h**3) / 12.0 + web_area * (self.h / 2.0 - x0) ** 2
        I_flange = (self.bf - self.b) * self.hf**3 / 12.0 + flange_area * (yf - x0) ** 2 if flange_area > 0 else 0.0
        # Rebars:
        I_rebar_t = alpha * As_tot * (self.h - self.a - x0) ** 2
        I_rebar_c = alpha * Asc_tot * (x0 - self.a_prime) ** 2

        Ired = I_web + I_flange + I_rebar_t + I_rebar_c

        # Tension edge distance and elastic modulus Wred = Ired / yt (CT 160)
        y_t = max(1.0, self.h - x0)
        Wred = Ired / y_t

        # CT (159): Wpl = gamma * Wred; gamma = 1.3 for rectangular and T with flange in compression,
        # Phụ lục L Bảng L.1 item 3 for T with flange in tension
        gamma = 1.3
        if self.has_flange and self.flange_in_tension:
            gamma = 1.20 if (self.bf / self.b > 2.0 and self.hf / self.h < 0.2) else 1.25
        Wpl = gamma * Wred

        return {
            "Ared": Ared,
            "Sred": Sred,
            "x0": x0,
            "Ired": Ired,
            "Wred": Wred,
            "Wpl": Wpl,
            "gamma": gamma,
            "yt": y_t,
        }

    def tension_concrete_area(self, height: float) -> float:
        """Concrete area within `height` from the tension edge (for Abt, 8.2.2.3.3)."""
        if self.has_flange and self.flange_in_tension:
            return self.bf * min(height, self.hf) + self.b * max(0.0, height - self.hf)
        return self.b * height
