"""Entrypoint for the fixture-mesh plugin."""

from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from modumesh_plugin_sdk import PluginContext

_ASSETS = Path(__file__).resolve().parents[2] / "assets"


def run(ctx: "PluginContext") -> None:
    """Copy packaged mesh fixtures into the job work directory."""
    fmt = str(ctx.input.get("format") or "both")
    label = str(ctx.input.get("label") or "fixture-cube")
    scale = float(ctx.input.get("scale") or 1)
    include_plate = bool(ctx.input.get("include_build_plate", True))

    ctx.set_progress(10, "loading fixture assets")
    emitted: list[str] = []

    def _copy(name: str, dest: str) -> None:
        src = _ASSETS / name
        if not src.is_file():
            raise FileNotFoundError(f"missing fixture asset: {src}")
        shutil.copyfile(src, Path(ctx.work_dir) / dest)
        ctx.register_output(dest)
        emitted.append(dest)

    if fmt in ("stl", "both"):
        ctx.set_progress(40, "emitting model.stl")
        _copy("sample-cube.stl", "model.stl")

    if fmt in ("glb", "both"):
        ctx.set_progress(70, "emitting model.glb")
        _copy("sample-cube.glb", "model.glb")

    ctx.set_progress(90, "writing meta.json")
    ctx.write_json(
        "meta.json",
        {
            "plugin_id": ctx.plugin_id,
            "plugin_version": ctx.plugin_version,
            "job_id": ctx.job_id,
            "label": label,
            "format": fmt,
            "scale": scale,
            "include_build_plate": include_plate,
            "emitted": emitted,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    ctx.set_progress(100, "fixture mesh complete")
