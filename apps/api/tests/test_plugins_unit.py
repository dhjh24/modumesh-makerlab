"""API unit tests for plugin contract helpers (no live stack)."""

from __future__ import annotations

from pathlib import Path

from modumesh_plugin_sdk.discovery import discover_plugins
from modumesh_plugin_sdk.manifest import load_plugin_directory


ROOT = Path(__file__).resolve().parents[3]
PLUGIN_ROOT = ROOT / "plugins"


def test_discover_fixture_echo_from_repo_plugins():
    result = discover_plugins(PLUGIN_ROOT)
    assert any(p.plugin_id == "fixture-echo" for p in result.plugins)


def test_nameplate_plugin_loads():
    nameplate = load_plugin_directory(PLUGIN_ROOT / "nameplate")
    assert nameplate.plugin_id == "nameplate"
    assert nameplate.version == "1.0.0"
    assert nameplate.engine == "python"
    names = {o.name for o in nameplate.outputs}
    assert "model.stl" in names
    assert "model.glb" in names
    assert "thumbnail.png" in names


def test_discover_includes_nameplate():
    result = discover_plugins(PLUGIN_ROOT)
    assert any(p.plugin_id == "nameplate" for p in result.plugins)
