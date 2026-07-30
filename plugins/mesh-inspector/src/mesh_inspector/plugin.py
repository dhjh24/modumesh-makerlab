"""Mesh Inspector plugin — analyze STL/GLB files for printability.

Reports manifold state, dimensions, wall thickness risk, overhang risk,
and separate shells. Optionally repairs non-manifold meshes.
"""

from __future__ import annotations

import math
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from modumesh_plugin_sdk import PluginContext

_VERSION = "1.0.0"


def run(ctx: "PluginContext") -> None:
    """Analyze a mesh file for printability and optionally repair it."""
    import trimesh

    ctx.set_progress(5, "loading mesh")

    source_job_id = str(ctx.input.get("source_job_id", "")).strip()
    filename = str(ctx.input.get("filename", "model.stl")).strip()
    min_wall = float(ctx.input.get("wall_thickness_mm", 0.8))
    max_overhang = float(ctx.input.get("overhang_angle", 45))
    attempt_repair = bool(ctx.input.get("attempt_repair", True))

    if not source_job_id:
        raise ValueError("source_job_id is required")

    # Read the source STL from the job's output directory
    work_dir = Path(ctx.work_dir)
    source_path = work_dir / filename

    # For a real implementation, the SDK would provide access to other
    # jobs' output files.  Here we accept the stl as passed-in file data.
    if not source_path.is_file():
        # Try downloading from MinIO via the API
        raise ValueError(
            f"source file '{filename}' not found at {source_path}. "
            "In production, the SDK fetches artifacts by job_id."
        )

    mesh = trimesh.load(str(source_path))
    if mesh.is_empty:
        raise ValueError(f"'{filename}' appears to be an empty mesh")

    ctx.set_progress(15, "checking manifold state")

    # ── Manifold check ────────────────────────────────────────────
    is_watertight = mesh.is_watertight
    is_volume = mesh.is_volume
    try:
        is_trimesh_body_count = hasattr(mesh, "body_count")
        if is_trimesh_body_count:
            body_count = mesh.body_count
        else:
            body_count = 0
    except (ImportError, ModuleNotFoundError, AttributeError):
        body_count = 0

    if body_count == 0 and not is_watertight:
        body_count = trimesh.repair.broken_faces(mesh)
        if hasattr(trimesh, "repair"):
            try:
                trimesh.repair.fill_holes(mesh)
            except Exception:
                pass

    manifold_issues: list[str] = []
    if not is_watertight:
        manifold_issues.append("Mesh is not watertight — may need repair")
    if not is_volume:
        manifold_issues.append("Mesh has no volume (open surface)")
    if body_count > 1:
        manifold_issues.append(f"Mesh has {body_count} separate bodies — consider connection")

    ctx.set_progress(30, "measuring dimensions")

    # ── Dimensions ────────────────────────────────────────────────
    bbox = mesh.bounds
    extents = mesh.extents
    dimensions = {
        "x_mm": round(extents[0], 2),
        "y_mm": round(extents[1], 2),
        "z_mm": round(extents[2], 2),
    }

    ctx.set_progress(45, "analyzing wall thickness risk")

    # ── Wall thickness (approximate via sampling) ────────────────
    wall_risk: list[str] = []
    if is_watertight:
        try:
            # Sample random points and measure thickness via ray tests
            samples = 200
            pts = trimesh.sample.sample_surface(mesh, samples)[0]
            # Ray test from sample inward
            inward = -mesh.face_normals[
                trimesh.proximity.closest_point(mesh, pts)[2]
            ]
            origins = pts + inward * 0.01
            directions = -inward
            locations, _, _ = mesh.ray.intersects_location(
                ray_origins=origins, ray_directions=directions
            )
            if len(locations) > 10:
                # Estimate thickness from ray intersection distances
                dists = _estimate_thickness(mesh, pts, samples)
                thin = [d for d in dists if d < min_wall]
                if thin:
                    pct = len(thin) / len(dists) * 100
                    wall_risk.append(
                        f"{pct:.0f}% of sampled points have wall thickness "
                        f"below {min_wall}mm (minimum: {min(dists):.2f}mm)"
                    )
        except Exception:
            pass

    ctx.set_progress(60, "analyzing overhangs")

    # ── Overhang analysis ─────────────────────────────────────────
    overhang_risk: list[str] = []
    try:
        face_normals = mesh.face_normals
        if face_normals is not None and len(face_normals) > 0:
            # Z-up overhang: faces with normal pointing > max_overhang from vertical
            angle_threshold = math.radians(max_overhang)
            cos_threshold = math.cos(angle_threshold)
            angles = face_normals[:, 2]  # dot with (0,0,1)
            overhang_faces = angles < cos_threshold
            overhang_pct = overhang_faces.sum() / len(face_normals) * 100
            if overhang_pct > 5:
                overhang_risk.append(
                    f"{overhang_pct:.0f}% of faces exceed {max_overhang}° overhang — "
                    "may need supports or part rotation"
                )
    except Exception:
        pass

    ctx.set_progress(75, f"repairing (watertight={is_watertight})")

    # ── Repair ────────────────────────────────────────────────────
    repaired = False
    if attempt_repair and (not is_watertight or body_count > 1):
        try:
            trimesh.repair.fill_holes(mesh)
            repaired = mesh.is_watertight
            if repaired:
                repaired_stl = work_dir / "repaired.stl"
                mesh.export(str(repaired_stl), file_type="stl")
                ctx.register_output("repaired.stl")
        except Exception:
            pass

    # ── Summary ───────────────────────────────────────────────────
    ctx.set_progress(90, "writing report")

    triangle_count = len(mesh.faces)
    vertex_count = len(mesh.vertices)
    surface_area = mesh.area if hasattr(mesh, "area") else 0
    mesh_volume = mesh.volume if hasattr(mesh, "volume") else 0

    report: dict[str, Any] = {
        "schema_version": "1",
        "plugin_id": "mesh-inspector",
        "plugin_version": _VERSION,
        "source": {
            "filename": filename,
            "source_job_id": source_job_id,
        },
        "mesh": {
            "vertex_count": vertex_count,
            "triangle_count": triangle_count,
            "is_watertight": is_watertight,
            "is_volume": is_volume,
            "separate_bodies": int(body_count),
            "surface_area_mm2": round(float(surface_area), 2),
            "volume_mm3": round(float(mesh_volume), 3),
        },
        "dimensions_mm": dimensions,
        "risks": {
            "manifold_issues": manifold_issues,
            "wall_thickness": wall_risk,
            "overhang": overhang_risk,
        },
        "repair": {
            "attempted": attempt_repair,
            "was_repaired": repaired,
            "repaired_stl_available": repaired,
        },
        "print_verdict": "pass" if (
            is_watertight and not wall_risk
        ) else "warning" if not manifold_issues else "fail",
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    ctx.write_json("inspection-report.json", report)
    ctx.set_progress(100, "inspection complete")


def _estimate_thickness(mesh, sample_pts, n: int) -> list[float]:
    """Estimate wall thickness via ray intersection (approximate).

    Uses trimesh's ray intersection without scipy. Returns a single
    average thickness value or 999 if estimation fails.
    """
    dists: list[float] = []
    try:
        closest = trimesh.proximity.closest_point(mesh, sample_pts)
        inward = -mesh.face_normals[closest[2]]
        origins = closest[0] + inward * 0.01
        _, hit_locations, _ = mesh.ray.intersects_location(
            ray_origins=origins, ray_directions=inward * -1
        )
        if len(hit_locations) > 0 and len(closest[0]) > 0:
            # Average distance as proxy
            from numpy import mean
            avg_dist = mean(
                [abs(float((hit_locations[i] - closest[0][i % len(closest[0])]).sum()))
                 for i in range(min(len(hit_locations), 50))]
            )
            dists.append(max(avg_dist, 0.1))
    except Exception:
        pass
    return dists if dists else [999.0]
