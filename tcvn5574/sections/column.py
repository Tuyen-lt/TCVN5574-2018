"""Rectangular column section with bars at arbitrary positions (bars around the perimeter)."""

import math
from dataclasses import dataclass, field
from typing import List, Tuple

from tcvn5574.materials.rebar import bar_area
from tcvn5574.sections.rebar_layout import RebarGroup
from tcvn5574.sections.rectangular import RectangularBeamSection


@dataclass
class RectangularColumnSection:
    """b (along x) by h (along y), origin at the bottom-left corner; bars = [(x, y, diameter)] in mm.

    Mx bends in the plane of h (about the x axis), My in the plane of b.
    """

    b: float
    h: float
    bars: List[Tuple[float, float, float]] = field(default_factory=list)

    @classmethod
    def perimeter(cls, b: float, h: float, a: float, n_b: int, n_h: int, d: float, d_corner: float = None):
        """Bars on the four faces: n_b per face along b and n_h per face along h (both counts include
        the corners), centres at distance a from the faces. d_corner defaults to d."""
        dc = d_corner or d
        pts = {}
        for i in range(n_b):
            x = a + (b - 2 * a) * i / (n_b - 1)
            pts[(round(x, 6), a)] = pts[(round(x, 6), h - a)] = d
        for j in range(n_h):
            y = a + (h - 2 * a) * j / (n_h - 1)
            pts[(a, round(y, 6))] = pts[(b - a, round(y, 6))] = d
        for c in ((a, a), (b - a, a), (a, h - a), (b - a, h - a)):
            pts[(round(c[0], 6), round(c[1], 6))] = dc
        return cls(b, h, [(x, y, dd) for (x, y), dd in pts.items()])

    @property
    def As_total(self) -> float:
        return sum(bar_area(d) for _, _, d in self.bars)

    @property
    def mu_total_percent(self) -> float:
        return self.As_total / (self.b * self.h) * 100.0

    def Is(self, axis: str) -> float:
        """Moment of inertia of all bars about the centroid: axis 'x' (Mx) or 'y' (My)."""
        if axis == "x":
            return sum(bar_area(d) * (y - self.h / 2) ** 2 for _, y, d in self.bars)
        return sum(bar_area(d) * (x - self.b / 2) ** 2 for x, _, d in self.bars)

    def uniaxial(self, axis: str, positive: bool = True) -> RectangularBeamSection:
        """Plane section for bending about `axis`: width b and depth h for 'x', width h and depth b for 'y'.

        Only the two outer bar rows parallel to the neutral axis count as As / A's (intermediate side bars
        are ignored, conservative). positive=True: the row at the low coordinate is in tension.
        """
        if axis == "x":
            width, depth, coord = self.b, self.h, [(y, d) for _, y, d in self.bars]
        else:
            width, depth, coord = self.h, self.b, [(x, d) for x, _, d in self.bars]
        lo = min(c for c, _ in coord)
        hi = max(c for c, _ in coord)
        low = [d for c, d in coord if math.isclose(c, lo)]
        high = [d for c, d in coord if math.isclose(c, hi)]
        g_low, g_high = RebarGroup(), RebarGroup()
        for d in low:
            g_low.add_layer(1, d, lo)
        for d in high:
            g_high.add_layer(1, d, depth - hi)
        t, c = (g_low, g_high) if positive else (g_high, g_low)
        return RectangularBeamSection(width, depth, tensile_rebar=t, comp_rebar=c)
