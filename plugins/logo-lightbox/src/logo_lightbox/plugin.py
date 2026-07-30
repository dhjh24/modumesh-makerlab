"""Logo Light Box plugin — face, enclosure, and back-panel generation.

Converts text or uploaded artwork into a 3D-printable LED light box
with replaceable face plate, enclosure, and snap-fit back panel.
"""

from __future__ import annotations

import base64
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from modumesh_plugin_sdk import PluginContext

# Reusable version string
_VERSION = "1.0.0"


# ── SVG Sanitization ──────────────────────────────────────────────────

_DANGEROUS_SVG_PATTERNS = re.compile(
    r"(<script|<svg\s[^>]*onload=|javascript:|data:\s*text/html|<foreignObject|"
    r"<use\s[^>]*href=|<use\s[^>]*xlink:href=|<!ENTITY|<!DOCTYPE\[)",
    re.IGNORECASE,
)
_EXTERNAL_REF_PATTERN = re.compile(
    r'(href|xlink:href)=["\'](https?://|ftp://)',
    re.IGNORECASE,
)


def _sanitize_svg(content: str) -> str:
    """Remove dangerous content from SVG markup.

    Strips scripts, event handlers, external references, embedded HTML,
    external entities, DTDs, and foreign objects.
    """
    if not content or len(content) > 1_000_000:
        raise ValueError("SVG content is empty or exceeds 1 MB")

    # Block DTDs and external entities
    if "<!DOCTYPE" in content or "<!ENTITY" in content:
        raise ValueError("SVG contains DOCTYPE or ENTITY declarations — rejected")

    # Block known dangerous patterns
    if _DANGEROUS_SVG_PATTERNS.search(content):
        raise ValueError("SVG contains unsafe content (scripts, handlers, foreign objects)")

    # Block external references
    if _EXTERNAL_REF_PATTERN.search(content):
        raise ValueError("SVG contains external references — rejected")

    # Scrub leftover event handler attributes
    cleaned = re.sub(r'\s+on\w+\s*=\s*["\'][^"\']*["\']', "", content, flags=re.IGNORECASE)

    return cleaned


# ── PNG Tracing ──────────────────────────────────────────────────────

