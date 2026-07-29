"""CadQuery geometry builder for the Nameplate plugin (millimeters)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import cadquery as cq

from nameplate.fonts import resolve_font_path
from nameplate.params import (
    RAISED_JOIN_OVERLAP_MM,
    TEXT_SIZE_RATIO,
    NameplateParams,
    ParameterError,
)

if TYPE_CHECKING:
    from cadquery import Workplane

# Fixed tessellation settings for deterministic mesh exports.
EXPORT_TOLERANCE = 0.1
EXPORT_ANGULAR_TOLERANCE = 0.2


def _hole_points(params: NameplateParams) -> list[tuple[float, float]]:
    """Compute hole centers in plate-local XY (origin at plate center)."""
    count = params.hole_count
    if count <= 0:
        return []

    half_w = params.width_mm / 2.0
    half_h = params.height_mm / 2.0
    m = params.edge_margin_mm
    x = half_w - m
    y = half_h - m

    if count == 1:
        return [(0.0, 0.0)]
    if count == 2:
        return [(-x, 0.0), (x, 0.0)]
    if count == 3:
        return [(-x, 0.0), (0.0, 0.0), (x, 0.0)]
    if count == 4:
        return [(-x, -y), (x, -y), (-x, y), (x, y)]
    raise ParameterError(f"unsupported hole_count {count}")


def _text_fontsize(params: NameplateParams) -> float:
    # Leave vertical margin so glyphs stay clear of holes / edges.
    usable = max(6.0, params.height_mm - 2.0 * params.edge_margin_mm)
    return max(4.0, min(usable * TEXT_SIZE_RATIO * 2.2, params.height_mm * 0.55))


def _text_halign(alignment: str) -> str:
    return {"left": "left", "center": "center", "right": "right"}[alignment]


def _text_offset_x(params: NameplateParams) -> float:
    """Shift workplane origin for left/right alignment toward plate edges."""
    if params.alignment == "center":
        return 0.0
    inset = params.edge_margin_mm
    half = params.width_mm / 2.0 - inset
    if params.alignment == "left":
        return -half
    return half


def _make_text_solid(
    params: NameplateParams,
    *,
    font_path: str,
    fontsize: float,
    extrude: float,
    z_offset: float,
) -> cq.Workplane:
    ox = _text_offset_x(params)
    return (
        cq.Workplane("XY")
        .workplane(offset=z_offset)
        .transformed(offset=(ox, 0, 0))
        .text(
            params.text,
            fontsize,
            extrude,
            fontPath=font_path,
            halign=_text_halign(params.alignment),
            valign="center",
            combine=False,
        )
    )


def _fit_fontsize(params: NameplateParams, font_path: str) -> float:
    """Shrink font size until text width fits inside the plate margins."""
    fontsize = _text_fontsize(params)
    usable_w = max(8.0, params.width_mm - 2.0 * params.edge_margin_mm)
    # Probe with a thin extrusion at z=0 (measurement only).
    for _ in range(10):
        probe = _make_text_solid(
            params,
            font_path=font_path,
            fontsize=fontsize,
            extrude=0.2,
            z_offset=0.0,
        )
        bb = probe.val().BoundingBox()
        width = float(bb.xlen)
        if width <= usable_w + 1e-3:
            return max(3.0, fontsize)
        fontsize *= 0.92 * (usable_w / max(width, 1e-3))
    return max(3.0, fontsize)


def build_nameplate(params: NameplateParams) -> "Workplane":
    """Build a solid nameplate Workplane in millimeters."""
    font_path = str(resolve_font_path(params.font))
    plate = cq.Workplane("XY").box(
        params.width_mm,
        params.height_mm,
        params.base_thickness_mm,
    )
    if params.corner_radius_mm > 0.05:
        plate = plate.edges("|Z").fillet(params.corner_radius_mm)

    fontsize = _fit_fontsize(params, font_path)

    if params.mode == "raised":
        # Sink text slightly into the plate so the boolean join is watertight.
        top_z = params.base_thickness_mm / 2.0
        overlap = RAISED_JOIN_OVERLAP_MM
        text_solid = _make_text_solid(
            params,
            font_path=font_path,
            fontsize=fontsize,
            extrude=params.text_depth_mm + overlap,
            z_offset=top_z - overlap,
        )
        solid = plate.union(text_solid)
    else:
        # Engrave via face cut (negative extrusion). Rebuild with fitted size.
        solid = plate.faces(">Z").workplane()
        ox = _text_offset_x(params)
        solid = solid.transformed(offset=(ox, 0, 0)).text(
            params.text,
            fontsize,
            -params.text_depth_mm,
            fontPath=font_path,
            halign=_text_halign(params.alignment),
            valign="center",
            combine=True,
        )

    points = _hole_points(params)
    if points:
        solid = (
            solid.faces(">Z")
            .workplane()
            .pushPoints(points)
            .hole(params.hole_diameter_mm)
        )

    return solid
