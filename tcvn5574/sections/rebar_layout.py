"""Rebar layout and layer geometric computations."""

from dataclasses import dataclass, field
from typing import List
from tcvn5574.materials.rebar import bar_area


@dataclass
class RebarLayer:
    """A single layer of rebar.

    Attributes:
        n_bars: Number of bars in this layer
        diameter: Diameter of bars in mm
        distance_from_edge: Distance from the external surface (bottom or top)
                           to the center of this rebar layer in mm
    """

    n_bars: int
    diameter: float
    distance_from_edge: float

    @property
    def area(self) -> float:
        """Total area of bars in this layer in mm²."""
        return self.n_bars * bar_area(self.diameter)


@dataclass
class RebarGroup:
    """A group of rebar layers (e.g. all tensile or all compressive bars)."""

    layers: List[RebarLayer] = field(default_factory=list)

    def add_layer(self, n_bars: int, diameter: float, distance_from_edge: float) -> "RebarGroup":
        if n_bars > 0 and diameter > 0:
            self.layers.append(RebarLayer(n_bars, diameter, distance_from_edge))
        return self

    @property
    def total_area(self) -> float:
        """Total cross-sectional area of rebar in mm²."""
        return sum(layer.area for layer in self.layers)

    @property
    def total_area_cm2(self) -> float:
        """Total cross-sectional area of rebar in cm²."""
        return self.total_area / 100.0

    @property
    def centroid_distance(self) -> float:
        """Distance from the reference edge to the centroid of the rebar group in mm."""
        a_tot = self.total_area
        if a_tot <= 0.0:
            return 0.0
        return sum(layer.area * layer.distance_from_edge for layer in self.layers) / a_tot

    @property
    def effective_diameter(self) -> float:
        """Area-weighted equivalent bar diameter in mm."""
        a_tot = self.total_area
        if a_tot <= 0.0:
            return 0.0
        return sum(layer.area * layer.diameter for layer in self.layers) / a_tot

    @property
    def nominal_diameter(self) -> float:
        """ds for crack spacing with mixed diameters: sum(n d^2) / sum(n d).

        TCVN 5574:2018 8.2.2.3.3 only says "nominal diameter"; this weighting follows
        SP 63.13330.2018 (8.2.17). Equals d for a single diameter.
        """
        s1 = sum(l.n_bars * l.diameter for l in self.layers)
        return sum(l.n_bars * l.diameter**2 for l in self.layers) / s1 if s1 > 0 else 0.0

    @property
    def total_bars(self) -> int:
        """Total number of bars."""
        return sum(layer.n_bars for layer in self.layers)

    @classmethod
    def from_simple(cls, n_bars: int, diameter: float, a_dist: float) -> "RebarGroup":
        """Create a single-layer group."""
        group = cls()
        group.add_layer(n_bars, diameter, a_dist)
        return group
