"""Entrypoint for the fixture-echo plugin."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from modumesh_plugin_sdk import PluginContext


def run(ctx: "PluginContext") -> None:
    """Write declared fixture outputs under the approved job directory."""
    message = str(ctx.input.get("message", ""))
    tag = str(ctx.input.get("tag", "fixture"))
    sleep_s = float(ctx.input.get("force_sleep_seconds") or 0)

    ctx.set_progress(10, "starting fixture echo")
    ctx.log(f"echoing message ({len(message)} chars) tag={tag}")

    if sleep_s > 0:
        ctx.set_progress(20, f"sleeping {sleep_s}s")
        end = time.monotonic() + sleep_s
        while time.monotonic() < end:
            time.sleep(min(0.2, end - time.monotonic()))

    ctx.set_progress(50, "writing echo.json")
    ctx.write_json(
        "echo.json",
        {
            "plugin_id": ctx.plugin_id,
            "plugin_version": ctx.plugin_version,
            "job_id": ctx.job_id,
            "tag": tag,
            "message": message,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
    )

    ctx.set_progress(80, "writing note.txt")
    ctx.write_text("note.txt", f"[{tag}] {message}\n")
    ctx.set_progress(100, "fixture echo complete")
