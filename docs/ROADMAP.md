# MakerLab Plugin-First Delivery Plan

Updated: 2026-07-30

## Product direction

MakerLab is the workflow platform. CAD engines, mesh tools, slicers, and AI models are replaceable plugins. The web app owns projects, job history, previews, downloads, and user flow. The API and worker own validation, queues, storage, cancellation, audit data, and resource controls.

A user starts from one of three paths:

1. **Describe** — route text or an image to a compatible AI generator.
2. **Upload image** — create a draft mesh, then repair and inspect it.
3. **Customize template** — generate exact geometry from CadQuery or OpenSCAD parameters.

Every successful path ends with a preview, validation report, print estimate, and STL/3MF download. Shop submission stays locked until the model passes the required gates.

## Current baseline

Phases 1–4 already provide the monorepo, plugin SDK, manifest validation, plugin registry, project/job APIs, Redis worker queue, MinIO storage, schema-driven editor, and STL/GLB viewer.

Current generators are limited:

| Item | State |
| --- | --- |
| `fixture-echo` | Test plugin only |
| `fixture-mesh` | Test STL/GLB output only |
| `nameplate` | CadQuery Nameplate (Phase 5) — functional |
| `openscad-template` | OpenSCAD templates (Phase 6) — functional |
| Generator Marketplace | Epic GM-0 through GM-8 |
| Mesh repair and print inspection | Missing |
| Slicing and cost estimate | Missing |
| TripoSR and Hunyuan3D | Missing |
| Shop connector | Missing |

The present deployment has a likely remote-browser failure: `apps/web/Dockerfile` bakes `http://localhost:8000` into `NEXT_PUBLIC_API_URL`. On a phone or another computer, `localhost` points to that device rather than the MakerLab server. The existing Next.js same-origin rewrites can remove that dependency.

## Delivery rules

- Build and merge one phase at a time.
- A phase starts after its dependency gates pass.
- Keep all generation work in queued jobs; never run CAD or model inference inside a web request.
- Record plugin ID, version, runtime, input, outputs, checksums, validation, duration, and failure details on every job.
- Treat uploaded files and plugin code as untrusted input.
- Default plugin network access to denied. Grant a narrow exception only for a documented model-download or hosted-provider need.
- Pin runtime and model versions. Do not fetch an unversioned model during a production job.
- Keep fixture plugins for CI. They must never appear as customer-facing generators in production.
- No ModuMesh Shop submission before the Phase 13 gates pass.

## Phase sequence

| Phase | Scope | State | Depends on | Exit gate |
| --- | --- | --- | --- | --- |
|| 0 | Deployment connectivity and health | **Done** | Phases 1–4 | Remote desktop and phone reach the same API through the web origin |
|| 5 | CadQuery Nameplate | **Done** | Phase 0 | Real STL and STEP files pass contract, API, worker, viewer, and download tests |
|| 6 | OpenSCAD template engine | **Done** | Phase 5 | A second real parametric engine works without frontend-specific forms |
|| GM-0 | Marketplace audit and epic setup | **Active** | Phases 0–6 | ADR committed, CI status recorded, child issues created, roadmap linked |
|| GM-1 | Marketplace contract and catalog API | Planned | GM-0 | Catalog API tests pass, invalid manifests fail, unlicensed plugins quarantined |
|| GM-2 | Generator Marketplace UI | Planned | GM-1 | A user can discover, configure, submit, and inspect a fixture generator without hard-coded page |
|| GM-3 | Logo Light Box MVP | Planned | GM-2 | Golden fixtures reproduce accepted geometry, outputs survive restart, test prints pass fit checks |
|| GM-4 | Artwork tools, multicolor, print checks | Planned | GM-3 | Representative SVG/PNG fixtures generate printable parts, warnings actionable |
|| GM-5 | Projects, pricing, shop handoff | Planned | GM-4 | Saved configuration can reopen and send to draft shop order with no lost options |
|| GM-6 | Community plugin SDK and submission | Planned | GM-5 | Example community generator can be packaged, submitted, reviewed, installed, upgraded, disabled, removed |
|| GM-7 | Starter generator pack | Planned | GM-6 | No generator requires custom catalog, editor, job, or order code |
|| GM-8 | Release hardening | Planned | GM-7 | Security, accessibility, mobile, recovery, observability, and e2e test gates pass in CI |
||| 7 | Mesh repair and print inspector | **Done** | GM-8, Phase 6 | Reports manifold state, dimensions, wall risk, overhang risk, and repair result |
||| 8 | Slicing and cost estimate | **Done** | Phase 7 | Pinned printer profiles produce 3MF, time, filament, and cost estimates |
||| 9 | Generator capability and runtime contract | **Done** | Phase 8 | Local CPU, local GPU, and sidecar plugins share one stable job interface |
||| 10 | TripoSR fast image-to-3D | **Scaffolded** | Phase 9 | Image job yields previewable mesh on the documented GPU tier |
||| 11 | Hunyuan3D quality image-to-3D | **Scaffolded** | Phase 10 | Shape-only tier works first; texture tier is a separate hardware profile |
||| 12 | Compare mode and runtime routing | **Active** | Phase 11 | One input can run on two generators, with clear cost and hardware controls |
||| 13 | ModuMesh Shop connector | **Active** | Phase 12 | Only approved, priced, printable versions can enter the cart |
||| 14 | Community plugin release controls | **Active** | Phase 13 | Signed packages, compatibility checks, quotas, and admin controls are active |

