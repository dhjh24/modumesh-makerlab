"""JSON Schema helpers for manifests and generator inputs."""

from __future__ import annotations

import json
from importlib import resources
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError, ValidationError

from modumesh_plugin_sdk.errors import ContractError, ManifestError


def load_schema_resource(name: str) -> dict[str, Any]:
    package = resources.files("modumesh_plugin_sdk").joinpath("schemas", name)
    with package.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def validate_input_schema_document(schema: dict[str, Any]) -> None:
    """Ensure a plugin's input schema obeys MakerLab input-rules.v1."""
    rules = load_schema_resource("input-rules.v1.json")
    validator = Draft202012Validator(rules)
    errors = sorted(validator.iter_errors(schema), key=lambda e: list(e.path))
    if errors:
        messages = [f"{'/'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}" for e in errors]
        raise ManifestError("Input schema violates MakerLab rules:\n- " + "\n- ".join(messages))

    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        raise ManifestError(f"Input schema is not a valid JSON Schema: {exc.message}") from exc


def validate_input_payload(
    schema: dict[str, Any],
    payload: Any,
    *,
    max_bytes: int,
) -> None:
    """Validate job input against the plugin schema and byte budget."""
    encoded = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    if len(encoded) > max_bytes:
        raise ContractError(
            f"Input payload exceeds maxInputBytes ({len(encoded)} > {max_bytes})"
        )

    validator = Draft202012Validator(schema)
    try:
        validator.validate(payload)
    except ValidationError as exc:
        path = "/".join(str(p) for p in exc.absolute_path) or "<root>"
        raise ContractError(f"Input validation failed at {path}: {exc.message}") from exc
