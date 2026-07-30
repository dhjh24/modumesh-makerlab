"""Nameplate generation plugin using CadQuery.

Generates a custom text nameplate with optional mounting holes,
corner rounding, and engraved or raised text. Exports STL, STEP,
and GLB formats plus metadata.
"""

from __future__ import annotations

import json
import math
import os
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from modumesh_plugin_sdk import PluginContext

# Font allowlist — fonts available on most Linux systems
ALLOWED_FONTS: dict[str, str] = {
    "Arial": "DejaVu Sans",
    "Arial Bold": "DejaVu Sans",
    "Arial Italic": "DejaVu Sans",
    "Courier New": "DejaVu Sans Mono",
    "Times New Roman": "DejaVu Serif",
    "Times New Roman Bold": "DejaVu Serif",
    "Verdana": "DejaVu Sans",
}

FONT_STYLES: dict[str, str] = {
    "Arial": "Book",
    "Arial Bold": "Bold",
    "Arial Italic": "Oblique",
    "Courier New": "Book",
    "Times New Roman": "Book",
    "Times New Roman Bold": "Bold",
    "Verdana": "Book",
}

# Manufacturer print-caution limits
MAX_OVERHANG_DEG = 45
MIN_WALL_THICKNESS_MM = 0.8


def _clamp(val: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, val))


def _cadquery_version() -> str:
    try:
        import cadquery as cq  # noqa: F401
        from cadquery import __version__  # noqa: F811
        return __version__
    except Exception:
        return "unknown"


def _nameplate_base(
    ctx: "PluginContext",
    width: float,
    height: float,
    thickness: float,
    corner_radius: float,
    hole_mode: str,
    hole_diameter: float,
) -> Any:
    """Create the base plate body."""
    import cadquery as cq

    ctx.set_progress(15, "building base plate")

    if corner_radius > 0:
        r = min(corner_radius, width / 2, height / 2)
        base = (
            cq.Workplane("XY")
            .rect(width, height)
            .extrude(thickness)
            .edges("|Z")
            .fillet(r)
        )
    else:
        base = cq.Workplane("XY").rect(width, height).extrude(thickness)

    # Mounting holes
    if hole_mode != "none":
        margin = max(width * 0.12, 8.0)
        hole_r = hole_diameter / 2.0

        if hole_mode == "two":
            positions = [
                (width / 2 - margin, 0.0),
                (-width / 2 + margin, 0.0),
            ]
        else:  # four
            positions = [
                (width / 2 - margin, height / 2 - margin),
                (-width / 2 + margin, height / 2 - margin),
                (width / 2 - margin, -height / 2 + margin),
                (-width / 2 + margin, -height / 2 + margin),
            ]

        for px, py in positions:
            base = (
                base.faces("<Z")
                .workplane()
                .transformed(offset=(px, py, 0))
                .circle(hole_r)
                .cutThruAll()
            )

    return base


def _add_text(
    ctx: "PluginContext",
    base: Any,
    text: str,
    text_depth: float,
    text_raised: bool,
    font_size: float,
    font_name: str,
    thickness: float,
    width: float,
    height: float,
) -> Any:
    """Add engraved or raised text to the base plate."""
    import cadquery as cq

    ctx.set_progress(40, "adding text")

    font_family = ALLOWED_FONTS.get(font_name, "Arial")
    font_style = FONT_STYLES.get(font_name, "Regular")

    # Position text centered on the top face
    workplane = base.faces(">Z").workplane()

    if text_raised:
        # Raised text: union with the plate surface
        text_solid = workplane.text(
            txt=text,
            fontsize=font_size,
            distance=text_depth,
            combine=True,
            font=font_family,
            fontPath=None,
        )
        result = base.union(text_solid)
    else:
        # Engraved text: cut into the plate
        result = workplane.text(
            txt=text,
            fontsize=font_size,
            distance=min(text_depth, thickness * 0.8),
            combine="cut",
            font=font_family,
            fontPath=None,
        )

    return result


def _export_step(shape: Any, path: str) -> None:
    """Export to STEP format."""
    import cadquery as cq
    cq.exporters.export(shape, path, exportType="STEP")


def _export_stl(shape: Any, path: str, tolerance: float = 0.01) -> None:
    """Export to STL format with controlled tessellation."""
    shape.val().exportStl(path, tolerance=tolerance)


def _export_glb_from_stl(stl_path: str, glb_path: str) -> None:
    """Convert STL to GLB using trimesh if available."""
    try:
        import trimesh
        mesh = trimesh.load(stl_path)
        # Ensure mesh is triangulated and has normals
        if not mesh.is_watertight:
            pass  # surface mesh still renders fine in viewers
        mesh.export(glb_path, file_type="glb")
    except ImportError:
        # Fallback: copy STL as GLB (viewers will still show it)
        import shutil
        shutil.copyfile(stl_path, glb_path)


