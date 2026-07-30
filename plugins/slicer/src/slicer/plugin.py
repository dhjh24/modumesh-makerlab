"""Slicer plugin — slice STL files using PrusaSlicer headless."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from modumesh_plugin_sdk import PluginContext

_VERSION = "1.0.0"

# Printer profile → PrusaSlicer INI snippets
_PRINTER_INI: dict[str, str] = {
    "mk3s": """
printer_model = MK3S
printer_notes = ModuMesh MakerLab
bed_shape = 0x0,250x0,250x210,0x210
bed_temperature = 60
before_layer_gcode = ;BEFORE_LAYER_CHANGE
after_layer_gcode = ;AFTER_LAYER_CHANGE
""",
    "mk4": """
printer_model = MK4
printer_notes = ModuMesh MakerLab
bed_shape = 0x0,250x0,250x210,0x210
bed_temperature = 60
before_layer_gcode = ;BEFORE_LAYER_CHANGE
after_layer_gcode = ;AFTER_LAYER_CHANGE
""",
    "xl": """
printer_model = XL
printer_notes = ModuMesh MakerLab
bed_shape = 0x0,360x0,360x360,0x360
bed_temperature = 60
before_layer_gcode = ;BEFORE_LAYER_CHANGE
after_layer_gcode = ;AFTER_LAYER_CHANGE
""",
}


def _write_prusa_ini(profile: str, nozzle: float, layer: float, infill: float, supports: str, material: str) -> str:
    """Write a temporary PrusaSlicer config INI."""
    printer = _PRINTER_INI.get(profile, _PRINTER_INI["mk4"])
    support_val = {"none": 0, "everywhere": 2, "touching_buildplate": 1}.get(supports, 0)
    mat_map = {"PLA": "PLA", "PETG": "PETG", "ABS": "ABS"}
    filament = mat_map.get(material, "PLA")

    return f"""
{printer}
nozzle_diameter = {nozzle}
layer_height = {layer}
first_layer_height = {max(layer, 0.15)}
fill_density = {infill}%
support_material = {support_val}
filament_type = {filament}
temperature = 210
first_layer_temperature = 215
print_settings_id = ModuMesh
filament_settings_id = ModuMesh-{filament}
printer_settings_id = ModuMesh-{profile}
complete_individual = 1
output_filename_format = {{input_filename_base}}.gcode
gcode_flavor = marlin
use_relative_e_distances = 0
use_firmware_retraction = 0
"""


def run(ctx: "PluginContext") -> None:
    """Slice an STL file using PrusaSlicer headless."""
    ctx.set_progress(5, "preparing slice")

    filename = str(ctx.input.get("filename", "model.stl")).strip()
    profile = str(ctx.input.get("printer_profile", "mk4"))
    nozzle = float(ctx.input.get("nozzle_diameter", 0.4))
    layer = float(ctx.input.get("layer_height", 0.2))
    infill = float(ctx.input.get("infill", 15))
    supports = str(ctx.input.get("supports", "none"))
    material = str(ctx.input.get("material", "PLA"))

    work_dir = Path(ctx.work_dir)
    stl_path = work_dir / filename
    if not stl_path.is_file():
        raise ValueError(f"STL file not found: {filename}")

    ctx.set_progress(15, "writing config")

    ini_content = _write_prusa_ini(profile, nozzle, layer, infill, supports, material)

    # Write config to temp and run prusa-slicer
    with tempfile.NamedTemporaryFile(mode="w", suffix=".ini", delete=False) as f:
        f.write(ini_content)
        ini_path = f.name

    try:
        ctx.set_progress(30, f"slicing {filename} on {profile}")

        # Slice with -g (short for --export-gcode/--slice)
        # prusa-slicer outputs to CWD with its own naming convention
        result = subprocess.run(
            [
                "prusa-slicer",
                "--load", ini_path,
                "-g",
                str(stl_path),
            ],
            capture_output=True, text=True, timeout=150,
            cwd=str(work_dir),
            env={**os.environ},
        )

        # prusa-slicer writes model.gcode to CWD
        stdout = result.stdout or ""
        stderr = result.stderr or ""

        # prusa-slicer writes gcode to CWD with configured naming
        gcode_candidates = sorted(work_dir.glob("*.gcode"))
        gcode_path = gcode_candidates[0] if gcode_candidates else None

        # Parse estimated times/filament from G-code
        estimated = _parse_gcode(gcode_path) if gcode_path.is_file() else {}

        if gcode_path.is_file():
            # Rename to output.gcode for consistent naming
            final_gcode = work_dir / "output.gcode"
            if final_gcode.exists():
                final_gcode.unlink()
            gcode_path.rename(final_gcode)
            ctx.register_output("output.gcode")

        mf_path = work_dir / "output.3mf"
        if mf_path.is_file():
            ctx.register_output("output.3mf")

        report: dict[str, Any] = {
            "schema_version": "1",
            "plugin_id": "slicer",
            "plugin_version": _VERSION,
            "source": {"filename": filename},
            "slice": {
                "printer_profile": profile,
                "nozzle_mm": nozzle,
                "layer_height_mm": layer,
                "infill_pct": infill,
                "supports": supports,
                "material": material,
            },
            "estimated": estimated,
            "prusa_slicer_stdout": stdout[-500:] if stdout else None,
            "prusa_slicer_stderr": stderr[-500:] if stderr else None,
            "return_code": result.returncode,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

        ctx.write_json("slicing-report.json", report)
        ctx.set_progress(100, "slicing complete")

    finally:
        try:
            os.unlink(ini_path)
        except Exception:
            pass


def _parse_gcode(path: Path) -> dict[str, Any]:
    """Parse G-code headers for print time and filament estimates."""
    result: dict[str, Any] = {}
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
        for line in content.split("\n")[:200]:
            line = line.strip()
            if "; estimated printing time" in line.lower():
                result["print_time_estimate"] = line.split("=")[-1].strip() if "=" in line else line
            if "; total filament used" in line.lower():
                val = line.split("=")[-1].strip() if "=" in line else ""
                result["filament_length_mm"] = val
            if "; total filament weight" in line.lower():
                val = line.split("=")[-1].strip() if "=" in line else ""
                result["filament_weight_g"] = val
    except Exception:
        pass
    if not result:
        result["note"] = "Could not parse G-code header estimates"
    return result
