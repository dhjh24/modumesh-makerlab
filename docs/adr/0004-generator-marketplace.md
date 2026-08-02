# ADR-0004: Generator Marketplace and Logo Light Box Plugin

**Status:** Draft

**Date:** 2026-07-30

## Context

The repository has a working plugin SDK (v1), job queue, worker, object storage,
schema-driven editor, and 3D viewer. Phase 5 added CadQuery Nameplate (deterministic
CAD) and Phase 6 added OpenSCAD templates (safe parametric scripts). Both proved
the contract-to-production flow.

We now need a **Generator Marketplace** — a browsable library of parametric 3D
product generators. The first production generator is **Logo Light Box**: a customer
uploads permitted artwork, configures physical and printing options, previews,
generates printable parts, saves the project, and can later send it to ModuMesh Shop.

## Decision

### Manifest evolution (schemaVersion v1 → v2 compatible)

Extend the existing v1 manifest with additive optional fields. Existing Phase 3–6
plugins remain valid without changes.

New fields:

| Field           | Type          | Required | Description                                                                |
| --------------- | ------------- | -------- | -------------------------------------------------------------------------- |
| `author`        | string        | no       | Plugin author name or GitHub handle                                        |
| `license`       | string        | no       | SPDX identifier (e.g. `MIT`, `Apache-2.0`). Omitted = unknown → quarantine |
| `licenseUrl`    | string        | no       | Source URL for the license text                                            |
| `sourceUrl`     | string        | no       | Public source repository URL                                               |
| `maturity`      | string        | no       | `experimental`, `stable`, `deprecated`. Default `experimental`             |
| `capabilities`  | object        | no       | Declares supported features (see below)                                    |
| `tags`          | array[string] | no       | Freeform search tags                                                       |
| `thumbnail`     | string        | no       | Relative path to a PNG/WebP thumbnail inside the plugin directory          |
| `compatibility` | object        | no       | SDK version bounds, worker requirements                                    |

`capabilities` object fields (all optional booleans, default `false`):

| Field           | Meaning                                                     |
| --------------- | ----------------------------------------------------------- |
| `preview`       | Generator produces a preview GLB/PNG before full generation |
| `deterministic` | Same inputs always produce identical geometry               |
| `multipart`     | Output contains multiple printable artifacts                |
| `multicolor`    | Color-separated parts for multi-material printing           |
| `text`          | Accepts text/font input                                     |
| `imageUpload`   | Accepts image/SVG upload                                    |
| `shopReady`     | Output is suitable for manufacturing quotation              |

### Upload handling

- SVG uploads are sanitized (strip scripts, external refs, embedded HTML,
  foreign namespaces). Reject files over 5 MB, dimension over 4096 px.
- PNG uploads are accepted but flagged as "traced — verify artwork".
- Uploaded files are stored in MinIO under the project's immutable job path.
- Customers must confirm they have permission to use uploaded artwork.

### License policy

- `license` field required for public/catalog visibility.
- Plugins with omitted `license` or unrecognized SPDX → `status=quarantined`.
- Quarantined plugins invisible in the marketplace catalog.
- `commercial-use` and `redistribution` inferred from SPDX. Non-commercial
  licenses are flagged on the plugin detail page.

### Execution isolation

- Generator code runs in the existing worker (subprocess runner).
- No outbound network by default (`networkPolicy=deny`).
- Read-only base filesystem, per-job temp work dir, resource limits, timeout.
- SVG sanitization runs **before** the generator receives the file.
- Upload bytes are stored immutably; the job receives a read-only file path.

### Logo Light Box v1 outputs

| File                     | Required | Media type          |
| ------------------------ | -------- | ------------------- |
| `face.stl`               | yes      | `model/stl`         |
| `enclosure.stl`          | yes      | `model/stl`         |
| `back-panel.stl`         | yes      | `model/stl`         |
| `preview.glb`            | yes      | `model/gltf-binary` |
| `thumbnail.png`          | no       | `image/png`         |
| `design.json`            | yes      | `application/json`  |
| `validation-report.json` | yes      | `application/json`  |

### Reproducibility

- Every job records the generator version, SDK version, all normalized input
  parameters, file hashes, generation duration, warnings, and errors.
- The `design.json` output embeds enough data to regenerate the same geometry
  with no external lookups.

### Shop handoff (Phase GM-5)

- The project revision record carries artifact object keys, dimensions,
  material estimate, and price snapshot.
- The Vendure connector receives an opaque artifact set (no private storage
  URLs). MakerLab never exposes signed URLs to the shop system.

## Consequences

- **Positive**: Marketplace is schema-driven. New generators appear after
  directory drop + resync — no frontend code changes for v1.
- **Positive**: License and maturity metadata lets customers filter unsafe or
  unlicensed generators.
- **Positive**: SVG sanitization and private-by-default artwork prevent common
  XSS and data-leak vectors.
- **Negative**: Manifest v2 schema requires the discovery and validation code
  to accept unknown additive fields (backward-compatible).
- **Negative**: GLB preview requires a rendering step after generation; adds
  5–30 seconds to job duration.
- **Negative**: Logo Light Box is the first plugin requiring SVG processing.
  The sanitizer and tracer are new dependencies.
