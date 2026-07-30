"""In-process and subprocess plugin runner with contract enforcement."""

from __future__ import annotations

import importlib
import json
import os
import sys
import tempfile
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

from modumesh_plugin_sdk.context import PluginContext, RegisteredOutput
from modumesh_plugin_sdk.errors import (
    ContractError,
    PluginSecurityError,
    PluginTimeoutError,
)
from modumesh_plugin_sdk.manifest import LoadedPlugin, validate_job_input
from modumesh_plugin_sdk.security import (
    apply_memory_limit_mb,
    assert_no_docker_socket,
    install_network_deny_hooks,
    sanitize_environ,
)


ProgressCallback = Callable[[int, Optional[str]], None]
LogCallback = Callable[[str, str], None]


@dataclass
class RunResult:
    outputs: list[RegisteredOutput]
    work_dir: Path
    logs: list[tuple[str, str]]


def _import_entrypoint(entrypoint: str, src_path: Path):
    if ":" not in entrypoint:
        raise ContractError(f"Invalid entrypoint '{entrypoint}' (expected module:function)")
    module_name, func_name = entrypoint.split(":", 1)
    src = str(src_path.resolve())
    if src not in sys.path:
        sys.path.insert(0, src)
    module = importlib.import_module(module_name)
    func = getattr(module, func_name, None)
    if func is None or not callable(func):
        raise ContractError(f"Entrypoint '{entrypoint}' is not callable")
    return func


def enforce_declared_outputs(plugin: LoadedPlugin, registered: list[RegisteredOutput]) -> None:
    """Ensure required declared outputs were registered; reject extras (already blocked)."""
    have = {r.relative_path: r for r in registered}
    for decl in plugin.outputs:
        if decl.required and decl.name not in have:
            raise PluginSecurityError(f"Required output '{decl.name}' was not registered")
        if decl.name in have and have[decl.name].media_type != decl.media_type:
            raise PluginSecurityError(
                f"Output '{decl.name}' media type mismatch: "
                f"got '{have[decl.name].media_type}', declared '{decl.media_type}'"
            )


def run_plugin_inprocess(
    plugin: LoadedPlugin,
    *,
    job_id: str,
    input_payload: dict[str, Any],
    work_dir: Path | None = None,
    timeout_seconds: int | None = None,
    on_progress: ProgressCallback | None = None,
    on_log: LogCallback | None = None,
    check_docker_socket: bool = True,
    use_thread: bool = False,
) -> RunResult:
    """Execute a plugin entrypoint in-process with sandbox hooks.

    Prefer the subprocess runner for production isolation; this path is used by
    the contract CLI and by the worker when spawning is unavailable.

    When use_thread=False, the plugin runs directly in the current thread.
    This avoids library-loading issues (e.g. VTK shared-object mapping in threads)
    but means timeout must be enforced by the caller (e.g. subprocess timeout).
    """
    validate_job_input(plugin, input_payload)
    effective_timeout = min(
        int(timeout_seconds) if timeout_seconds is not None else plugin.timeout_seconds,
        plugin.timeout_seconds,
    )
    if effective_timeout < 1:
        raise PluginTimeoutError("Timeout must be >= 1 second")

    if check_docker_socket:
        assert_no_docker_socket()

    own_dir = work_dir is None
    tmp: tempfile.TemporaryDirectory[str] | None = None
    if own_dir:
        tmp = tempfile.TemporaryDirectory(prefix=f"modumesh-job-{job_id}-")
        work = Path(tmp.name)
    else:
        assert work_dir is not None
        work = Path(work_dir)
        work.mkdir(parents=True, exist_ok=True)

    logs: list[tuple[str, str]] = []

    def _log(level: str, message: str) -> None:
        logs.append((level, message))
        if on_log:
            on_log(level, message)

    declared = {o.name: o.media_type for o in plugin.outputs}
    ctx = PluginContext(
        job_id=job_id,
        plugin_id=plugin.plugin_id,
        plugin_version=plugin.version,
        input=dict(input_payload),
        work_dir=work.resolve(),
        _declared_outputs=declared,
        _max_output_bytes=plugin.max_output_bytes,
        _on_progress=on_progress,
        _on_log=_log,
    )

    if plugin.network_policy != "allow":
        install_network_deny_hooks()
    apply_memory_limit_mb(plugin.memory_mb)

    # Clear credential env in this process as defense-in-depth for in-process runs.
    for key in list(__import__("os").environ):
        from modumesh_plugin_sdk.security import _is_blocked_env_key

        if _is_blocked_env_key(key):
            __import__("os").environ.pop(key, None)

    func = _import_entrypoint(plugin.entrypoint, plugin.src_path)

    import concurrent.futures

    if use_thread:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(func, ctx)
            try:
                future.result(timeout=effective_timeout)
            except concurrent.futures.TimeoutError as exc:
                raise PluginTimeoutError(
                    f"Plugin exceeded timeout of {effective_timeout}s"
                ) from exc
    else:
        try:
            func(ctx)
        except PluginSecurityError:
            raise
        except ContractError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise ContractError(f"Plugin raised: {exc}\n{traceback.format_exc()}") from exc

    enforce_declared_outputs(plugin, ctx.registered_outputs)
    result = RunResult(outputs=ctx.registered_outputs, work_dir=work, logs=logs)
    # Caller owns cleanup when work_dir was provided; otherwise keep tmp alive via result
    # by not cleaning until caller reads files — copy paths are under work.
    if tmp is not None:
        # Detach: TemporaryDirectory would delete on GC; materialize by not auto-clean.
        tmp._finalizer.detach()  # type: ignore[attr-defined]
    return result


