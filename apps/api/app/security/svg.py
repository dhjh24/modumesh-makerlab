"""SVG sanitization for untrusted SVG content (plugin submissions, uploads).

Rejects SVG documents that contain scriptable or external-resource content:

* ``<script>`` elements
* event-handler attributes (``on*``)
* ``DOCTYPE`` declarations and internal/external entity declarations (XXE)
* ``<foreignObject>`` / ``<iframe>`` embedding
* external ``href`` / ``xlink:href`` references (http:, https:, protocol-
  relative ``//``, ``data:``, ``javascript:``, ``vbscript:``)

This module is deliberately stdlib-only (``re``): no XML parser is used, so
XXE and entity-expansion ("billion laughs") attacks are structurally
impossible. The check is fail-closed — a suspicious document raises
``ValueError`` with a human-readable reason and is never returned.
"""

from __future__ import annotations

import re

_DOCTYPE_RE = re.compile(r"<!DOCTYPE\b[^>]*>", re.IGNORECASE | re.DOTALL)
_ENTITY_RE = re.compile(r"<!ENTITY\b[^>]*>", re.IGNORECASE | re.DOTALL)
_SCRIPT_TAG_RE = re.compile(r"<script\b[^>]*>.*?</script>", re.IGNORECASE | re.DOTALL)
_SCRIPT_OPEN_RE = re.compile(r"<script\b", re.IGNORECASE)
_FOREIGN_OBJECT_RE = re.compile(r"<foreignObject\b", re.IGNORECASE)
_IFRAME_RE = re.compile(r"<iframe\b", re.IGNORECASE)
_EVENT_ATTR_RE = re.compile(r"\son[a-z]+\s*=", re.IGNORECASE)
# External / dangerous URI schemes on href / xlink:href. Relative references
# (e.g. href="#defs", href="/assets/x.svg") are allowed.
_EXTERNAL_HREF_RE = re.compile(
    r"(?:\shref|xlink:href)\s*=\s*[\"'](?:https?:|//|data:|javascript:|vbscript:)",
    re.IGNORECASE,
)


def sanitize_svg(svg_text: str) -> str:
    """Validate that *svg_text* is a safe, script-free SVG document.

    Raises:
        ValueError: with a reason on the first detected attack vector.

    Returns:
        The input unchanged when it is benign (no rewriting — callers may
        store the returned string as-is).
    """
    if not isinstance(svg_text, str) or not svg_text.strip():
        raise ValueError("SVG content is empty")

    if _DOCTYPE_RE.search(svg_text):
        raise ValueError("SVG contains a DOCTYPE declaration (XXE risk)")
    if _ENTITY_RE.search(svg_text):
        raise ValueError("SVG contains an entity declaration (XXE risk)")
    if _SCRIPT_TAG_RE.search(svg_text) or _SCRIPT_OPEN_RE.search(svg_text):
        raise ValueError("SVG contains a <script> element")
    if _FOREIGN_OBJECT_RE.search(svg_text):
        raise ValueError("SVG contains a <foreignObject> element")
    if _IFRAME_RE.search(svg_text):
        raise ValueError("SVG contains an <iframe> element")
    if _EVENT_ATTR_RE.search(svg_text):
        raise ValueError("SVG contains an event-handler attribute (on*)")
    if _EXTERNAL_HREF_RE.search(svg_text):
        raise ValueError("SVG contains an external href/xlink:href reference")

    return svg_text
