"""Parameter bounds and cross-field validation for the Nameplate plugin."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

# Keep wall / join safety constants in one place for geometry + tests.
MIN_ENGRAVE_REMAINING_MM = 0.8
MIN_HOLE_WALL_MM = 1.5
RAISED_JOIN_OVERLAP_MM = 0.05
TEXT_SIZE_RATIO = 0.42  # font size relative to plate height


class ParameterError(ValueError):
    """Raised when inputs fail Nameplate bounds or cross-field rules."""


@dataclass(frozen=True)
class NameplateParams:
    text: str
    font: str
    width_mm: float
    height_mm: float
    base_thickness_mm: float
    text_depth_mm: float
    mode: str
    corner_radius_mm: float
    alignment: str
    hole_count: int
    hole_diameter_mm: float
    edge_margin_mm: float

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _num(payload: Mapping[str, Any], key: str) -> float:
    raw = payload[key]
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise ParameterError(f"{key} must be a number")
    return float(raw)


def _int(payload: Mapping[str, Any], key: str) -> int:
    raw = payload[key]
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise ParameterError(f"{key} must be an integer")
    return int(raw)


def validate_params(payload: Mapping[str, Any]) -> NameplateParams:
    """Validate JSON-schema-shaped input plus geometric cross-field rules."""
    text = payload.get("text")
    if not isinstance(text, str):
        raise ParameterError("text must be a string")
    text = text.strip()
    if not text:
        raise ParameterError("text must not be empty")
    if len(text) > 48:
        raise ParameterError("text exceeds maximum length of 48 characters")

    font = payload.get("font")
    if font not in {"DejaVuSans", "FreeSans"}:
        raise ParameterError("font must be one of: DejaVuSans, FreeSans")

    mode = payload.get("mode")
    if mode not in {"raised", "engraved"}:
        raise ParameterError("mode must be 'raised' or 'engraved'")

    alignment = payload.get("alignment")
    if alignment not in {"left", "center", "right"}:
        raise ParameterError("alignment must be left, center, or right")

    width = _num(payload, "width_mm")
    height = _num(payload, "height_mm")
    thickness = _num(payload, "base_thickness_mm")
    depth = _num(payload, "text_depth_mm")
    radius = _num(payload, "corner_radius_mm")
    hole_count = _int(payload, "hole_count")
    hole_diameter = _num(payload, "hole_diameter_mm")
    edge_margin = _num(payload, "edge_margin_mm")

    if not 40.0 <= width <= 200.0:
        raise ParameterError("width_mm must be between 40 and 200")
    if not 20.0 <= height <= 100.0:
        raise ParameterError("height_mm must be between 20 and 100")
    if not 1.5 <= thickness <= 8.0:
        raise ParameterError("base_thickness_mm must be between 1.5 and 8")
    if not 0.4 <= depth <= 3.0:
        raise ParameterError("text_depth_mm must be between 0.4 and 3")
    if not 0.0 <= radius <= 20.0:
        raise ParameterError("corner_radius_mm must be between 0 and 20")
    if hole_count < 0 or hole_count > 4:
        raise ParameterError("hole_count must be between 0 and 4")
    if not 2.0 <= hole_diameter <= 6.0:
        raise ParameterError("hole_diameter_mm must be between 2 and 6")
    if not 3.0 <= edge_margin <= 20.0:
        raise ParameterError("edge_margin_mm must be between 3 and 20")

    max_radius = min(width, height) / 2.0 - 0.01
    if radius > max_radius:
        raise ParameterError(
            f"corner_radius_mm ({radius}) exceeds plate limit ({max_radius:.2f} mm)"
        )

    if mode == "engraved" and depth > thickness - MIN_ENGRAVE_REMAINING_MM:
        raise ParameterError(
            f"engraving depth {depth} mm would cut through the plate; "
            f"maximum for thickness {thickness} mm is "
            f"{thickness - MIN_ENGRAVE_REMAINING_MM:.2f} mm "
            f"(retaining {MIN_ENGRAVE_REMAINING_MM} mm)"
        )

    if mode == "raised" and depth + thickness > 20.0:
        raise ParameterError("raised text plus thickness exceeds 20 mm overall height")

    if hole_count > 0:
        radius_h = hole_diameter / 2.0
        # Hole center must leave diameter/2 + min wall from every edge.
        min_inset = radius_h + MIN_HOLE_WALL_MM
        if edge_margin < min_inset:
            raise ParameterError(
                f"edge_margin_mm ({edge_margin}) too small for hole_diameter_mm "
                f"{hole_diameter}; need at least {min_inset:.2f} mm"
            )
        usable_w = width - 2.0 * edge_margin
        usable_h = height - 2.0 * edge_margin
        if usable_w < hole_diameter or usable_h < hole_diameter:
            raise ParameterError("mounting holes do not fit inside the plate with edge margin")

        if hole_count >= 2 and usable_w < hole_diameter + MIN_HOLE_WALL_MM:
            raise ParameterError("plate too narrow for multiple mounting holes")

        # Corner fillets must not collide with corner-placed holes.
        if hole_count == 4 and radius > edge_margin - radius_h:
            raise ParameterError(
                "corner_radius_mm conflicts with corner mounting holes; "
                "reduce radius or increase edge_margin_mm"
            )

    return NameplateParams(
        text=text,
        font=str(font),
        width_mm=width,
        height_mm=height,
        base_thickness_mm=thickness,
        text_depth_mm=depth,
        mode=str(mode),
        corner_radius_mm=radius,
        alignment=str(alignment),
        hole_count=hole_count,
        hole_diameter_mm=hole_diameter,
        edge_margin_mm=edge_margin,
    )
