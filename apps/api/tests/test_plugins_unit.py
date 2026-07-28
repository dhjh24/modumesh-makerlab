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


def test_nameplate_placeholder_has_no_manifest():
    # Nameplate is Phase 5 — must not appear as a runnable plugin yet.
    nameplate = PLUGIN_ROOT / "nameplate"
    assert nameplate.is_dir()
    assert not (nameplate / "plugin.manifest.json").exists()
    loaded = load_plugin_directory(PLUGIN_ROOT / "fixture-echo")
    assert loaded.engine == "python"
