"""Geometry and fiber discretization for RC shear and core walls per TCVN 5574:2018.

Supports single rectangular walls, flanged I/T/L walls, core elevator walls (C/U shape),
and arbitrary combinations of rectangular wall segments and longitudinal rebars.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional, Tuple


@dataclass
class WallFiber:
    """A discretized 2D fiber element representing concrete or rebar."""

    x: float  # mm, centroid X in section coordinate system
    y: float  # mm, centroid Y in section coordinate system
    area: float  # mm^2, fiber cross-sectional area
    material_type: str  # "concrete" or "rebar"
    diameter: float = 0.0  # mm, bar diameter (if rebar)


@dataclass
class WallSegment:
    """A rectangular wall leg/segment.

    Defined in local coordinates with width/thickness `thickness` along local y'
    and length `length` along local x', rotated by `angle_deg` relative to global X.
    """

    x0: float  # mm, origin X
    y0: float  # mm, origin Y
    length: float  # mm, length of segment along local x'
    thickness: float  # mm, thickness of segment along local y'
    angle_deg: float = 0.0  # degrees, counter-clockwise angle from global X

    def __post_init__(self) -> None:
        if self.length <= 0.0 or self.thickness <= 0.0:
            raise ValueError("wall segment length and thickness must be positive")

    @property
    def area(self) -> float:
        """Concrete area of the segment, mm^2."""
        return self.length * self.thickness

    @property
    def angle_rad(self) -> float:
        """Angle in radians."""
        return math.radians(self.angle_deg)

    def centroid(self) -> Tuple[float, float]:
        """Centroid (Xc, Yc) of the segment in global coordinates."""
        lx_mid = self.length / 2.0
        ly_mid = self.thickness / 2.0
        cos_a = math.cos(self.angle_rad)
        sin_a = math.sin(self.angle_rad)
        xc = self.x0 + lx_mid * cos_a - ly_mid * sin_a
        yc = self.y0 + lx_mid * sin_a + ly_mid * cos_a
        return xc, yc

    def discretize(
        self, max_dx: float = 25.0, max_dy: float = 25.0
    ) -> List[WallFiber]:
        """Subdivide this segment into a regular grid of concrete fibers."""
        nx = max(1, math.ceil(self.length / max_dx))
        ny = max(1, math.ceil(self.thickness / max_dy))
        dx = self.length / nx
        dy = self.thickness / ny
        fiber_area = dx * dy

        cos_a = math.cos(self.angle_rad)
        sin_a = math.sin(self.angle_rad)

        fibers: List[WallFiber] = []
        for i in range(nx):
            x_loc = (i + 0.5) * dx
            for j in range(ny):
                y_loc = (j + 0.5) * dy
                # Transform local (x_loc, y_loc) to global (X, Y)
                x_glob = self.x0 + x_loc * cos_a - y_loc * sin_a
                y_glob = self.y0 + x_loc * sin_a + y_loc * cos_a
                fibers.append(
                    WallFiber(
                        x=x_glob,
                        y=y_glob,
                        area=fiber_area,
                        material_type="concrete",
                    )
                )
        return fibers


@dataclass
class WallRebar:
    """Longitudinal reinforcement bar."""

    x: float  # mm, global X coordinate
    y: float  # mm, global Y coordinate
    diameter: float  # mm
    area: Optional[float] = None  # mm^2, calculated from diameter if None

    def __post_init__(self) -> None:
        if self.diameter <= 0.0:
            raise ValueError("rebar diameter must be positive")
        if self.area is not None and self.area < 0.0:
            raise ValueError("rebar area must be positive")
        if self.area is None or self.area <= 0.0:
            self.area = math.pi * (self.diameter**2) / 4.0

    def to_fiber(self) -> WallFiber:
        return WallFiber(
            x=self.x,
            y=self.y,
            area=self.area or 0.0,
            material_type="rebar",
            diameter=self.diameter,
        )


@dataclass
class WallSection:
    """Reinforced concrete shear wall or core wall section.

    Consists of concrete segments and longitudinal rebar bars.
    """

    segments: List[WallSegment] = field(default_factory=list)
    rebars: List[WallRebar] = field(default_factory=list)

    @property
    def total_concrete_area(self) -> float:
        """Total cross-sectional concrete area, mm^2."""
        return sum(s.area for s in self.segments)

    @property
    def total_rebar_area(self) -> float:
        """Total cross-sectional rebar area, mm^2."""
        return sum(r.area or 0.0 for r in self.rebars)

    @property
    def rebar_ratio(self) -> float:
        """Reinforcement ratio rho = As / Ac."""
        ac = self.total_concrete_area
        return (self.total_rebar_area / ac) if ac > 0 else 0.0

    def calculate_concrete_properties(
        self,
    ) -> Tuple[float, float, float, float, float, float, float, float]:
        """Compute gross concrete section properties.

        Returns:
            (Ac, Xc, Yc, Ix, Iy, Ixy, ix, iy)
            where Ix, Iy, Ixy are with respect to the centroid (Xc, Yc).
        """
        ac_total = self.total_concrete_area
        if ac_total <= 0.0:
            return 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0

        # Centroid
        sum_a_x = 0.0
        sum_a_y = 0.0
        for seg in self.segments:
            xc, yc = seg.centroid()
            a = seg.area
            sum_a_x += a * xc
            sum_a_y += a * yc

        xc_total = sum_a_x / ac_total
        yc_total = sum_a_y / ac_total

        # Moments of inertia about centroidal axes
        ix_total = 0.0
        iy_total = 0.0
        ixy_total = 0.0

        for seg in self.segments:
            l = seg.length
            t = seg.thickness
            a = seg.area
            cos_a = math.cos(seg.angle_rad)
            sin_a = math.sin(seg.angle_rad)

            # Local moments of inertia (x' along length, y' along thickness)
            # Ix' = l * t^3 / 12, Iy' = t * l^3 / 12
            ix_prime = (l * (t**3)) / 12.0
            iy_prime = (t * (l**3)) / 12.0

            # Rotation to global axes
            ix_local_rot = ix_prime * (cos_a**2) + iy_prime * (sin_a**2)
            iy_local_rot = ix_prime * (sin_a**2) + iy_prime * (cos_a**2)
            ixy_local_rot = (iy_prime - ix_prime) * sin_a * cos_a

            # Parallel axis theorem
            xc_s, yc_s = seg.centroid()
            dx = xc_s - xc_total
            dy = yc_s - yc_total

            ix_total += ix_local_rot + a * (dy**2)
            iy_total += iy_local_rot + a * (dx**2)
            ixy_total += ixy_local_rot + a * dx * dy

        ix_rad = math.sqrt(ix_total / ac_total) if ix_total > 0 else 0.0
        iy_rad = math.sqrt(iy_total / ac_total) if iy_total > 0 else 0.0

        return (
            ac_total,
            xc_total,
            yc_total,
            ix_total,
            iy_total,
            ixy_total,
            ix_rad,
            iy_rad,
        )

    def calculate_rebar_inertia(
        self, xc: float = 0.0, yc: float = 0.0
    ) -> Tuple[float, float]:
        """Compute rebar moments of inertia Is_x, Is_y about given point (default 0,0)."""
        is_x = 0.0
        is_y = 0.0
        for r in self.rebars:
            a = r.area or 0.0
            dy = r.y - yc
            dx = r.x - xc
            is_x += a * (dy**2)
            is_y += a * (dx**2)
        return is_x, is_y

    def shifted_to_centroid(self) -> WallSection:
        """Return a new WallSection shifted so that concrete centroid is at (0, 0)."""
        _, xc, yc, _, _, _, _, _ = self.calculate_concrete_properties()
        new_segments = [
            WallSegment(
                x0=seg.x0 - xc,
                y0=seg.y0 - yc,
                length=seg.length,
                thickness=seg.thickness,
                angle_deg=seg.angle_deg,
            )
            for seg in self.segments
        ]
        new_rebars = [
            WallRebar(
                x=r.x - xc,
                y=r.y - yc,
                diameter=r.diameter,
                area=r.area,
            )
            for r in self.rebars
        ]
        return WallSection(segments=new_segments, rebars=new_rebars)

    def discretize_fibers(
        self, max_dx: float = 25.0, max_dy: float = 25.0
    ) -> Tuple[List[WallFiber], List[WallFiber]]:
        """Generate concrete and rebar fibers in the section coordinate system.

        Returns:
            (concrete_fibers, rebar_fibers)
        """
        if max_dx <= 0.0 or max_dy <= 0.0:
            raise ValueError("fiber dimensions must be positive")
        concrete_fibers: List[WallFiber] = []
        for seg in self.segments:
            concrete_fibers.extend(seg.discretize(max_dx=max_dx, max_dy=max_dy))

        rebar_fibers = [r.to_fiber() for r in self.rebars]
        return concrete_fibers, rebar_fibers

    # -------------------------------------------------------------------------
    # Standard factory methods for common shear wall geometries
    # -------------------------------------------------------------------------

    @classmethod
    def rectangle(
        cls,
        length: float,
        thickness: float,
        rebars: Optional[List[WallRebar]] = None,
        origin_at_bottom_left: bool = False,
    ) -> WallSection:
        """Create a single rectangular wall along Y-axis or X-axis.

        By default, length is along Y-axis (height in plan, 0 to length)
        and thickness along X-axis (-thickness/2 to thickness/2).
        """
        if origin_at_bottom_left:
            # Segment along Y: length along Y, thickness along X
            # local x' along length (angle=90 deg):
            seg = WallSegment(
                x0=thickness,
                y0=0.0,
                length=length,
                thickness=thickness,
                angle_deg=90.0,
            )
        else:
            # Centered at (0, 0): Y from -length/2 to length/2, X from -thickness/2 to thickness/2
            seg = WallSegment(
                x0=thickness / 2.0,
                y0=-length / 2.0,
                length=length,
                thickness=thickness,
                angle_deg=90.0,
            )
        return cls(segments=[seg], rebars=rebars or [])

    @classmethod
    def flanged_I(
        cls,
        length: float,
        web_thickness: float,
        flange_width: float,
        flange_thickness: float,
        rebars: Optional[List[WallRebar]] = None,
    ) -> WallSection:
        """Create a symmetrical flanged I-section wall along Y-axis (like Section 7 example).

        - Length `length` (L_w or h) along Y from -length/2 to length/2.
        - Web thickness `web_thickness` (b_w) along X.
        - Flanges at top (Y = length/2 - flange_thickness to length/2) and
          bottom (Y = -length/2 to -length/2 + flange_thickness), width `flange_width` (b_f).
        """
        half_l = length / 2.0
        tf = flange_thickness
        tw = web_thickness
        bf = flange_width

        # Web segment between flanges: length = (length - 2 * tf), thickness = tw
        web_len = length - 2.0 * tf
        # Segments:
        # Bottom flange: along X, from -bf/2 to bf/2, Y from -half_l to -half_l + tf
        bottom_flange = WallSegment(
            x0=-bf / 2.0,
            y0=-half_l,
            length=bf,
            thickness=tf,
            angle_deg=0.0,
        )
        # Web: along Y, from -half_l + tf to half_l - tf
        web = WallSegment(
            x0=tw / 2.0,
            y0=-half_l + tf,
            length=web_len,
            thickness=tw,
            angle_deg=90.0,
        )
        # Top flange: along X, from -bf/2 to bf/2, Y from half_l - tf to half_l
        top_flange = WallSegment(
            x0=-bf / 2.0,
            y0=half_l - tf,
            length=bf,
            thickness=tf,
            angle_deg=0.0,
        )

        return cls(
            segments=[bottom_flange, web, top_flange], rebars=rebars or []
        )

    @classmethod
    def flanged_L(
        cls,
        web_length: float,
        web_thickness: float,
        flange_length: float,
        flange_thickness: float,
        rebars: Optional[List[WallRebar]] = None,
    ) -> WallSection:
        """Create an L-shaped shear wall.

        Web along Y (length `web_length`, thickness `web_thickness`).
        Flange along X at bottom (length `flange_length`, thickness `flange_thickness`).
        """
        # Flange at Y=0 along X
        flange = WallSegment(
            x0=0.0,
            y0=0.0,
            length=flange_length,
            thickness=flange_thickness,
            angle_deg=0.0,
        )
        # Web along Y from Y=flange_thickness
        web = WallSegment(
            x0=web_thickness,
            y0=flange_thickness,
            length=web_length - flange_thickness,
            thickness=web_thickness,
            angle_deg=90.0,
        )
        return cls(segments=[flange, web], rebars=rebars or [])

    @classmethod
    def core_C(
        cls,
        web_length: float,
        flange_length: float,
        thickness: float,
        rebars: Optional[List[WallRebar]] = None,
    ) -> WallSection:
        """Create a C/U-shaped elevator core wall.

        - Back web along Y of length `web_length`, thickness `thickness`.
        - Two side flanges along +X of length `flange_length`, thickness `thickness`.
        """
        tw = thickness
        # Back web: along Y, from 0 to web_length
        back_web = WallSegment(
            x0=tw,
            y0=0.0,
            length=web_length,
            thickness=tw,
            angle_deg=90.0,
        )
        # Bottom flange: along X, from tw to flange_length, at Y=0
        bottom_flange = WallSegment(
            x0=tw,
            y0=0.0,
            length=flange_length - tw,
            thickness=tw,
            angle_deg=0.0,
        )
        # Top flange: along X, from tw to flange_length, at Y=web_length - tw
        top_flange = WallSegment(
            x0=tw,
            y0=web_length - tw,
            length=flange_length - tw,
            thickness=tw,
            angle_deg=0.0,
        )
        return cls(
            segments=[back_web, bottom_flange, top_flange], rebars=rebars or []
        )