## Phase 0 — Deployment connectivity and health

### Scope

- Stop baking `http://localhost:8000` into the production frontend image.
- Use same-origin `/api/v1/*` and `/backend-health` routes in the browser by default.
- Keep `API_INTERNAL_URL=http://api:8000` for server-side rewrites inside Docker.
- Permit an explicit public API URL only as an opt-in deployment setting.
- Add a visible service-health panel for web, API, database, Redis, MinIO, worker heartbeat, and plugin discovery.
- Separate “browser cannot reach API” from “API is reachable but a dependency is unhealthy.”
- Document local, LAN, and reverse-proxy examples. Do not suggest changing to port 8002 unless that port is truly published and routed.

### Tests

- Unit tests for browser and server API base selection.
- Compose smoke test through the web origin, not direct port 8000.
- Playwright checks on desktop and mobile viewports.
- Reverse-proxy test with no public API port exposed.

### Exit gate

A phone on the same LAN and a remote browser using the public site can load projects, plugins, job status, and backend health without referencing their own `localhost`.

## Phase 5 — CadQuery Nameplate

### Scope

- Replace the empty `plugins/nameplate` stub with a complete manifest, JSON Schema, implementation, fixtures, tests, and documentation.
- Support text, width, height, thickness, corner radius, text depth, hole mode, hole diameter, margin, font choice from an allowlist, and units in millimeters.
- Generate STL for printing, STEP for editing, GLB for preview, and JSON metadata.
- Pin a supported CadQuery release and its runtime dependencies.
- Reject blank text, unsafe paths, unsupported fonts, impossible dimensions, and output that exceeds limits.

### Exit gate

The contract CLI, API job flow, worker, file storage, viewer, downloads, and CI all pass using a real generated nameplate.

## Phase 6 — OpenSCAD template engine

### Scope

- Add an `openscad-template` plugin with a pinned headless OpenSCAD runtime.
- Start with a storage box or organizer template to prove exact dimensions and conditional options.
- Pass values through generated definitions or a safe parameter file; never concatenate raw user script text.
- Export STL plus metadata. Add 3MF or GLB only through a tested conversion step.
- Record OpenSCAD version, template version, command arguments, duration, and stderr diagnostics.

### Exit gate

A new OpenSCAD template can be added by manifest, schema, and template files without editing the frontend.

## Phase 7 — Mesh repair and print inspector

### Scope

- Add post-processing jobs that can consume prior STL, OBJ, or GLB outputs.
- Report triangle count, bounds, volume, manifold state, watertight state, degenerate faces, inverted normals, disconnected shells, wall-thickness risk, overhang risk, and build-volume fit.
- Add conservative repair with before/after artifacts and no silent replacement of the source file.
- Use Manifold where it fits its documented guarantees; add a fallback tool only after test fixtures show a clear need.
- Define score bands: blocked, warning, and print-ready. Keep the underlying measurements visible.

### Exit gate

Known-good and known-bad fixture meshes produce deterministic reports, and repaired output never replaces the original artifact.

## Phase 8 — Slicing and cost estimate

### Scope

- Add a slicer sidecar using a pinned Bambu Studio CLI build or another reviewed slicer backend behind the same interface.
- Store versioned printer, nozzle, filament, and process profiles.
- Produce 3MF, preview data when available, print time, filament length, filament mass, purge waste, and estimated material cost.
- Make price assumptions editable by an administrator and show them in every estimate.
- Apply timeouts, file-size limits, output limits, and safe argument handling.

### Exit gate

A validated STL can be sliced with at least one Bambu printer profile and one generic profile, with repeatable estimates in CI fixtures.

## Phase 9 — Generator capability and runtime contract

### Scope

Extend the current manifest contract without breaking Phase 3 plugins. Add capability fields for:

