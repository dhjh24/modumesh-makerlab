"""Entrypoint for the Nameplate CadQuery reference plugin."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from nameplate.export import export_step, export_stl, render_thumbnail_png, stl_to_glb
from nameplate.geometry import build_nameplate
from nameplate.mesh_validate import validate_mesh
from nameplate.params import ParameterError, validate_params

if TYPE_CHECKING:
    from modumesh_plugin_sdk import PluginContext

PLUGIN_VERSION = "1.0.0"


def run(ctx: "PluginContext") -> None:
    """Generate Nameplate outputs under the job work directory."""
    ctx.set_progress(5, "validating parameters")
    try:
        params = validate_params(ctx.input)
    except ParameterError as exc:
        raise ValueError(str(exc)) from exc

    ctx.log(
        f"nameplate {PLUGIN_VERSION}: mode={params.mode} "
        f"{params.width_mm}x{params.height_mm}x{params.base_thickness_mm} mm"
    )

    ctx.set_progress(20, "building CadQuery solid")
    solid = build_nameplate(params)

    work = ctx.work_dir
    stl_path = work / "model.stl"
    step_path = work / "model.step"
    glb_path = work / "model.glb"
    png_path = work / "thumbnail.png"

    ctx.set_progress(45, "exporting STEP")
    export_step(solid, step_path)
    ctx.register_output("model.step")

    ctx.set_progress(55, "exporting STL")
    export_stl(solid, stl_path)
    ctx.register_output("model.stl")

    ctx.set_progress(70, "building GLB preview mesh")
    mesh = stl_to_glb(stl_path, glb_path)
    ctx.register_output("model.glb")

    ctx.set_progress(80, "rendering PNG thumbnail")
    render_thumbnail_png(mesh, png_path)
    ctx.register_output("thumbnail.png")

    ctx.set_progress(90, "validating mesh")
    report = validate_mesh(mesh, stl_path=stl_path, params=params)
    if not report["passed"]:
        raise ValueError(
            "mesh validation failed: " + "; ".join(report.get("warnings") or ["unknown"])
        )

    outputs = {
        "model.stl": {"media_type": "model/stl", "bytes": stl_path.stat().st_size},
        "model.step": {"media_type": "model/step", "bytes": step_path.stat().st_size},
        "model.glb": {"media_type": "model/gltf-binary", "bytes": glb_path.stat().st_size},
        "thumbnail.png": {"media_type": "image/png", "bytes": png_path.stat().st_size},
        "metadata.json": {"media_type": "application/json"},
    }

    # Jobs act as immutable project versions; record job id as the version key.
    metadata = {
        "plugin_id": ctx.plugin_id,
        "plugin_version": ctx.plugin_version or PLUGIN_VERSION,
        "job_id": ctx.job_id,
        "project_version": ctx.job_id,
        "units": "mm",
        "inputs": params.as_dict(),
        "outputs": outputs,
        "validation": report,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "deterministic": {
            "export_tolerance_mm": 0.1,
            "export_angular_tolerance": 0.2,
            "note": "Identical plugin version + inputs yield identical STL checksums",
        },
    }
    ctx.write_json("metadata.json", metadata)
    ctx.set_progress(100, "nameplate complete")
