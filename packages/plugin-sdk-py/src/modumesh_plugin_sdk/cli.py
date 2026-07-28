"""Contract test CLI for plugin authors (`modumesh-plugin-check`)."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

from modumesh_plugin_sdk.discovery import discover_plugins
from modumesh_plugin_sdk.errors import CompatibilityError, ContractError, ManifestError
from modumesh_plugin_sdk.manifest import load_plugin_directory, validate_job_input
from modumesh_plugin_sdk.runner import enforce_declared_outputs, run_plugin_inprocess


def _cmd_check(args: argparse.Namespace) -> int:
    path = Path(args.path).resolve()
    print(f"Checking plugin at {path}")
    try:
        plugin = load_plugin_directory(path)
    except (ManifestError, CompatibilityError, ContractError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    print(f"  id={plugin.plugin_id} version={plugin.version} sdk={plugin.sdk_version}")
    print(f"  engine={plugin.engine} entrypoint={plugin.entrypoint}")
    print(f"  outputs={[o.name for o in plugin.outputs]}")
    for diag in plugin.diagnostics:
        print(f"  WARN: {diag}")

    sample_input: dict = {}
    if args.input:
        sample_input = json.loads(Path(args.input).read_text(encoding="utf-8"))
    else:
        # Minimal object — may fail schema; that's OK for --no-run
        sample_input = {}

    if not args.no_run:
        try:
            validate_job_input(plugin, sample_input)
        except ContractError as exc:
            if args.input:
                print(f"FAIL: input invalid: {exc}", file=sys.stderr)
                return 1
            # Without --input, invent defaults from schema if possible
            props = (plugin.input_schema.get("properties") or {})
            required = set(plugin.input_schema.get("required") or [])
            sample_input = {}
            for name, schema in props.items():
                if name not in required and not args.require_all:
                    continue
                t = schema.get("type")
                if t == "string":
                    sample_input[name] = schema.get("default", "fixture")
                elif t == "integer":
                    sample_input[name] = schema.get("default", 1)
                elif t == "number":
                    sample_input[name] = schema.get("default", 1.0)
                elif t == "boolean":
                    sample_input[name] = schema.get("default", False)
                elif t == "object":
                    sample_input[name] = schema.get("default", {})
                elif t == "array":
                    sample_input[name] = schema.get("default", [])
                else:
                    sample_input[name] = schema.get("default", None)
            try:
                validate_job_input(plugin, sample_input)
            except ContractError as exc:
                print(
                    f"FAIL: could not synthesize valid input ({exc}). "
                    "Pass --input fixture.json",
                    file=sys.stderr,
                )
                return 1

        with tempfile.TemporaryDirectory(prefix="modumesh-contract-") as tmp:
            try:
                result = run_plugin_inprocess(
                    plugin,
                    job_id="contract-test",
                    input_payload=sample_input,
                    work_dir=Path(tmp),
                    check_docker_socket=False,
                )
                enforce_declared_outputs(plugin, result.outputs)
            except Exception as exc:  # noqa: BLE001
                print(f"FAIL: execution: {exc}", file=sys.stderr)
                return 1
            print(f"  registered={ [o.relative_path for o in result.outputs] }")

    print("PASS")
    return 0


def _cmd_discover(args: argparse.Namespace) -> int:
    result = discover_plugins(args.path)
    for issue in result.issues:
        print(f"{issue.severity.upper()}: {issue.path}: {issue.message}", file=sys.stderr)
    for plugin in result.plugins:
        print(f"{plugin.plugin_id}@{plugin.version}\t{plugin.root}")
    return 0 if result.ok or args.allow_errors else (0 if result.plugins else 1)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="modumesh-plugin-check",
        description="ModuMesh MakerLab plugin contract test CLI",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check", help="Validate a single plugin directory")
    check.add_argument("path", help="Path to plugin directory")
    check.add_argument("--input", help="JSON file used as generator input for a dry run")
    check.add_argument("--no-run", action="store_true", help="Validate manifest/schema only")
    check.add_argument(
        "--require-all",
        action="store_true",
        help="When synthesizing input, include optional properties too",
    )
    check.set_defaults(func=_cmd_check)

    discover = sub.add_parser("discover", help="Scan a plugins root directory")
    discover.add_argument("path", help="Plugins root (contains one directory per plugin)")
    discover.add_argument(
        "--allow-errors",
        action="store_true",
        help="Exit 0 even when some plugins failed validation",
    )
    discover.set_defaults(func=_cmd_discover)

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    code = args.func(args)
    raise SystemExit(code)


if __name__ == "__main__":
    main()