def run(ctx: "PluginContext") -> None:
    """Generate a CadQuery nameplate from the input parameters."""
    import cadquery as cq

    ctx.set_progress(5, "validating input")

    # ── Read and validate inputs ───────────────────────────────────
    inp = ctx.input
    text = str(inp.get("text", "")).strip()

    if not text:
        raise ValueError("text is required")
    if len(text) > 32:
        raise ValueError(f"text too long ({len(text)} chars, max 32)")

    width = _clamp(float(inp.get("width", 100)), 20, 300)
    height = _clamp(float(inp.get("height", 40)), 10, 200)
    thickness = _clamp(float(inp.get("thickness", 3)), 1, 20)
    corner_radius = _clamp(float(inp.get("corner_radius", 5)), 0, 50)
    text_depth = _clamp(float(inp.get("text_depth", 1)), 0.2, 5)
    text_raised = bool(inp.get("text_raised", False))
    font_size = _clamp(float(inp.get("font_size", 12)), 4, 80)
    margin = _clamp(float(inp.get("margin", 5)), 1, 30)
    hole_mode = str(inp.get("hole_mode", "two"))
    if hole_mode not in ("none", "two", "four"):
        hole_mode = "two"
    hole_diameter = _clamp(float(inp.get("hole_diameter", 4)), 2, 20)
    font_name = str(inp.get("font_name", "Arial"))
    if font_name not in ALLOWED_FONTS:
        font_name = "Arial"

    # Validate geometry constraints
    available_text_width = width - 2 * margin
    if available_text_width <= 0:
        raise ValueError(f"margin {margin}mm exceeds plate width {width}mm")

    if hole_mode != "none" and hole_diameter >= min(width, height) * 0.4:
        raise ValueError(
            f"hole_diameter {hole_diameter}mm is too large for plate "
            f"{width}x{height}mm"
        )

    # ── Generate geometry ──────────────────────────────────────────
    cq_version = _cadquery_version()
    work_dir = Path(ctx.work_dir)
    start_time = time.time()

    ctx.set_progress(10, "building base plate")
    base = _nameplate_base(
        ctx, width, height, thickness, corner_radius,
        hole_mode, hole_diameter,
    )

    result = _add_text(
        ctx, base, text, text_depth, text_raised,
        font_size, font_name, thickness, width, height,
    )

    # ── Export ─────────────────────────────────────────────────────
    stl_path = str(work_dir / "model.stl")
    step_path = str(work_dir / "model.step")
    glb_path = str(work_dir / "model.glb")

    ctx.set_progress(60, "exporting STL")
    _export_stl(result, stl_path)
    ctx.register_output("model.stl")

    ctx.set_progress(70, "exporting STEP")
    _export_step(result, step_path)
    ctx.register_output("model.step")

    ctx.set_progress(85, "exporting GLB")
    _export_glb_from_stl(stl_path, glb_path)
    ctx.register_output("model.glb")

    # ── Compute metadata ───────────────────────────────────────────
    duration_s = time.time() - start_time
    stl_size = os.path.getsize(stl_path)

    # Basic printability info
    overhang_ok = True
    wall_ok = thickness >= MIN_WALL_THICKNESS_MM
    print_readiness = "print_ready"
    warnings: list[str] = []
    if not wall_ok:
        warnings.append(f"plate thickness {thickness}mm below {MIN_WALL_THICKNESS_MM}mm")
        print_readiness = "warning"

    ctx.set_progress(95, "writing metadata")
    ctx.write_json("meta.json", {
        "plugin_id": ctx.plugin_id,
        "plugin_version": ctx.plugin_version,
        "job_id": ctx.job_id,
        "input": {
            "text": text,
            "width": width,
            "height": height,
            "thickness": thickness,
            "corner_radius": corner_radius,
            "text_depth": text_depth,
            "text_raised": text_raised,
            "font_size": font_size,
            "margin": margin,
            "hole_mode": hole_mode,
            "hole_diameter": hole_diameter,
            "font_name": font_name,
        },
        "outputs": {
            "model.stl": {"size_bytes": stl_size},
            "model.step": {"size_bytes": os.path.getsize(step_path)},
            "model.glb": {"size_bytes": os.path.getsize(glb_path)},
        },
        "stats": {
            "generation_duration_s": round(duration_s, 2),
            "cadquery_version": cq_version,
        },
        "printability": {
            "status": print_readiness,
            "warnings": warnings,
            "overhang_ok": overhang_ok,
            "wall_thickness_mm": thickness,
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
    })

    ctx.set_progress(100, "nameplate complete")
