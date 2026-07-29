"""Unit tests for Nameplate parameter validation."""

from __future__ import annotations

import copy

import pytest

from nameplate.params import ParameterError, validate_params

DEFAULT = {
    "text": "MAKERLAB",
    "font": "DejaVuSans",
    "width_mm": 80,
    "height_mm": 30,
    "base_thickness_mm": 3,
    "text_depth_mm": 1.2,
    "mode": "raised",
    "corner_radius_mm": 2,
    "alignment": "center",
    "hole_count": 2,
    "hole_diameter_mm": 3.2,
    "edge_margin_mm": 8,
}


def test_default_params_ok():
    p = validate_params(DEFAULT)
    assert p.text == "MAKERLAB"
    assert p.mode == "raised"


def test_empty_text_rejected():
    with pytest.raises(ParameterError, match="empty"):
        validate_params({**DEFAULT, "text": ""})
    with pytest.raises(ParameterError, match="empty"):
        validate_params({**DEFAULT, "text": "   "})


def test_overlong_text_rejected():
    with pytest.raises(ParameterError, match="maximum length"):
        validate_params({**DEFAULT, "text": "x" * 49})


def test_min_max_dimensions():
    lo = validate_params(
        {
            **DEFAULT,
            "width_mm": 40,
            "height_mm": 20,
            "base_thickness_mm": 1.5,
            "text_depth_mm": 0.4,
            "corner_radius_mm": 0,
            "hole_count": 0,
        }
    )
    assert lo.width_mm == 40
    hi = validate_params(
        {
            **DEFAULT,
            "width_mm": 200,
            "height_mm": 100,
            "base_thickness_mm": 8,
            "text_depth_mm": 3,
            "mode": "raised",
            "corner_radius_mm": 20,
            "hole_count": 0,
            "edge_margin_mm": 20,
        }
    )
    assert hi.height_mm == 100


def test_engraving_cut_through_rejected():
    with pytest.raises(ParameterError, match="cut through"):
        validate_params(
            {
                **DEFAULT,
                "mode": "engraved",
                "base_thickness_mm": 1.5,
                "text_depth_mm": 1.0,
            }
        )


def test_hole_margin_wall_thickness():
    with pytest.raises(ParameterError, match="edge_margin"):
        validate_params(
            {
                **DEFAULT,
                "hole_count": 2,
                "hole_diameter_mm": 6,
                "edge_margin_mm": 3,
            }
        )


@pytest.mark.parametrize("count", [0, 1, 2, 3, 4])
def test_hole_counts_accepted(count: int):
    payload = copy.deepcopy(DEFAULT)
    payload["hole_count"] = count
    if count == 4:
        payload["edge_margin_mm"] = 10
        payload["corner_radius_mm"] = 1
    validate_params(payload)