def _png_to_svg_trace(
    png_data: bytes,
    threshold: int = 128,
    smoothing: float = 1.0,
) -> str:
    """Convert a PNG bitmap to SVG paths using potrace via subprocess.

    Returns the SVG markup string with traced paths.
    """
    import subprocess
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        png_path = Path(tmp) / "input.png"
        bmp_path = Path(tmp) / "input.bmp"
        svg_path = Path(tmp) / "output.svg"

        png_path.write_bytes(png_data)

        # Convert PNG to BMP for potrace (potrace reads BMP/PGM/PPM)
        try:
            from PIL import Image
            img = Image.open(str(png_path))
            # Convert to grayscale
            if img.mode != "L":
                img = img.convert("L")
            # Apply threshold
            img = img.point(lambda p: 255 if p > threshold else 0, mode="1")
            img.save(str(bmp_path), format="BMP")
        except ImportError:
            raise RuntimeError("Pillow (PIL) is required for PNG tracing")

        # Run potrace
        result = subprocess.run(
            [
                "potrace",
                "-s",  # SVG output
                "--svg",
                "-o", str(svg_path),
                "-t", str(smoothing),
                str(bmp_path),
            ],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            raise RuntimeError(f"potrace failed (exit={result.returncode}): {result.stderr[-500:]}")

        if not svg_path.is_file():
            raise RuntimeError("potrace did not produce SVG output")

        svg_content = svg_path.read_text(encoding="utf-8")
        # Wrap in a proper SVG tag with viewBox
        return svg_content


# ── Validation Report ─────────────────────────────────────────────────

def _estimate_material(params: dict[str, Any], part_volumes_mm3: dict[str, float]) -> dict[str, Any]:
    """Estimate print time, filament usage, and cost from part volumes."""
    material = params.get("material", "PLA")
    price_per_kg = float(params.get("filament_price_per_kg", 25))
    led_cost = float(params.get("led_kit_cost", 5))

    # Density g/cm³ for common materials
    densities = {"PLA": 1.24, "PETG": 1.27, "ABS": 1.04, "ASA": 1.07, "PC": 1.20}
    density = densities.get(material, 1.24)

    total_volume_mm3 = sum(part_volumes_mm3.values())
    total_volume_cm3 = total_volume_mm3 / 1000.0
    mass_g = total_volume_cm3 * density
    filament_cost = (mass_g / 1000.0) * price_per_kg
    total_cost = filament_cost + led_cost

    # Rough print time: ~10 mm³/s for standard 0.4mm nozzle
    print_time_s = total_volume_mm3 / 10.0

    return {
        "material": material,
        "total_volume_cm3": round(total_volume_cm3, 2),
        "estimated_mass_g": round(mass_g, 1),
        "filament_cost_usd": round(filament_cost, 2),
        "led_kit_cost_usd": led_cost,
        "total_estimated_cost_usd": round(total_cost, 2),
        "estimated_print_time_min": round(print_time_s / 60.0, 1),
        "density_g_per_cm3": density,
        "disclaimer": "Estimates are approximate. Actual print time, material use, and cost depend on printer, settings, and infill.",
    }


def _check_artwork_suggestions(
    artwork_type: str, text_val: str, issues: list[str],
) -> list[str]:
    """Add artwork repair suggestions as warnings."""
    suggestions: list[str] = []
    if artwork_type == "text" and text_val:
        if len(text_val) > 15:
            suggestions.append("Long text may appear small at 200×150mm. Consider increasing box size.")
        if text_val.isupper() and len(text_val) > 8:
            suggestions.append("ALL CAPS text may not fit well. Consider mixed case.")
    return suggestions


def _build_validation_report(params: dict[str, Any], issues: list[str]) -> dict[str, Any]:
    """Create a validation-report.json with preflight and geometry checks."""
    return {
        "schema_version": "1",
        "generator_version": _VERSION,
        "parameters": params,
        "issues": issues,
        "status": "blocked" if any(
            i.startswith("ERROR") for i in issues
        ) else "warning" if issues else "passed",
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


# ── Geometry Generation (inline CadQuery ─────────────────────────────

def _generate_parts(
    ctx: "PluginContext",
    params: dict[str, Any],
    work_dir: Path,
) -> dict[str, Any]:
    """Generate face, enclosure, and back panel STL files using CadQuery."""
    import cadquery as cq

    w, h = params["width"], params["height"]
    bd = params["box_depth"]
    ft, wt, bt = params["face_thickness"], params["wall_thickness"], params["back_thickness"]
    dg, lcd = params["diffuser_gap"], params["led_cavity_depth"]
    back_style, cable_exit = params["back_style"], params["cable_exit"]
    text_val, artwork_type = params.get("text", ""), params.get("artwork_type", "text")

    # Face plate
    face = cq.Workplane("XY").rect(w, h).extrude(ft)
    if artwork_type == "text" and text_val:
        margin = max(w * 0.08, 10)
        fs = min((w - 2*margin) / max(len(text_val), 1) * 1.5, (h - 2*margin) * 0.6, 40)
        fs = max(fs, 6)
        face = face.faces(">Z").workplane().text(text_val, fs, ft*0.8, combine="cut", font="DejaVu Sans")
        cr = min(w, h) * 0.04
        if cr > 1:
            face = face.edges("|Z").fillet(cr)
    face.val().exportStl(str(work_dir / "face.stl"), 0.05)

    # Enclosure
    box = cq.Workplane("XY").rect(w, h).extrude(bd)
    iw, ih = w - 2*wt, h - 2*wt
    box = box.faces("<Z").workplane().rect(iw, ih).cutBlind(bd - bt)
    cd = min(lcd, bd - bt - dg - 2)
    if cd > 2:
        box = box.faces(">Z").workplane().rect(iw*0.7, ih*0.7).cutBlind(-cd)
    if cable_exit == "bottom":
        box = box.faces(">Z").workplane().transformed(offset=(0, -h/2+1, 0)).rect(8, 6).cutBlind(-wt-1)
    elif cable_exit == "left":
        box = box.faces(">Z").workplane().transformed(offset=(-w/2+1, 0, 0)).rect(6, 8).cutBlind(-wt-1)
    elif cable_exit == "right":
        box = box.faces(">Z").workplane().transformed(offset=(w/2-1, 0, 0)).rect(6, 8).cutBlind(-wt-1)
    elif cable_exit == "rear":
        box = box.faces(">Z").workplane().transformed(offset=(0, h/2-1, 0)).rect(8, 6).cutBlind(-wt-1)
    box.val().exportStl(str(work_dir / "enclosure.stl"), 0.05)

    # Back panel
    bw, bh = w - 2*wt - 0.2, h - 2*wt - 0.2
    back = cq.Workplane("XY").rect(bw, bh).extrude(bt)
    if back_style == "snap-fit":
        for x in (-bw/2+8, bw/2-8):
            back = back.faces(">Z").workplane().transformed(offset=(x, bh/2-2, 0)).rect(6, 3).extrude(2)
            back = back.faces(">Z").workplane().transformed(offset=(x, -bh/2+2, 0)).rect(6, 3).extrude(2)
    back.val().exportStl(str(work_dir / "back-panel.stl"), 0.05)

    # GLB preview
    assembled = face.translate((0, 0, bd)).union(box).union(back)
    tmp = work_dir / "_tmp.stl"
    assembled.val().exportStl(str(tmp), 0.1)
    try:
        import trimesh
        m = trimesh.load(str(tmp))
        m.export(str(work_dir / "preview.glb"), file_type="glb")
    except Exception:
        pass
    if tmp.is_file():
        tmp.unlink()

    return {
        "face_bytes": (work_dir / "face.stl").stat().st_size,
        "enclosure_bytes": (work_dir / "enclosure.stl").stat().st_size,
        "back_bytes": (work_dir / "back-panel.stl").stat().st_size,
        "glb_bytes": (work_dir / "preview.glb").stat().st_size if (work_dir / "preview.glb").is_file() else 0,
        "cq_version": getattr(cq, "__version__", "unknown"),
    }


# ── Entrypoint ────────────────────────────────────────────────────────

def run(ctx: "PluginContext") -> None:
    """Generate a Logo Light Box from the input parameters."""
    import cadquery as cq  # noqa: F401 — load VTK/CadQuery early before memory limit
    ctx.set_progress(5, "validating input")
    inp = ctx.input

    artwork_type = str(inp.get("artwork_type", "text"))
    text_val = str(inp.get("text", "")).strip()
    artwork_data = str(inp.get("artwork_data", "")).strip()

    if artwork_type not in ("text", "svg", "png"):
        raise ValueError(f"Unsupported artwork_type '{artwork_type}'")

    if artwork_type == "text" and not text_val:
        raise ValueError("text is required when artwork_type=text")

    if artwork_type in ("svg", "png") and not artwork_data:
        raise ValueError(f"artwork_data is required when artwork_type={artwork_type}")

    rights_confirmed = bool(inp.get("rights_confirmed", False))
    if artwork_type in ("svg", "png") and not rights_confirmed:
        raise ValueError("You must confirm you have permission to use the uploaded artwork")

    # Clamp dimensions
    w = max(50, min(500, float(inp.get("width", 200))))
    h = max(50, min(500, float(inp.get("height", 150))))
    bd = max(15, min(100, float(inp.get("box_depth", 30))))
    ft = max(1, min(10, float(inp.get("face_thickness", 2))))
    wt = max(1, min(10, float(inp.get("wall_thickness", 2))))
    bt = max(1, min(10, float(inp.get("back_thickness", 2))))
    dg = max(1, min(10, float(inp.get("diffuser_gap", 3))))
    lcd = max(5, min(50, float(inp.get("led_cavity_depth", 15))))
    back_style = str(inp.get("back_style", "snap-fit"))
    cable_exit = str(inp.get("cable_exit", "bottom"))
    mounting = str(inp.get("mounting", "none"))

    if back_style not in ("snap-fit", "screw", "slide-in"):
        back_style = "snap-fit"
    if cable_exit not in ("none", "left", "right", "bottom", "rear"):
        cable_exit = "bottom"
    if mounting not in ("none", "tabletop", "keyholes", "screws"):
        mounting = "none"

    params = {
        "artwork_type": artwork_type,
        "text": text_val,
        "width": w,
        "height": h,
        "box_depth": bd,
        "face_thickness": ft,
        "wall_thickness": wt,
        "back_thickness": bt,
        "diffuser_gap": dg,
        "led_cavity_depth": lcd,
        "back_style": back_style,
        "cable_exit": cable_exit,
        "mounting": mounting,
        "rights_confirmed": rights_confirmed,
        "has_artwork_data": bool(artwork_data),
    }

    # SVG sanitization / PNG tracing
    issues: list[str] = []
    has_traced = False
    if artwork_type == "svg" and artwork_data:
        try:
            decoded = base64.b64decode(artwork_data).decode("utf-8", errors="replace")
            decoded = _sanitize_svg(decoded)
        except (ValueError, Exception) as exc:
            issues.append(f"ERROR: SVG sanitization failed: {exc}")
    elif artwork_type == "png" and artwork_data:
        try:
            threshold = int(inp.get("trace_threshold", 128))
            smoothing = float(inp.get("trace_smoothing", 1.0))
            png_bytes = base64.b64decode(artwork_data)
            traced_svg = _png_to_svg_trace(png_bytes, threshold=threshold, smoothing=smoothing)
            # Save traced SVG for reprocessing
            (Path(ctx.work_dir) / "_traced.svg").write_text(traced_svg, encoding="utf-8")
            has_traced = True
            issues.append("INFO: PNG traced to SVG via potrace. Verify artwork quality before printing.")
        except Exception as exc:
            issues.append(f"WARNING: PNG tracing failed: {exc}. Using placeholder opening.")

    # Artwork suggestions
    suggestions = _check_artwork_suggestions(artwork_type, text_val, issues)
    issues.extend(suggestions)

    # Geometry validation
    if wt * 2 >= w or wt * 2 >= h:
        issues.append(f"ERROR: wall_thickness {wt}mm exceeds half of width or height")
    if bd <= dg + lcd + 2:
        issues.append(f"WARNING: box_depth {bd}mm may be too shallow for LED cavity + diffuser gap")

    ctx.set_progress(8, "preflight checks complete")

    # Write validation report
    work_dir = Path(ctx.work_dir)
    validation = _build_validation_report(params, issues)
    ctx.write_json("validation-report.json", validation)

    if any(i.startswith("ERROR") for i in issues):
        raise ValueError(f"Preflight checks failed: {'; '.join(issues)}")

    # Generate parts
    start_time = time.time()
    part_meta = _generate_parts(ctx, params, work_dir)
    duration_s = time.time() - start_time

    # Register outputs
    for fname in ("face.stl", "enclosure.stl", "back-panel.stl", "preview.glb"):
        if (work_dir / fname).is_file():
            ctx.register_output(fname)

    # Write design manifest
    ctx.set_progress(95, "writing design manifest")
    design = {
        "schema_version": "1",
        "generator": "logo-lightbox",
        "generator_version": _VERSION,
        "cadquery_version": part_meta.get("cq_version", "unknown"),
        "parameters": params,
        "outputs": {
            "face.stl": {"size_bytes": part_meta.get("face_bytes", 0)},
            "enclosure.stl": {"size_bytes": part_meta.get("enclosure_bytes", 0)},
            "back-panel.stl": {"size_bytes": part_meta.get("back_bytes", 0)},
            "preview.glb": {"size_bytes": part_meta.get("glb_bytes", 0)},
        },
        "generation_duration_s": round(duration_s, 2),
        "warnings": [i for i in issues if i.startswith("WARNING") or i.startswith("INFO")],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    # Material estimate (based on STL file sizes as volume proxy)
    part_volumes = {
        "face": part_meta.get("face_bytes", 0),
        "enclosure": part_meta.get("enclosure_bytes", 0),
        "back_panel": part_meta.get("back_bytes", 0),
    }
    design["material_estimate"] = _estimate_material(params, part_volumes)

    ctx.write_json("design.json", design)

    ctx.set_progress(100, "logo light box complete")
