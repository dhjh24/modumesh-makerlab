"""Unit tests for plugin manifest validation and discovery."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from modumesh_plugin_sdk.discovery import discover_plugins
from modumesh_plugin_sdk.errors import CompatibilityError, ManifestError, PluginSecurityError
from modumesh_plugin_sdk.manifest import load_plugin_directory, validate_manifest_dict
from modumesh_plugin_sdk.runner import run_plugin_inprocess
from modumesh_plugin_sdk.security import assert_safe_relative_file, resolve_under, sanitize_environ


FIXTURE_PLUGIN = Path(__file__).resolve().parents[3] / "plugins" / "fixture-echo"


def test_fixture_echo_loads():
    plugin = load_plugin_directory(FIXTURE_PLUGIN)
    assert plugin.plugin_id == "fixture-echo"
    assert plugin.version == "1.0.0"
    assert plugin.network_policy == "deny"


def test_incompatible_sdk_rejected():
    manifest = json.loads((FIXTURE_PLUGIN / "plugin.manifest.json").read_text())
    manifest["sdkVersion"] = "2.0.0"
    with pytest.raises(CompatibilityError):
        validate_manifest_dict(manifest)


def test_invalid_manifest_rejected():
    with pytest.raises(ManifestError):
        validate_manifest_dict({"id": "x"})


def test_path_traversal_rejected(tmp_path: Path):
    with pytest.raises(PluginSecurityError):
        assert_safe_relative_file("../etc/passwd")
    with pytest.raises(PluginSecurityError):
        resolve_under(tmp_path, "..", "outside.txt")


def test_sanitize_environ_strips_credentials():
    cleaned = sanitize_environ(
        {
            "PATH": "/usr/bin",
            "POSTGRES_PASSWORD": "secret",
            "MINIO_SECRET_KEY": "secret",
            "REDIS_HOST": "redis",
            "HOME": "/home/plugin",
        }
    )
    assert "PATH" in cleaned
    assert "HOME" in cleaned
    assert "POSTGRES_PASSWORD" not in cleaned
    assert "MINIO_SECRET_KEY" not in cleaned
    assert "REDIS_HOST" not in cleaned


def test_fixture_echo_run(tmp_path: Path):
    plugin = load_plugin_directory(FIXTURE_PLUGIN)
    result = run_plugin_inprocess(
        plugin,
        job_id="test-job",
            input_payload={"message": "hello", "tag": "fixture"},
        work_dir=tmp_path,
        check_docker_socket=False,
    )
    names = {o.relative_path for o in result.outputs}
    assert names == {"echo.json", "note.txt"}
    echo = json.loads((tmp_path / "echo.json").read_text())
    assert echo["message"] == "hello"


def test_undeclared_output_fails(tmp_path: Path):
    plugin = load_plugin_directory(FIXTURE_PLUGIN)

    def bad_entrypoint(ctx):
        (ctx.work_dir / "sneaky.bin").write_bytes(b"nope")
        ctx.register_output("sneaky.bin", media_type="application/octet-stream")

    # Swap entrypoint by monkeypatching import — use context directly
    from modumesh_plugin_sdk.context import PluginContext
    from modumesh_plugin_sdk.errors import PluginSecurityError as PSE

    ctx = PluginContext(
        job_id="j",
        plugin_id=plugin.plugin_id,
        plugin_version=plugin.version,
        input={},
        work_dir=tmp_path,
        _declared_outputs={o.name: o.media_type for o in plugin.outputs},
    )
    (tmp_path / "sneaky.bin").write_bytes(b"x")
    with pytest.raises(PSE):
        ctx.register_output("sneaky.bin")


def test_discover_plugins_finds_fixture():
    root = FIXTURE_PLUGIN.parent
    result = discover_plugins(root)
    ids = {p.plugin_id for p in result.plugins}
    assert "fixture-echo" in ids
