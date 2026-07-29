"""Geometry and regression tests for the Nameplate CadQuery plugin."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from nameplate.export import export_stl, render_thumbnail_png, stl_to_glb
from nameplate.geometry import build_nameplate
from nameplate.mesh_validate import validate_mesh
from nameplate.params import validate_params
from nameplate.plugin import run

pytest.importorskip("cadquery")
pytest.importorskip("trimesh")

DEFAULT = {
    "text": "MAKERLAB",
    "font": "DejaVuSans",
    "width_mm": 80,
    "height_mm": 30,
    "base_thickness_mm": 3,
    "text_depth_mm": 1.2,
    "mode": "raised",
    "corner_radius_mm": 2,
    "alignment": "center",
    "hole_count": 2,
    "hole_diameter_mm": 3.2,
    "edge_margin_mm": 8,
}

# Volume envelope for the default raised plate (mm³).
DEFAULT_VOLUME_MIN = 7200.0
DEFAULT_VOLUME_MAX = 7800.0
DEFAULT_FACE_MIN = 800
DEFAULT_FACE_MAX = 8000


@pytest.fixture()
def default_params():
    return validate_params(DEFAULT)


def test_default_geometry_volume_and_faces(default_params, tmp_path: Path):
    solid = build_nameplate(default_params)
    stl = tmp_path / "model.stl"
    export_stl(solid, stl)
    mesh = stl_to_glb(stl, tmp_path / "model.glb")
    report = validate_mesh(mesh, stl_path=stl, params=default_params)
    assert report["passed"]
    assert report["watertight"] is True
    assert DEFAULT_VOLUME_MIN <= report["volume_mm3"] <= DEFAULT_VOLUME_MAX
    assert DEFAULT_FACE_MIN <= report["triangle_count"] <= DEFAULT_FACE_MAX
    assert abs(report["dimensions_mm"]["x"] - 80.0) < 0.5
    assert abs(report["dimensions_mm"]["y"] - 30.0) < 0.5
    assert report["dimensions_mm"]["z"] == pytest.approx(4.2, abs=0.15)


def test_raised_text_increases_height(default_params, tmp_path: Path):
    solid = build_nameplate(default_params)
    export_stl(solid, tmp_path / "r.stl")
    mesh = stl_to_glb(tmp_path / "r.stl", tmp_path / "r.glb")
    z = mesh.extents[2]
    assert z > default_params.base_thickness_mm + 0.5


def test_engraved_mode_reduces_volume(tmp_path: Path):
    raised = validate_params(DEFAULT)
    engraved = validate_params({**DEFAULT, "mode": "engraved", "text_depth_mm": 0.8})
    for label, params in (("raised", raised), ("engraved", engraved)):
        solid = build_nameplate(params)
        export_stl(solid, tmp_path / f"{label}.stl")
    import trimesh

    vr = trimesh.load(str(tmp_path / "raised.stl"), force="mesh").volume
    ve = trimesh.load(str(tmp_path / "engraved.stl"), force="mesh").volume
    assert ve < vr
    assert ve > 0


@pytest.mark.parametrize("hole_count", [0, 1, 2, 4])
def test_hole_counts_build(hole_count: int, tmp_path: Path):
    payload = {
        **DEFAULT,
        "hole_count": hole_count,
        "edge_margin_mm": 10 if hole_count == 4 else 8,
        "corner_radius_mm": 1 if hole_count == 4 else 2,
    }
    params = validate_params(payload)
    solid = build_nameplate(params)
    export_stl(solid, tmp_path / "h.stl")
    assert (tmp_path / "h.stl").stat().st_size > 1000


def test_unicode_supported_by_dejavu(tmp_path: Path):
    params = validate_params({**DEFAULT, "text": "Café Ångström", "hole_count": 0})
    solid = build_nameplate(params)
    export_stl(solid, tmp_path / "u.stl")
    mesh = stl_to_glb(tmp_path / "u.stl", tmp_path / "u.glb")
    report = validate_mesh(mesh, stl_path=tmp_path / "u.stl", params=params)
    assert report["passed"]
    assert report["volume_mm3"] > params.width_mm * params.height_mm * params.base_thickness_mm


def test_min_max_dimension_builds(tmp_path: Path):
    for payload in (
        {
            **DEFAULT,
            "width_mm": 40,
            "height_mm": 20,
            "base_thickness_mm": 1.5,
            "text_depth_mm": 0.4,
            "corner_radius_mm": 0,
            "hole_count": 0,
            "text": "MIN",
        },
        {
            **DEFAULT,
            "width_mm": 200,
            "height_mm": 100,
            "base_thickness_mm": 8,
            "text_depth_mm": 2.5,
            "mode": "raised",
            "corner_radius_mm": 5,
            "hole_count": 0,
            "text": "MAX",
        },
    ):
        params = validate_params(payload)
        solid = build_nameplate(params)
        export_stl(solid, tmp_path / f"{payload['text']}.stl")
        assert (tmp_path / f"{payload['text']}.stl").stat().st_size > 500


def test_deterministic_stl_checksum(default_params, tmp_path: Path):
    solid = build_nameplate(default_params)
    a = tmp_path / "a.stl"
    b = tmp_path / "b.stl"
    export_stl(solid, a)
    export_stl(solid, b)
    assert hashlib.sha256(a.read_bytes()).digest() == hashlib.sha256(b.read_bytes()).digest()


def test_thumbnail_snapshot_nonempty(default_params, tmp_path: Path):
    solid = build_nameplate(default_params)
    export_stl(solid, tmp_path / "m.stl")
    mesh = stl_to_glb(tmp_path / "m.stl", tmp_path / "m.glb")
    png = tmp_path / "thumbnail.png"
    render_thumbnail_png(mesh, png)
    data = png.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    assert len(data) > 500


def test_plugin_entrypoint_emits_all_outputs(tmp_path: Path):
    from modumesh_plugin_sdk.context import PluginContext

    declared = {
        "model.stl": "model/stl",
        "model.step": "model/step",
        "model.glb": "model/gltf-binary",
        "thumbnail.png": "image/png",
        "metadata.json": "application/json",
    }
    ctx = PluginContext(
        job_id="test-job-version-1",
        plugin_id="nameplate",
        plugin_version="1.0.0",
        input=dict(DEFAULT),
        work_dir=tmp_path,
        _declared_outputs=declared,
        _max_output_bytes=16_777_216,
    )
    run(ctx)
    names = {o.relative_path for o in ctx.registered_outputs}
    assert names == set(declared)
    meta = json.loads((tmp_path / "metadata.json").read_text())
    assert meta["plugin_version"] == "1.0.0"
    assert meta["project_version"] == "test-job-version-1"
    assert meta["validation"]["passed"] is True
    assert meta["validation"]["checksum_sha256"]
    assert meta["units"] == "mm"
