"""Typed errors for the plugin contract."""

from __future__ import annotations


class ContractError(Exception):
    """Base class for plugin contract failures."""


class ManifestError(ContractError):
    """Invalid or unreadable plugin manifest."""


class CompatibilityError(ContractError):
    """SDK / engine / schema version incompatibility."""


class PluginSecurityError(ContractError):
    """Path traversal, undeclared output, size, or sandbox violation."""


class PluginTimeoutError(ContractError):
    """Plugin exceeded its declared or job timeout."""
