"""Security helpers for the ModuMesh MakerLab API.

Fail-closed admin authentication (``require_admin``) and SVG sanitization
(``sanitize_svg``) live here so router modules can share them without
circular imports.
"""
