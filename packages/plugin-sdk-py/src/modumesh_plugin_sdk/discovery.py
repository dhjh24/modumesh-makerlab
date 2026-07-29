"""Plugin directory discovery with duplicate diagnostics."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from modumesh_plugin_sdk.errors import CompatibilityError, ContractError, ManifestError
from modumesh_plugin_sdk.manifest import LoadedPlugin, load_plugin_directory


@dataclass
class DiscoveryIssue:
    path: str
    message: str
    severity: str = "error"  # error | warning


@dataclass
class DiscoveryResult:
    plugins: list[LoadedPlugin] = field(default_factory=list)
    issues: list[DiscoveryIssue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any(i.severity == "error" for i in self.issues)


def discover_plugins(plugin_root: str | Path) -> DiscoveryResult:
    """Scan plugin_root for plugin.manifest.json directories.

    Duplicate (id, version) pairs are reported as errors and excluded.
    Invalid / incompatible plugins are reported with clear diagnostics.
    """
    root = Path(plugin_root).resolve()
    result = DiscoveryResult()
    if not root.is_dir():
        result.issues.append(
            DiscoveryIssue(path=str(root), message="Plugin root does not exist or is not a directory")
        )
        return result

    loaded: list[tuple[Path, LoadedPlugin]] = []
    for manifest_path in sorted(root.glob("*/plugin.manifest.json")):
        plugin_dir = manifest_path.parent
        try:
            plugin = load_plugin_directory(plugin_dir)
            loaded.append((plugin_dir, plugin))
            for diag in plugin.diagnostics:
                result.issues.append(
                    DiscoveryIssue(path=str(plugin_dir), message=diag, severity="warning")
                )
        except (ManifestError, CompatibilityError, ContractError) as exc:
            result.issues.append(DiscoveryIssue(path=str(plugin_dir), message=str(exc)))
        except Exception as exc:  # noqa: BLE001 — surface unexpected discovery failures
            result.issues.append(
                DiscoveryIssue(path=str(plugin_dir), message=f"Unexpected discovery error: {exc}")
            )

    # Duplicate id/version detection
    seen: dict[tuple[str, str], Path] = {}
    for plugin_dir, plugin in loaded:
        key = (plugin.plugin_id, plugin.version)
        if key in seen:
            result.issues.append(
                DiscoveryIssue(
                    path=str(plugin_dir),
                    message=(
                        f"Duplicate plugin id/version '{plugin.plugin_id}@{plugin.version}' "
                        f"(also found at {seen[key]}). Both copies are excluded until resolved."
                    ),
                )
            )
            # Mark the first as well if not already
            first = seen[key]
            result.issues.append(
                DiscoveryIssue(
                    path=str(first),
                    message=(
                        f"Duplicate plugin id/version '{plugin.plugin_id}@{plugin.version}' "
                        f"(conflict with {plugin_dir}). Excluded."
                    ),
                )
            )
            seen[key] = first  # keep first path
            # Remove any previously accepted copy
            result.plugins = [
                p
                for p in result.plugins
                if not (p.plugin_id == plugin.plugin_id and p.version == plugin.version)
            ]
            continue
        seen[key] = plugin_dir
        result.plugins.append(plugin)

    return result


def find_plugin(
    plugin_root: str | Path,
    plugin_id: str,
    version: Optional[str] = None,
) -> Optional[LoadedPlugin]:
    """Find a discovered plugin by id (and optional version). Latest semver-ish string match if omitted."""
    discovered = discover_plugins(plugin_root)
    matches = [p for p in discovered.plugins if p.plugin_id == plugin_id]
    if version is not None:
        for p in matches:
            if p.version == version:
                return p
        return None
    if not matches:
        return None
    # Lexicographic semver works for zero-padded-free x.y.z
    return sorted(matches, key=lambda p: tuple(int(x) for x in p.version.split(".")[:3]), reverse=True)[0]
