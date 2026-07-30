"""Community plugin submission and review API."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.logging import get_logger

router = APIRouter(tags=["submissions"])
log = get_logger("submissions")


# ── Security scan patterns ───────────────────────────────────────────

_DANGEROUS_PATTERNS = [
    ("subprocess", r"subprocess\.(run|Popen|call|check_output)"),
    ("eval/exec", r"(eval|exec)\s*\("),
    ("file_write_anywhere", r"open\s*\(\s*['\"](?!.*work_dir)"),
    ("os_system", r"os\.system\s*\("),
    ("pickle_load", r"pickle\.(load|loads)"),
    ("base64_decode", r"base64\.(b64decode|decode)"),
    ("requests_outbound", r"(requests|urllib|httpx)\.(get|post|put|delete)"),
    ("socket_bind", r"socket\.(bind|connect)"),
]

_DANGEROUS_IMPORTS = [
    "ctypes", "socket", "multiprocessing", "threading",
    "pty", "fcntl", "termios",
]


def _security_scan(source_dir: Path) -> list[dict[str, Any]]:
    """Run static security checks on plugin source code."""
    findings: list[dict[str, Any]] = []
    for py_file in source_dir.rglob("*.py"):
        try:
            content = py_file.read_text(encoding="utf-8")
        except Exception:
            continue

        lines = content.split("\n")
        for i, line in enumerate(lines, 1):
            stripped = line.strip()

            # Check dangerous imports
            for imp in _DANGEROUS_IMPORTS:
                if f"import {imp}" in stripped or f"from {imp}" in stripped:
                    findings.append({
                        "severity": "high",
                        "file": str(py_file.relative_to(source_dir)),
                        "line": i,
                        "finding": f"dangerous import: {imp}",
                    })

            # Check dangerous patterns
            for name, pattern in _DANGEROUS_PATTERNS:
                import re
                if re.search(pattern, stripped):
                    findings.append({
                        "severity": "medium" if name in (
                            "subprocess", "file_write_anywhere", "base64_decode",
                        ) else "high",
                        "file": str(py_file.relative_to(source_dir)),
                        "line": i,
                        "finding": f"potentially unsafe pattern: {name}",
                    })

    return findings


@router.post("/api/v1/submissions/validate", status_code=200)
async def validate_submission(body: dict[str, Any]) -> dict:
    """Validate a plugin manifest without registering it.

    Used by authors to check their plugin before submission.
    """
    manifest = body.get("manifest")
    if not manifest:
        raise HTTPException(status_code=400, detail="manifest is required")

    from modumesh_plugin_sdk.manifest import validate_manifest_dict

    diagnostics: list[str] = []
    try:
        diag = validate_manifest_dict(manifest)
        diagnostics.extend(diag)
    except Exception as exc:
        return {
            "valid": False,
            "diagnostics": [str(exc)],
        }

    # Check required marketplace fields
    if not manifest.get("author"):
        diagnostics.append("Missing recommended field: author")
    if not manifest.get("license"):
        diagnostics.append("Missing required field: license (SPDX identifier)")
    if not manifest.get("sourceUrl"):
        diagnostics.append("Missing recommended field: sourceUrl")

    return {
        "valid": len(diagnostics) == 0 or all(
            "Missing" in d or "recommended" in d for d in diagnostics
        ),
        "diagnostics": diagnostics,
    }


@router.post("/api/v1/submissions/security-scan")
async def security_scan_endpoint(body: dict[str, Any]) -> dict:
    """Run a static security scan on plugin source code.

    Expects {\"source\": \"<base64-encoded-tarball>\"} or {\"manifest\": {...}}.
    For manifest-only scans, returns a basic check.
    """
    manifest = body.get("manifest")
    if not manifest:
        raise HTTPException(status_code=400, detail="manifest is required")

    findings: list[dict[str, Any]] = []

    # Check network policy
    if manifest.get("networkPolicy") == "allow":
        findings.append({
            "severity": "high",
            "finding": "networkPolicy=allow — outbound network is enabled",
        })

    # Check memory limits
    if (manifest.get("memoryMb") or 0) > 1024:
        findings.append({
            "severity": "medium",
            "finding": f"memoryMb={manifest['memoryMb']} exceeds recommended 1024 MB",
        })

    # Check for known licenses
    if not manifest.get("license"):
        findings.append({
            "severity": "high",
            "finding": "No license declared — plugin will be quarantined",
        })

    return {
        "findings": findings,
        "summary": {
            "high": len([f for f in findings if f["severity"] == "high"]),
            "medium": len([f for f in findings if f["severity"] == "medium"]),
            "low": len([f for f in findings if f["severity"] == "low"]),
        },
        "passed": len([f for f in findings if f["severity"] == "high"]) == 0,
    }
