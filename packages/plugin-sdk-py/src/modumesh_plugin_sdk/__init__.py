"""ModuMesh MakerLab plugin SDK (Python).

Host-facing utilities for manifest validation, compatibility checks,
sandboxed plugin context, and the author contract CLI.
"""

from modumesh_plugin_sdk.constants import (
    CURRENT_SDK_VERSION,
    MANIFEST_SCHEMA_VERSION,
    SUPPORTED_ENGINES,
)
from modumesh_plugin_sdk.context import PluginContext, RegisteredOutput
from modumesh_plugin_sdk.errors import (
    CompatibilityError,
    ContractError,
    ManifestError,
    PluginSecurityError,
    PluginTimeoutError,
)
from modumesh_plugin_sdk.manifest import (
    LoadedPlugin,
    load_plugin_directory,
    validate_manifest_dict,
)

__all__ = [
    "CURRENT_SDK_VERSION",
    "MANIFEST_SCHEMA_VERSION",
    "SUPPORTED_ENGINES",
    "PluginContext",
    "RegisteredOutput",
    "CompatibilityError",
    "ContractError",
    "ManifestError",
    "PluginSecurityError",
    "PluginTimeoutError",
    "LoadedPlugin",
    "load_plugin_directory",
    "validate_manifest_dict",
]

__version__ = CURRENT_SDK_VERSION
