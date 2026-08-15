"""Content-Disposition header injection tests (GM-12 D1.5, audit L2).

The download endpoint must never interpolate a user-controlled filename into
the Content-Disposition header with CR/LF or quote characters intact — that
would allow response header injection.
"""

from __future__ import annotations

from uuid import UUID

from app.routers.files import _safe_download_filename

FILE_ID = UUID("f705ad2c-8c1b-4d8f-a630-4d95ad866b44")


class TestSafeDownloadFilename:
    def test_plain_filename_unchanged(self) -> None:
        assert _safe_download_filename("enclosure.stl", FILE_ID) == "enclosure.stl"

    def test_crlf_stripped(self) -> None:
        evil = "enclosure.stl\r\nX-Injected: 1"
        result = _safe_download_filename(evil, FILE_ID)
        assert "\r" not in result
        assert "\n" not in result
        assert result == "enclosure.stlX-Injected: 1"

    def test_quote_stripped(self) -> None:
        # A quote would terminate the quoted filename= parameter early.
        result = _safe_download_filename('enclosure"style.stl', FILE_ID)
        assert '"' not in result
        assert result == "enclosurestyle.stl"

    def test_all_control_chars_stripped(self) -> None:
        result = _safe_download_filename("a\x00b\x1fc.stl", FILE_ID)
        assert "\x00" not in result
        assert "\x1f" not in result
        assert result == "abc.stl"

    def test_empty_filename_falls_back_to_model_id(self) -> None:
        assert _safe_download_filename("", FILE_ID) == f"model-{FILE_ID}"

    def test_control_only_filename_falls_back_with_extension(self) -> None:
        # Extension survives sanitization even when the name part is all control.
        result = _safe_download_filename("\r\n\r\n.stl", FILE_ID)
        assert result == f"model-{FILE_ID}.stl"

    def test_filename_never_empty_or_whitespace(self) -> None:
        for evil in ["   ", "\r\n", "\x00\x07\x1b"]:
            result = _safe_download_filename(evil, FILE_ID)
            assert result
            assert result == result.strip()
            assert result.startswith("model-")