def build_subprocess_env(*, network_allow: bool = False) -> dict[str, str]:
    return sanitize_environ(strip_proxy=not network_allow)


def run_plugin_subprocess(
    plugin: LoadedPlugin,
    *,
    job_id: str,
    input_payload: dict[str, Any],
    work_dir: Path,
    timeout_seconds: int | None = None,
) -> RunResult:
    """Execute a plugin in an isolated subprocess with a sanitized environment."""
    import subprocess

    validate_job_input(plugin, input_payload)
    work = Path(work_dir)
    work.mkdir(parents=True, exist_ok=True)
    effective_timeout = min(
        int(timeout_seconds) if timeout_seconds is not None else plugin.timeout_seconds,
        plugin.timeout_seconds,
    )

    request_path = work / "_request.json"
    result_path = work / "_result.json"
    request_path.write_text(
        json.dumps(
            {
                "job_id": job_id,
                "plugin_root": str(plugin.root),
                "work_dir": str(work),
                "result_path": str(result_path),
                "input": input_payload,
                "timeout_seconds": effective_timeout,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    env = build_subprocess_env(network_allow=(plugin.network_policy == "allow"))
    # Ensure plugin src is importable inside the child.
    pythonpath = env.get("PYTHONPATH", "")
    src = str(plugin.src_path.resolve())
    env["PYTHONPATH"] = src + (os.pathsep + pythonpath if pythonpath else "")

    try:
        completed = subprocess.run(
            [sys.executable, "-m", "modumesh_plugin_sdk.execute", str(request_path)],
            env=env,
            cwd=str(work),
            capture_output=True,
            text=True,
            timeout=effective_timeout + 5,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise PluginTimeoutError(
            f"Plugin exceeded timeout of {effective_timeout}s"
        ) from exc

    if not result_path.is_file():
        raise ContractError(
            "Plugin subprocess produced no result file: "
            f"exit={completed.returncode} stderr={completed.stderr[-2000:]}"
        )

    payload = json.loads(result_path.read_text(encoding="utf-8"))
    if not payload.get("ok"):
        err = payload.get("error") or "plugin failed"
        err_type = payload.get("error_type") or ""
        if err_type == "PluginTimeoutError":
            raise PluginTimeoutError(err)
        if err_type == "PluginSecurityError":
            raise PluginSecurityError(err)
        raise ContractError(err)

    outputs: list[RegisteredOutput] = []
    for item in payload.get("outputs") or []:
        abs_path = Path(item["path"])
        outputs.append(
            RegisteredOutput(
                relative_path=item["name"],
                absolute_path=abs_path,
                media_type=item.get("media_type"),
                size_bytes=int(item.get("size_bytes") or abs_path.stat().st_size),
            )
        )
    enforce_declared_outputs(plugin, outputs)
    logs = [(e.get("level", "info"), e.get("message", "")) for e in payload.get("logs") or []]
    return RunResult(outputs=outputs, work_dir=work, logs=logs)
