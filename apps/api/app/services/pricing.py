"""Pricing and shop handoff service for ModuMesh MakerLab.

Computes final prices from material estimates and generates
Vendure-compatible handoff payloads for shop integration.
"""

from __future__ import annotations

from typing import Any


# ── Pricing rules ─────────────────────────────────────────────────────

# Labor and overhead rates (USD)
LABOR_RATE_PER_HOUR = 30.0
MACHINE_RATE_PER_HOUR = 5.0
MARKUP_PCT = 30.0
SHIPPING_HANDLING_FLAT = 5.0


def calculate_price(
    material_estimate: dict[str, Any] | None,
    *,
    labor_minutes: float = 10,
    margin_pct: float | None = None,
) -> dict[str, Any]:
    """Calculate a final price from a Logo Light Box material estimate.

    Returns a price breakdown with subtotals and total.
    """
    if not material_estimate:
        return {
            "currency": "USD",
            "subtotal_materials": 0,
            "subtotal_labor": 0,
            "subtotal_machine": 0,
            "shipping_handling": 0,
            "markup_pct": 0,
            "markup_amount": 0,
            "total": 0,
            "error": "No material estimate available",
        }

    filament_cost = float(material_estimate.get("filament_cost_usd", 0))
    led_cost = float(material_estimate.get("led_kit_cost_usd", 0))
    material_total = filament_cost + led_cost

    machine_hours = labor_minutes / 60.0
    labor_cost = LABOR_RATE_PER_HOUR * machine_hours
    machine_cost = MACHINE_RATE_PER_HOUR * machine_hours

    subtotal = material_total + labor_cost + machine_cost + SHIPPING_HANDLING_FLAT

    effective_margin = margin_pct if margin_pct is not None else MARKUP_PCT
    markup = subtotal * (effective_margin / 100.0)
    total = subtotal + markup

    return {
        "currency": "USD",
        "price_breakdown": {
            "materials": round(material_total, 2),
            "labor": round(labor_cost, 2),
            "machine_time": round(machine_cost, 2),
            "shipping_handling": SHIPPING_HANDLING_FLAT,
        },
        "markup_pct": effective_margin,
        "markup_amount": round(markup, 2),
        "total": round(total, 2),
        "includes": [
            "Face plate (custom artwork)",
            "LED enclosure",
            "Snap-fit back panel",
            "LED strip/kit",
            "Cable routing",
            "Assembly",
        ],
        "disclaimer": "Final price may vary. Actual shipping calculated at checkout.",
    }


def build_shop_handoff(project: dict[str, Any], job: dict[str, Any], pricing: dict[str, Any]) -> dict[str, Any]:
    """Build a Vendure-compatible shop handoff payload.

    This payload carries artifact references, dimensions, options,
    manufacturing notes, preview URL, and the computed price snapshot.
    No private storage URLs are exposed — only opaque artifact IDs.
    """
    return {
        "schema_version": "1",
        "platform": "modumesh-makerlab",
        "project_id": str(project["id"]),
        "project_name": project.get("name", ""),
        "artifact_ids": [
            str(f["id"])
            for f in (job.get("files") or [])
            if f.get("filename") in ("face.stl", "enclosure.stl", "back-panel.stl")
        ],
        "preview_id": next(
            (str(f["id"]) for f in (job.get("files") or []) if f.get("filename") == "preview.glb"),
            None,
        ),
        "design_id": next(
            (str(f["id"]) for f in (job.get("files") or []) if f.get("filename") == "design.json"),
            None,
        ),
        "options": {
            "generator": str(job.get("plugin_version", "")),
            "artwork_type": str(job.get("input_payload", {}).get("artwork_type", "")),
            "dimensions": {
                "width_mm": job.get("input_payload", {}).get("width"),
                "height_mm": job.get("input_payload", {}).get("height"),
                "depth_mm": job.get("input_payload", {}).get("box_depth"),
            },
            "material": job.get("input_payload", {}).get("material", "PLA"),
        },
        "price": {
            "currency": pricing.get("currency", "USD"),
            "total": pricing.get("total", 0),
            "breakdown": pricing.get("price_breakdown", {}),
        },
        "manufacturing_notes": [
            "Parts are designed for FDM/FFF printing",
            "PLA or PETG recommended for LED compatibility",
            "Snap-fit back panel may require light sanding for smooth fit",
            "LED strip adhesion: use double-sided thermal tape",
            "Diffuser: 2-3mm white acrylic or frosted PETG sheet (customer supplied)",
        ],
        "generated_at": job.get("completed_at") or "",
    }