- input modalities: text, image, parameters, or mesh;
- output formats and texture support;
- print-ready claim;
- CPU, RAM, GPU type, and VRAM request;
- local process or internal sidecar execution;
- health and capability checks;
- model/license metadata;
- estimated time and optional credit cost.

Use one MakerLab-facing job API. Internal sidecars may expose `/health`, `/capabilities`, `/generate`, `/jobs/{id}`, and `/jobs/{id}/cancel`, but the browser never talks to them directly.

### Exit gate

Fixture, CadQuery, OpenSCAD, repair, and slicer plugins continue working under the updated contract, and a fake GPU sidecar passes failure, timeout, progress, cancel, and retry tests.

## Phase 10 — TripoSR fast image-to-3D

### Scope

- Add an isolated TripoSR sidecar for single-image reconstruction.
- Pin code, weights, Python, PyTorch, and CUDA versions.
- Validate image type, dimensions, size, alpha handling, and orientation.
- Produce a mesh plus generation metadata, then pass it through Phase 7 inspection.
- Publish a CPU-disabled or slow-development mode separately from the supported GPU profile.

The official project documents about 6 GB VRAM for its default single-image path and an MIT license. Recheck both before merging the integration.

### Exit gate

A versioned fixture image produces a repeatable mesh artifact, progress can be cancelled, failures are readable, and the print inspector runs automatically.

## Phase 11 — Hunyuan3D quality image-to-3D

### Scope

- Add Hunyuan3D as a separate GPU sidecar; do not install it into the general worker image.
- Ship shape generation first. Add texture generation as a second runtime profile.
- Pin weights and dependencies, cache models outside ephemeral job directories, and verify model checksums at startup.
- Add a license review record for code and weights before distribution or hosted use.
- Document hardware tiers in the admin UI.

The official Hunyuan3D 2.1 repository lists about 10 GB VRAM for shape, 21 GB for texture, and 29 GB for both together. Treat these as planning figures and benchmark the target machine.

### Exit gate

Shape-only generation passes on the documented tier. Texture generation cannot be selected on an undersized worker.

## Phase 12 — Compare mode and runtime routing

### Scope

- Let a user submit one image to two compatible generators and compare results side by side.
- Show generator version, duration, queue time, VRAM tier, inspection score, dimensions, file size, and estimated cost.
- Add routing policies for CPU, GPU, local, hosted, disabled, busy, and insufficient-memory states.
- Add per-user concurrency and spending limits before parallel model jobs are enabled.
- Make the winning output an explicit saved project version.

### Exit gate

Cancelling one comparison child does not corrupt the other, resource limits are enforced, and the selected output keeps full provenance.

## Phase 13 — ModuMesh Shop connector

### Scope

- Create a separate connector package for MakerLab-to-shop calls.
- Send an immutable approved artifact ID, preview, dimensions, material/profile choice, print time, material estimate, price breakdown, and checksum.
- Create a signed quote with an expiration time. Recalculate after model, material, profile, or quantity changes.
- Block cart submission for failed inspection, missing slice data, unavailable printer profile, or expired quote.
- Keep payment, tax, inventory, and order state in the commerce platform rather than MakerLab.

### Exit gate

A test order traces from project version to approved artifact, slice profile, quote, cart line, and production file with matching checksums.

## Phase 14 — Community plugin release controls

### Scope

- Package plugins with a signed manifest, checksums, license record, changelog, compatibility range, and reproducible build reference.
- Add install, update, disable, rollback, and quarantine operations for administrators.
- Scan packages for secrets, unsafe paths, executable surprises, oversized files, and disallowed network policy.
- Add publisher identity, review state, usage quotas, runtime quotas, logs, and kill switches.
- Keep third-party plugins disabled until an administrator approves them.

### Exit gate

An administrator can install a sample external plugin, run its contract suite, activate it, roll it back, and quarantine it without changing MakerLab source.

## Deferred model: TRELLIS.2

Keep TRELLIS.2 outside the committed delivery path for now. Its official repository currently calls for Linux, CUDA 12.4, and at least 24 GB NVIDIA VRAM. A July 2026 repository issue reports a missing license file. Do not distribute or host it as a product feature until legal review, license clarity, a reproducible build, and target-GPU benchmarks are complete.

## Reference projects

- CadQuery: https://github.com/CadQuery/cadquery
- OpenSCAD: https://github.com/openscad/openscad
- Manifold: https://github.com/elalish/manifold
- TripoSR: https://github.com/VAST-AI-Research/TripoSR
- Hunyuan3D 2.1: https://github.com/tencent-hunyuan/hunyuan3d-2.1
- TRELLIS.2: https://github.com/microsoft/TRELLIS.2
- Bambu Studio CLI: https://github.com/bambulab/BambuStudio/wiki/Command-Line-Usage
