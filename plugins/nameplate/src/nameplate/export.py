"""Export helpers: STL, STEP, GLB, PNG thumbnail (deterministic tessellation)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import cadquery as cq
import numpy as np
import trimesh
from PIL import Image, ImageDraw

from nameplate.geometry import EXPORT_ANGULAR_TOLERANCE, EXPORT_TOLERANCE


def export_step(solid: cq.Workplane, path: Path) -> None:
    cq.exporters.export(solid, str(path))


def export_stl(solid: cq.Workplane, path: Path) -> None:
    cq.exporters.export(
        solid,
        str(path),
        tolerance=EXPORT_TOLERANCE,
        angularTolerance=EXPORT_ANGULAR_TOLERANCE,
    )


def stl_to_glb(stl_path: Path, glb_path: Path) -> trimesh.Trimesh:
    mesh = trimesh.load(str(stl_path), force="mesh")
    if isinstance(mesh, trimesh.Scene):
        mesh = trimesh.util.concatenate(tuple(mesh.geometry.values()))
    if not isinstance(mesh, trimesh.Trimesh):
        raise RuntimeError("Failed to load STL as a triangle mesh")
    # Stable vertex/face ordering helps deterministic GLB payloads.
    mesh.merge_vertices()
    mesh.export(str(glb_path))
    return mesh


def render_thumbnail_png(mesh: trimesh.Trimesh, path: Path, *, size: int = 256) -> None:
    """Headless orthographic top-down thumbnail (no OpenGL / STEP parse)."""
    verts = np.asarray(mesh.vertices, dtype=np.float64)
    faces = np.asarray(mesh.faces, dtype=np.int64)
    if verts.size == 0 or faces.size == 0:
        raise RuntimeError("cannot thumbnail empty mesh")

    xy = verts[:, :2]
    mins = xy.min(axis=0)
    maxs = xy.max(axis=0)
    span = np.maximum(maxs - mins, 1e-6)
    pad = 0.06 * span.max()
    mins = mins - pad
    maxs = maxs + pad
    span = maxs - mins

    scale = (size - 1) / span.max()
    # Center in square canvas.
    offset = ((size - span * scale) / 2.0) - mins * scale

    img = Image.new("RGB", (size, size), (245, 247, 250))
    draw = ImageDraw.Draw(img)

    # Painter's algorithm by mean Z (top faces last / brighter).
    face_z = verts[faces][:, :, 2].mean(axis=1)
    order = np.argsort(face_z)

    zmin = float(verts[:, 2].min())
    zmax = float(verts[:, 2].max())
    zspan = max(zmax - zmin, 1e-6)

    for fi in order:
        tri = verts[faces[fi]]
        pts = []
        for v in tri:
            x = float(v[0] * scale + offset[0])
            y = float((size - 1) - (v[1] * scale + offset[1]))
            pts.append((x, y))
        shade = 0.35 + 0.55 * ((float(tri[:, 2].mean()) - zmin) / zspan)
        color = (
            int(40 + 80 * shade),
            int(90 + 100 * shade),
            int(120 + 100 * shade),
        )
        draw.polygon(pts, fill=color)

    # Border for visual framing in the UI.
    draw.rectangle((0, 0, size - 1, size - 1), outline=(30, 40, 55), width=2)
    img.save(path, format="PNG", optimize=True)


def mesh_summary(mesh: trimesh.Trimesh) -> dict[str, Any]:
    bounds = mesh.bounds
    extents = mesh.extents
    return {
        "triangle_count": int(len(mesh.faces)),
        "vertex_count": int(len(mesh.vertices)),
        "bounding_box_mm": {
            "min": [float(bounds[0, 0]), float(bounds[0, 1]), float(bounds[0, 2])],
            "max": [float(bounds[1, 0]), float(bounds[1, 1]), float(bounds[1, 2])],
        },
        "dimensions_mm": {
            "x": float(extents[0]),
            "y": float(extents[1]),
            "z": float(extents[2]),
        },
        "volume_mm3": float(mesh.volume) if mesh.is_volume else None,
        "watertight": bool(mesh.is_watertight),
    }
