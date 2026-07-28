"""Filesystem and environment security helpers for plugin execution."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Mapping

from modumesh_plugin_sdk.constants import BLOCKED_ENV_KEYS, BLOCKED_ENV_PREFIXES
from modumesh_plugin_sdk.errors import PluginSecurityError

_SAFE_FILE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


def assert_safe_relative_file(name: str) -> str:
    """Reject path separators and traversal in declared output names."""
    if not name or not _SAFE_FILE.match(name):
        raise PluginSecurityError(
            f"Illegal output filename '{name}': must be a single path segment "
            "matching [A-Za-z0-9._-]+"
        )
    if name in {".", ".."}:
        raise PluginSecurityError(f"Illegal output filename '{name}'")
    return name


def resolve_under(base: Path, *parts: str) -> Path:
    """Resolve parts under base; raise on path traversal."""
    base_resolved = base.resolve()
    candidate = base_resolved.joinpath(*parts).resolve()
    try:
        candidate.relative_to(base_resolved)
    except ValueError as exc:
        raise PluginSecurityError(
            f"Path escapes approved job directory: {candidate}"
        ) from exc
    return candidate


def _is_blocked_env_key(key: str) -> bool:
    upper = key.upper()
    if upper in BLOCKED_ENV_KEYS:
        return True
    return any(upper.startswith(prefix) for prefix in BLOCKED_ENV_PREFIXES)


def sanitize_environ(
    source: Mapping[str, str] | None = None,
    *,
    strip_proxy: bool = True,
) -> dict[str, str]:
    """Strip database/storage/credential variables from a subprocess environment."""
    env = dict(source if source is not None else os.environ)
    cleaned: dict[str, str] = {}
    proxy_keys = {"HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY", "http_proxy", "https_proxy"}
    for key, value in env.items():
        if _is_blocked_env_key(key):
            continue
        if strip_proxy and key in proxy_keys:
            continue
        cleaned[key] = value
    cleaned.pop("DOCKER_HOST", None)
    cleaned.pop("DOCKER_SOCK", None)
    return cleaned


def apply_memory_limit_mb(memory_mb: int) -> None:
    """Best-effort address-space limit for the current process (Unix)."""
    try:
        import resource
    except ImportError:
        return
    bytes_limit = max(32, int(memory_mb)) * 1024 * 1024
    soft, hard = resource.getrlimit(resource.RLIMIT_AS)
    new_hard = hard if hard > 0 else bytes_limit
    new_soft = min(bytes_limit, new_hard) if new_hard > 0 else bytes_limit
    try:
        resource.setrlimit(resource.RLIMIT_AS, (new_soft, new_hard if new_hard > 0 else new_soft))
    except (ValueError, OSError):
        pass


def install_network_deny_hooks() -> None:
    """Monkey-patch socket creation to deny network access in-process."""
    import socket

    def _blocked(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        raise PluginSecurityError("Network access denied by plugin networkPolicy=deny")

    socket.socket = _blocked  # type: ignore[misc, assignment]
    if hasattr(socket, "create_connection"):
        socket.create_connection = _blocked  # type: ignore[misc, assignment]


def assert_no_docker_socket(path: Path | str = "/var/run/docker.sock") -> None:
    """Refuse to run when Docker control plane is exposed to the plugin env.

    Presence of the host socket file alone is not fatal (developer laptops often
    have /var/run/docker.sock). We fail when the process environment clearly
    exposes Docker control (DOCKER_HOST) — compose must not set this for workers.
    """
    if os.environ.get("DOCKER_HOST") or os.environ.get("DOCKER_SOCK"):
        raise PluginSecurityError(
            "Docker control environment is visible to the plugin; refusing to run"
        )
    # Optional hard mode for locked-down containers
    if os.environ.get("MODUMESH_DENY_DOCKER_SOCK") == "1" and Path(path).exists():
        raise PluginSecurityError(
            "Docker socket is visible and MODUMESH_DENY_DOCKER_SOCK=1; refusing to run"
        )
