"""Mesh validation report for Nameplate outputs."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import numpy as np
import trimesh

from nameplate.params import NameplateParams


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def validate_mesh(
    mesh: trimesh.Trimesh,
    *,
    stl_path: Path,
    params: NameplateParams,
) -> dict[str, Any]:
    """Produce a structured validation report for the generated mesh."""
    warnings: list[str] = []
    verts = np.asarray(mesh.vertices, dtype=np.float64)
    faces = np.asarray(mesh.faces, dtype=np.int64)

    non_empty = verts.size > 0 and faces.size > 0
    finite = bool(np.isfinite(verts).all()) if non_empty else False

    if not non_empty:
        warnings.append("mesh is empty")
    if non_empty and not finite:
        warnings.append("non-finite vertex coordinates detected")

    # Degenerate faces (near-zero area).
    degenerate = 0
    if non_empty:
        tri = verts[faces]
        cross = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
        areas = np.linalg.norm(cross, axis=1) * 0.5
        degenerate = int(np.count_nonzero(areas < 1e-12))
        if degenerate:
            warnings.append(f"{degenerate} degenerate triangles")

    extents = mesh.extents if non_empty else np.zeros(3)
    bounds = mesh.bounds if non_empty else np.zeros((2, 3))
    watertight = bool(mesh.is_watertight) if non_empty else False
    volume = float(mesh.volume) if non_empty and mesh.is_volume else 0.0

    # Dimension sanity vs inputs (allow text protrusion / fillet tolerance).
    dim_ok = True
    if non_empty:
        tol = 1.5
        if abs(extents[0] - params.width_mm) > tol:
            dim_ok = False
            warnings.append(
                f"X extent {extents[0]:.2f} mm differs from width {params.width_mm}"
            )
        if abs(extents[1] - params.height_mm) > tol:
            dim_ok = False
            warnings.append(
                f"Y extent {extents[1]:.2f} mm differs from height {params.height_mm}"
            )
        expected_z = params.base_thickness_mm + (
            params.text_depth_mm if params.mode == "raised" else 0.0
        )
        if extents[2] < params.base_thickness_mm - 0.5:
            dim_ok = False
            warnings.append("Z extent thinner than base thickness")
        if extents[2] > expected_z + 1.0:
            warnings.append(
                f"Z extent {extents[2]:.2f} mm exceeds expected ~{expected_z:.2f} mm"
            )

    if non_empty and not watertight:
        warnings.append("mesh is not watertight")

    if non_empty and volume <= 0:
        warnings.append("non-positive volume")

    checksum = _sha256_file(stl_path) if stl_path.is_file() else ""

    passed = bool(
        non_empty
        and finite
        and dim_ok
        and volume > 0
        and len(faces) > 0
        and degenerate == 0
    )

    return {
        "passed": passed,
        "non_empty": non_empty,
        "finite_coordinates": finite,
        "dimensions_ok": dim_ok,
        "watertight": watertight,
        "volume_mm3": volume,
        "triangle_count": int(len(faces)),
        "vertex_count": int(len(verts)),
        "degenerate_triangles": degenerate,
        "warnings": warnings,
        "checksum_sha256": checksum,
        "bounding_box_mm": {
            "min": [float(bounds[0, 0]), float(bounds[0, 1]), float(bounds[0, 2])],
            "max": [float(bounds[1, 0]), float(bounds[1, 1]), float(bounds[1, 2])],
        },
        "dimensions_mm": {
            "x": float(extents[0]),
            "y": float(extents[1]),
            "z": float(extents[2]),
        },
        "units": "mm",
    }
