"""Subprocess entrypoint for sandboxed plugin execution.

Invoked as: python -m modumesh_plugin_sdk.execute <request.json>
Never receives database or object-storage credentials.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from modumesh_plugin_sdk.errors import ContractError, PluginSecurityError, PluginTimeoutError
from modumesh_plugin_sdk.manifest import load_plugin_directory
from modumesh_plugin_sdk.runner import enforce_declared_outputs, run_plugin_inprocess
from modumesh_plugin_sdk.security import assert_no_docker_socket


def main(argv: list[str] | None = None) -> None:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1:
        print("usage: python -m modumesh_plugin_sdk.execute <request.json>", file=sys.stderr)
        raise SystemExit(2)

    request_path = Path(args[0])
    request = json.loads(request_path.read_text(encoding="utf-8"))
    plugin_root = Path(request["plugin_root"])
    work_dir = Path(request["work_dir"])
    result_path = Path(request["result_path"])

    try:
        assert_no_docker_socket()
        plugin = load_plugin_directory(plugin_root)
        result = run_plugin_inprocess(
            plugin,
            job_id=str(request["job_id"]),
            input_payload=request.get("input") or {},
            work_dir=work_dir,
            timeout_seconds=int(request.get("timeout_seconds") or plugin.timeout_seconds),
            check_docker_socket=False,  # already checked above
        )
        enforce_declared_outputs(plugin, result.outputs)
        payload = {
            "ok": True,
            "outputs": [
                {
                    "name": o.relative_path,
                    "media_type": o.media_type,
                    "size_bytes": o.size_bytes,
                    "path": str(o.absolute_path),
                }
                for o in result.outputs
            ],
            "logs": [{"level": lvl, "message": msg} for lvl, msg in result.logs],
        }
    except (PluginTimeoutError, PluginSecurityError, ContractError) as exc:
        payload = {"ok": False, "error": str(exc), "error_type": type(exc).__name__}
    except Exception as exc:  # noqa: BLE001
        payload = {"ok": False, "error": str(exc), "error_type": "Exception"}

    result_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    raise SystemExit(0 if payload.get("ok") else 1)


if __name__ == "__main__":
    main()
