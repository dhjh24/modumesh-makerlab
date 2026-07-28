"""Sandboxed plugin execution context — no DB/storage credentials."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from modumesh_plugin_sdk.errors import PluginSecurityError
from modumesh_plugin_sdk.security import assert_safe_relative_file, resolve_under


ProgressCallback = Callable[[int, Optional[str]], None]
LogCallback = Callable[[str, str], None]


@dataclass
class RegisteredOutput:
    relative_path: str
    absolute_path: Path
    media_type: Optional[str] = None
    size_bytes: int = 0


@dataclass
class PluginContext:
    """Approved helpers exposed to plugin entrypoints.

    Plugins receive only:
    - job metadata and validated input
    - a writable per-job work directory
    - logging, progress, and file-registration helpers
    """

    job_id: str
    plugin_id: str
    plugin_version: str
    input: dict[str, Any]
    work_dir: Path
    _declared_outputs: dict[str, str] = field(default_factory=dict, repr=False)
    _max_output_bytes: int = field(default=1_048_576, repr=False)
    _on_progress: Optional[ProgressCallback] = field(default=None, repr=False)
    _on_log: Optional[LogCallback] = field(default=None, repr=False)
    _logger: logging.Logger = field(default_factory=lambda: logging.getLogger("plugin"), repr=False)
    _registered: list[RegisteredOutput] = field(default_factory=list, repr=False)
    _total_output_bytes: int = field(default=0, repr=False)

    def log(self, message: str, *, level: str = "info") -> None:
        normalized = (level or "info").lower()
        if self._on_log is not None:
            self._on_log(normalized, message)
        getattr(self._logger, normalized if normalized in {"debug", "info", "warning", "error"} else "info")(
            message
        )

    def set_progress(self, percent: int, message: str | None = None) -> None:
        pct = max(0, min(100, int(percent)))
        if self._on_progress is not None:
            self._on_progress(pct, message)
        else:
            self.log(f"progress {pct}%{': ' + message if message else ''}")

    def path(self, *parts: str) -> Path:
        """Resolve a path under the approved work directory."""
        return resolve_under(self.work_dir, *parts)

    def register_output(
        self,
        relative_path: str,
        *,
        media_type: str | None = None,
    ) -> RegisteredOutput:
        """Register a file produced under the job work directory."""
        name = assert_safe_relative_file(relative_path)
        abs_path = resolve_under(self.work_dir, name)
        if not abs_path.is_file():
            raise PluginSecurityError(f"Registered output does not exist: {name}")

        size = abs_path.stat().st_size
        if self._total_output_bytes + size > self._max_output_bytes:
            raise PluginSecurityError(
                f"Total output exceeds maxOutputBytes "
                f"({self._total_output_bytes + size} > {self._max_output_bytes})"
            )

        declared = self._declared_outputs.get(name)
        if declared is None:
            raise PluginSecurityError(
                f"Undeclared output '{name}'. Declared: {sorted(self._declared_outputs)}"
            )
        effective_type = media_type or declared
        if media_type is not None and media_type != declared:
            raise PluginSecurityError(
                f"Output '{name}' media type '{media_type}' does not match declared '{declared}'"
            )

        record = RegisteredOutput(
            relative_path=name,
            absolute_path=abs_path,
            media_type=effective_type,
            size_bytes=size,
        )
        # Replace prior registration of the same name.
        self._registered = [r for r in self._registered if r.relative_path != name]
        self._registered.append(record)
        self._total_output_bytes = sum(r.size_bytes for r in self._registered)
        return record

    def write_json(self, relative_path: str, data: Any, *, media_type: str = "application/json") -> RegisteredOutput:
        path = self.path(assert_safe_relative_file(relative_path))
        path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return self.register_output(relative_path, media_type=media_type)

    def write_text(self, relative_path: str, text: str, *, media_type: str = "text/plain") -> RegisteredOutput:
        path = self.path(assert_safe_relative_file(relative_path))
        path.write_text(text, encoding="utf-8")
        return self.register_output(relative_path, media_type=media_type)

    @property
    def registered_outputs(self) -> list[RegisteredOutput]:
        return list(self._registered)
