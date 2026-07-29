"""Manifest loading and structural validation."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from modumesh_plugin_sdk.constants import (
    CURRENT_SDK_VERSION,
    MANIFEST_SCHEMA_VERSION,
    SDK_COMPAT_MAJOR,
    SUPPORTED_ENGINES,
)
from modumesh_plugin_sdk.errors import CompatibilityError, ManifestError
from modumesh_plugin_sdk.validation import (
    load_schema_resource,
    validate_input_schema_document,
    validate_input_payload,
)


def _manifest_validator() -> Draft202012Validator:
    schema = load_schema_resource("manifest.v1.json")
    return Draft202012Validator(schema)


@dataclass(frozen=True)
class OutputDecl:
    name: str
    media_type: str
    required: bool = True


@dataclass
class LoadedPlugin:
    """A plugin directory that passed contract validation."""

    root: Path
    manifest: dict[str, Any]
    input_schema: dict[str, Any]
    outputs: list[OutputDecl] = field(default_factory=list)
    diagnostics: list[str] = field(default_factory=list)

    @property
    def plugin_id(self) -> str:
        return str(self.manifest["id"])

    @property
    def version(self) -> str:
        return str(self.manifest["version"])

    @property
    def sdk_version(self) -> str:
        return str(self.manifest["sdkVersion"])

    @property
    def engine(self) -> str:
        return str(self.manifest["engine"])

    @property
    def entrypoint(self) -> str:
        return str(self.manifest["entrypoint"])

    @property
    def timeout_seconds(self) -> int:
        return int(self.manifest["timeoutSeconds"])

    @property
    def memory_mb(self) -> int:
        return int(self.manifest["memoryMb"])

    @property
    def network_policy(self) -> str:
        return str(self.manifest.get("networkPolicy", "deny"))

    @property
    def max_input_bytes(self) -> int:
        return int(self.manifest.get("maxInputBytes", 65_536))

    @property
    def max_output_bytes(self) -> int:
        return int(self.manifest.get("maxOutputBytes", 1_048_576))

    @property
    def categories(self) -> list[str]:
        return list(self.manifest.get("categories") or [])

    @property
    def name(self) -> str:
        return str(self.manifest["name"])

    @property
    def description(self) -> str:
        return str(self.manifest.get("description") or "")

    @property
    def src_path(self) -> Path:
        candidate = self.root / "src"
        return candidate if candidate.is_dir() else self.root


def check_sdk_compatibility(sdk_version: str) -> None:
    """Raise CompatibilityError if sdk_version is not host-compatible."""
    parts = sdk_version.split(".")
    if len(parts) < 1 or not parts[0].isdigit():
        raise CompatibilityError(f"Invalid sdkVersion '{sdk_version}'")
    major = int(parts[0])
    if major != SDK_COMPAT_MAJOR:
        raise CompatibilityError(
            f"Incompatible SDK version '{sdk_version}': host supports "
            f"major {SDK_COMPAT_MAJOR}.x (current {CURRENT_SDK_VERSION})"
        )


def validate_manifest_dict(manifest: dict[str, Any]) -> list[str]:
    """Validate a manifest dict. Returns non-fatal diagnostics; raises on hard errors."""
    validator = _manifest_validator()
    errors = sorted(validator.iter_errors(manifest), key=lambda e: list(e.path))
    if errors:
        messages = [f"{'/'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}" for e in errors]
        raise ManifestError("Invalid plugin manifest:\n- " + "\n- ".join(messages))

    if str(manifest.get("schemaVersion")) != MANIFEST_SCHEMA_VERSION:
        raise CompatibilityError(
            f"Unsupported manifest schemaVersion '{manifest.get('schemaVersion')}' "
            f"(expected '{MANIFEST_SCHEMA_VERSION}')"
        )

    check_sdk_compatibility(str(manifest["sdkVersion"]))

    if manifest.get("engine") not in SUPPORTED_ENGINES:
        raise CompatibilityError(
            f"Unsupported engine '{manifest.get('engine')}'; "
            f"supported={sorted(SUPPORTED_ENGINES)}"
        )

    diagnostics: list[str] = []
    if manifest.get("networkPolicy") == "allow":
        diagnostics.append(
            "networkPolicy=allow is discouraged; host still blocks credentials and Docker socket"
        )
    return diagnostics


def _resolve_input_schema(root: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    raw = manifest["inputSchema"]
    if isinstance(raw, dict):
        schema = raw
    elif isinstance(raw, str):
        path = (root / raw).resolve()
        if not str(path).startswith(str(root.resolve())):
            raise ManifestError(f"inputSchema path escapes plugin directory: {raw}")
        if not path.is_file():
            raise ManifestError(f"inputSchema file not found: {raw}")
        schema = json.loads(path.read_text(encoding="utf-8"))
    else:
        raise ManifestError("inputSchema must be an object or relative .json path")

    validate_input_schema_document(schema)
    return schema


def load_plugin_directory(path: str | Path) -> LoadedPlugin:
    """Load and validate a plugin from its directory."""
    root = Path(path).resolve()
    if not root.is_dir():
        raise ManifestError(f"Plugin path is not a directory: {root}")

    manifest_path = root / "plugin.manifest.json"
    if not manifest_path.is_file():
        raise ManifestError(f"Missing plugin.manifest.json in {root}")

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ManifestError(f"Malformed plugin.manifest.json: {exc}") from exc

    if not isinstance(manifest, dict):
        raise ManifestError("plugin.manifest.json must be a JSON object")

    diagnostics = validate_manifest_dict(manifest)
    input_schema = _resolve_input_schema(root, manifest)

    outputs = [
        OutputDecl(
            name=o["name"],
            media_type=o["mediaType"],
            required=bool(o.get("required", True)),
        )
        for o in manifest["outputs"]
    ]

    return LoadedPlugin(
        root=root,
        manifest=manifest,
        input_schema=input_schema,
        outputs=outputs,
        diagnostics=diagnostics,
    )


def validate_job_input(plugin: LoadedPlugin, payload: Any) -> None:
    """Validate a job input payload against the plugin input schema and size limits."""
    validate_input_payload(plugin.input_schema, payload, max_bytes=plugin.max_input_bytes)
