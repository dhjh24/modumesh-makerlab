"""QR Code Sign plugin — generate a 3D-printable QR code sign/plaque.

Uses batch extrusion for performance: all modules are added to a single
sketch via pushPoints, then extruded in one step.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from modumesh_plugin_sdk import PluginContext

_VERSION = "1.0.0"


def run(ctx: "PluginContext") -> None:
    """Generate a QR code sign using CadQuery + qrcode library."""
    import cadquery as cq

    ctx.set_progress(5, "validating input")

    data = str(ctx.input.get("data", "")).strip()
    if not data:
        raise ValueError("data is required")

    w = max(30, min(300, float(ctx.input.get("width", 80))))
    h = max(30, min(300, float(ctx.input.get("height", 80))))
    t = max(1, min(10, float(ctx.input.get("thickness", 3))))
    mh = max(0.5, min(5, float(ctx.input.get("module_height", 1.5))))
    raised = bool(ctx.input.get("raised", True))
    margin = max(2, min(20, float(ctx.input.get("margin_mm", 5))))
    cr = max(0, min(10, float(ctx.input.get("corner_radius", 2))))

    ctx.set_progress(10, "encoding QR code")

    import qrcode
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=0,
    )
    qr.add_data(data)
    qr.make(fit=True)
    modules = qr.get_matrix()
    n = len(modules)

    ctx.set_progress(15, f"QR code generated ({n}×{n})")

    # Calculate module size to fit within the sign minus margin
    usable_w = w - 2 * margin
    usable_h = h - 2 * margin
    ms = min(usable_w / n, usable_h / n)
    qr_w = ms * n
    qr_h = ms * n
    x_off = -qr_w / 2 + ms / 2
    y_off = -qr_h / 2 + ms / 2

    # Build base plate
    sign = cq.Workplane("XY").rect(w, h).extrude(t)
    if cr > 0:
        sign = sign.edges("|Z").fillet(cr)

    # Collect all module centers
    centers = []
    count = 0
    for row in range(n):
        for col in range(n):
            if modules[row][col]:
                centers.append((x_off + col * ms, y_off + row * ms))
                count += 1

    ctx.set_progress(40, f"extruding {count} modules")

    # Batch all modules via pushPoints — one extrude/cut operation
    ms_inset = ms * 0.88  # slight inset for gap between modules

    if raised:
        # Union all modules at once
        modules_cq = (
            cq.Workplane("XY")
            .pushPoints(centers)
            .rect(ms_inset, ms_inset)
            .extrude(t + mh)
        )
        sign = sign.union(modules_cq)
    else:
        modules_cq = (
            sign.faces(">Z")
            .workplane()
            .pushPoints(centers)
            .rect(ms_inset, ms_inset)
            .cutBlind(-mh)
        )

    ctx.set_progress(75, "exporting STL")

    stl_path = Path(ctx.work_dir) / "model.stl"
    sign.val().exportStl(str(stl_path), tolerance=0.05)
    ctx.register_output("model.stl")

    ctx.set_progress(95, "writing metadata")
    ctx.write_json("meta.json", {
        "schema_version": "1",
        "plugin_id": "qr-code-sign",
        "plugin_version": _VERSION,
        "data": data,
        "qr_size": n,
        "modules": count,
        "dimensions_mm": {"width": w, "height": h, "thickness": t, "module_height": mh},
        "module_size_mm": round(ms, 3),
        "raised": raised,
        "stl_bytes": stl_path.stat().st_size,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    })

    ctx.set_progress(100, "qr code sign complete")
