"""Approved local font resolution for the Nameplate plugin."""

from __future__ import annotations

from pathlib import Path

from nameplate.params import ParameterError

_FONT_FILES = {
    "DejaVuSans": "DejaVuSans.ttf",
    "FreeSans": "FreeSans.ttf",
}

_FONTS_DIR = Path(__file__).resolve().parents[2] / "fonts"


def resolve_font_path(font_id: str) -> Path:
    """Return the absolute path to a bundled approved font."""
    filename = _FONT_FILES.get(font_id)
    if filename is None:
        raise ParameterError(f"unsupported font '{font_id}'")
    path = (_FONTS_DIR / filename).resolve()
    if not path.is_file():
        raise ParameterError(f"approved font file missing: {filename}")
    if not str(path).startswith(str(_FONTS_DIR.resolve())):
        raise ParameterError("font path escapes approved fonts directory")
    return path


def approved_font_ids() -> list[str]:
    return sorted(_FONT_FILES)
