"""My Generator plugin — replace this with your implementation."""

from __future__ import annotations
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from modumesh_plugin_sdk import PluginContext


def run(ctx: "PluginContext") -> None:
    """Entrypoint: generate model.stl and meta.json."""
    label = str(ctx.input.get("label", "my-part"))
    scale = float(ctx.input.get("scale", 1))

    ctx.set_progress(10, f"generating {label} at {scale}x")

    # TODO: Replace with your generation logic
    work = Path(ctx.work_dir)
    stl_content = b"solid placeholder\nendsolid placeholder\n"
    (work / "model.stl").write_bytes(stl_content)

    ctx.register_output("model.stl")
    ctx.write_json("meta.json", {
        "plugin_id": ctx.plugin_id,
        "plugin_version": ctx.plugin_version,
        "label": label,
        "scale": scale,
    })
    ctx.set_progress(100, "complete")
