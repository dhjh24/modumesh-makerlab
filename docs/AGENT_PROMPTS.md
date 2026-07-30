# MakerLab Phase Implementation Prompts

Updated: 2026-07-30

Use one prompt at a time. Give the next prompt to the coding agent only after the current phase is merged and its exit gate passes. Each prompt requires the agent to work from the repository’s real state rather than assuming earlier work exists.

## Phase 0 prompt — Fix deployment connectivity and health

```text
Work on Phase 0 only in https://github.com/dhjh24/modumesh-makerlab.

Goal:
Fix “Unable to reach the MakerLab API” for deployed desktop and mobile browsers, then add clear service-health reporting. Do not add generators in this phase.

Read before editing:
- README.md
- docs/architecture.md
- docs/development.md
- docs/ROADMAP.md
- apps/web/lib/api.ts
- apps/web/next.config.js
- apps/web/Dockerfile
- infra/compose/docker-compose.yml
- API health routes and configuration

Known risk to verify:
apps/web/Dockerfile currently bakes http://localhost:8000 into NEXT_PUBLIC_API_URL. In a remote browser, localhost points to the user’s device. The repo already has same-origin Next.js rewrites for /api/v1 and /backend-health.

Required work:
1. Reproduce the failure from a browser that is not on the Docker host.
2. Trace the final browser URL used for API calls in local development, Docker Compose, production build, LAN access, and reverse-proxy access.
3. Make same-origin API calls the production default. Keep API_INTERNAL_URL for the Next.js server-to-API hop.
4. Leave a public API URL as an explicit opt-in setting only.
5. Remove hard-coded production localhost values from the web image.
6. Review CORS settings for direct-API deployments without weakening them to a wildcard with credentials.
7. Add a compact health view that distinguishes web reachability, API reachability, database, Redis, MinIO, worker heartbeat, and plugin discovery.
8. Improve the error message so it shows the failed URL, safe diagnostic detail, and correlation ID when present. Never expose secrets.
9. Update .env.example, Compose comments, deployment docs, and troubleshooting steps for local, LAN, and reverse-proxy setups.
10. Do not change the API to port 8002 unless deployment configuration proves that port is published and routed.

Tests and gates:
- Unit-test browser and server API-base selection.
- Add a Compose smoke test that reaches the API through the web origin.
- Add Playwright desktop and mobile checks.
- Test a reverse-proxy case with port 8000 not exposed publicly.
- Run formatting, type checks, API tests, web tests, and the relevant Compose smoke suite.

Delivery:
- Keep changes limited to Phase 0.
- Update docs/ROADMAP.md status and record the verified root cause.
- Open a focused PR with test evidence, deployment examples, screenshots of the health states, and any remaining risk.
- Do not start Phase 5.
```

## Phase 5 prompt — Complete the CadQuery Nameplate plugin

```text
Work on Phase 5 only in https://github.com/dhjh24/modumesh-makerlab after Phase 0 is merged.

Goal:
Replace the empty plugins/nameplate placeholder with the first real print-focused generator. It must run through the existing manifest, API, queue, worker, storage, viewer, and download flow.

Read before editing:
- docs/ROADMAP.md
- docs/plugins.md
- docs/architecture.md
- docs/adr/0003-plugin-contract.md
- fixture plugin implementations and tests
- worker runner and file-upload code
- plugin SDK schemas and contract CLI
- current plugins/nameplate files

Required work:
1. Add a complete plugin.manifest.json, input JSON Schema, Python implementation, packaging, fixtures, and docs.
2. Support text, width, height, thickness, corner radius, text depth, hole mode, hole diameter, margin, approved font, and millimeter units.
3. Generate model.stl, model.step, model.glb, and metadata.json. If GLB conversion needs a new dependency, pin it and cover it with tests.
4. Pin a CadQuery version supported by the worker’s Python version. Record CadQuery and OpenCASCADE/OCP versions in metadata.
5. Use an allowlisted font set packaged with the runtime. Reject font paths supplied by users.
6. Validate blank text, Unicode limits, geometry ranges, conflicting dimensions, file size, timeout, and path handling.
7. Report useful progress stages and cancellation points.
8. Keep the frontend schema-driven. Do not create a nameplate-only form.
9. Preserve source parameters and checksums with the job output.

Tests and gates:
- Contract CLI success and intentional invalid-input failures.
- Geometry tests for bounds, nonzero volume, watertight STL, expected holes, and text depth.
- Worker tests for progress, cancellation, timeout, output limits, and cleanup.
- API integration test from project creation through file download.
- Playwright test that creates, previews, and downloads a nameplate.
- Run formatting, type checks, Python tests, plugin checks, Compose smoke, and web e2e.

Delivery:
- Update docs/ROADMAP.md and docs/plugins.md.
- Add sample output screenshots and measured artifact sizes to the PR.
- State any platform limits for Linux/amd64 and ARM64.
- Do not start Phase 6.
```

## Phase 6 prompt — Add the OpenSCAD template engine

```text
Work on Phase 6 only in https://github.com/dhjh24/modumesh-makerlab after Phase 5 is merged.

Goal:
Add a second real parametric engine using headless OpenSCAD. Prove that new templates can appear through a manifest and JSON Schema with no frontend-specific code.

Read before editing:
- docs/ROADMAP.md
- docs/plugins.md
- completed CadQuery plugin
- plugin runner security controls
- worker image and Compose configuration
- current schema-form limitations

Required work:
1. Add an openscad-template plugin with a pinned OpenSCAD runtime.
2. Ship one useful starter template, preferably a storage box or grid organizer with exact dimensions.
3. Define all user options in JSON Schema with units, defaults, ranges, and friendly labels.
4. Pass parameters through a safe generated definitions file or strict command arguments. Never accept raw user OpenSCAD source.
5. Export STL and metadata. Add preview conversion only through a pinned and tested tool.
6. Record OpenSCAD version, template version, input parameters, safe command arguments, duration, warnings, and output checksums.
7. Apply CPU, memory, timeout, file-size, path, and subprocess controls.
8. Capture stderr into safe job diagnostics with length limits.
9. Document the steps for adding another approved template.

Tests and gates:
- Contract tests for valid and invalid parameters.
- Golden geometry tests for bounds and volume with tolerances.
- Injection tests covering quotes, shell characters, paths, and oversized strings.
- Worker cancellation and timeout tests.
- API and Playwright flow from template selection through preview and download.
- Cross-build check for the supported container architectures.

Delivery:
- Update docs/ROADMAP.md and plugin author guidance.
- Include a second tiny test template in fixtures to prove the extension path.
- Do not start Phase 7.
```

## Phase 7 prompt — Build mesh repair and print inspection

```text
Work on Phase 7 only in https://github.com/dhjh24/modumesh-makerlab after Phase 6 is merged.

Goal:
Add a post-processing pipeline that measures print risks, preserves the original mesh, and can create a separate repaired artifact.

Read before editing:
- docs/ROADMAP.md
- job and file data models
- worker job state machine
- viewer metadata flow
- CadQuery and OpenSCAD outputs
- Manifold project documentation and license

Required work:
1. Define a post-processing job that consumes an immutable prior mesh artifact.
2. Report format, triangle count, bounds, volume, manifold state, watertight state, degenerate faces, inverted normals, disconnected shells, wall-thickness risk, overhang risk, and build-volume fit.
3. Return raw measurements plus blocked, warning, or print-ready status. Do not hide measurements behind one score.
4. Add conservative repair using Manifold where its guarantees fit. Add another tool only when fixtures show a gap.
5. Store original, report, repair log, and repaired mesh as separate linked artifacts.
6. Never mark a mesh repaired if geometry changed beyond configured tolerances without a warning.
7. Add printer build-volume profiles used only for fit checks in this phase.
8. Show the report in the project UI with clear failure and warning states.
9. Trigger inspection automatically after a generator job completes, with an admin setting to disable automatic runs.

Tests and gates:
- Curated fixtures: clean cube, open hole, inverted normals, zero-area faces, multiple shells, thin wall, extreme overhang, and oversized model.
- Deterministic reports for repeat runs.
- Repair tests that compare bounds, volume, shell count, and checksum behavior.
- Security tests for malformed and oversized meshes.
- API, worker, UI, accessibility, and mobile tests.

Delivery:
- Document metric definitions and known limits.
- Update docs/ROADMAP.md with benchmark time and memory for each fixture class.
- Do not start Phase 8.
```

## Phase 8 prompt — Add slicing and cost estimates

```text
Work on Phase 8 only in https://github.com/dhjh24/modumesh-makerlab after Phase 7 is merged.

Goal:
Slice an approved mesh through a pinned backend and return a traceable 3MF, print-time estimate, material estimate, and price inputs.

Read before editing:
- docs/ROADMAP.md
- Phase 7 inspection contract
- job and artifact lineage code
- Bambu Studio CLI documentation
- current worker isolation and subprocess controls

Required work:
1. Create a slicer sidecar or isolated runner behind a MakerLab plugin contract.
2. Pin the slicer version and container digest. Do not use a floating latest image.
3. Add versioned printer, nozzle, filament, and process profiles. Start with one Bambu profile and one generic profile.
4. Accept only approved profile IDs from the server. Do not accept user-supplied filesystem paths or raw slicer arguments.
5. Produce 3MF, slice metadata, print time, filament length, filament mass, purge waste when reported, and material-cost estimate.
6. Store every price input: spool price, spool mass, waste factor, machine-time rate, labor rule, and currency.
7. Add admin controls for profiles and cost assumptions with validation and audit history.
8. Block slicing for failed inspection unless an administrator explicitly overrides it with a recorded reason.
9. Parse CLI output defensively and keep bounded logs.
10. Show estimate assumptions and profile versions in the UI.

Tests and gates:
- Repeat the same fixture and profile to confirm stable estimates within documented tolerance.
- Invalid profile, corrupted mesh, timeout, cancellation, oversized output, and slicer crash tests.
- Command-injection and path-traversal tests.
- End-to-end flow from generated mesh through inspection, slicing, 3MF download, and cost display.

Delivery:
- Add profile-management and cost-formula documentation.
- Record slicer licensing review in the repo.
- Update docs/ROADMAP.md.
- Do not start Phase 9.
```

## Phase 9 prompt — Extend the capability and runtime contract

```text
Work on Phase 9 only in https://github.com/dhjh24/modumesh-makerlab after Phase 8 is merged.

Goal:
Extend the plugin contract for CPU generators, GPU generators, and internal sidecars without breaking existing Phase 3–8 plugins.

Read before editing:
- docs/ROADMAP.md
- docs/plugins.md
- ADR-0003
- TypeScript and Python SDKs
- manifest JSON Schema
- registry sync code
- API job creation and worker execution code
- every active plugin manifest

Required work:
1. Propose and record an ADR for an additive manifest schema or a clean schema-version migration.
2. Add input modalities, output capabilities, texture support, print-ready claim, CPU/RAM/GPU/VRAM requests, execution mode, health checks, model metadata, license metadata, estimated duration, and optional credit cost.
3. Keep one public MakerLab job API. The browser must never call a generator sidecar directly.
4. Define the internal sidecar contract for health, capabilities, generate, status, progress, cancel, and bounded error payloads.
5. Add authentication between worker and sidecars, narrow network rules, request IDs, timeouts, retries, and idempotency.
6. Add scheduler decisions for disabled, unhealthy, busy, incompatible, and insufficient-resource states.
7. Migrate fixture, CadQuery, OpenSCAD, repair, and slicer manifests with compatibility tests.
8. Add a fake GPU sidecar that simulates progress, failure, cancellation, timeout, and output.
9. Keep secrets out of job records, plugin logs, and browser payloads.

Tests and gates:
- Backward-compatibility suite for every existing manifest.
- TypeScript/Python schema parity.
- Sidecar contract tests and failure matrix.
- Scheduler tests for CPU, GPU, VRAM, health, concurrency, and cancellation.
- Integration test with the fake sidecar through the full job flow.

Delivery:
- Update ADR, plugin author guide, architecture, OpenAPI examples, and docs/ROADMAP.md.
- List breaking changes; the expected count is zero for active plugins unless the ADR proves a version bump is needed.
- Do not start Phase 10.
```

## Phase 10 prompt — Integrate TripoSR

```text
Work on Phase 10 only in https://github.com/dhjh24/modumesh-makerlab after Phase 9 is merged.

Goal:
Add a fast single-image-to-3D generator through an isolated TripoSR sidecar and the new runtime contract.

Read before editing:
- docs/ROADMAP.md
- Phase 9 sidecar ADR and contract
- official TripoSR repository, model card, license, and requirements at the commit selected for integration
- Phase 7 inspection pipeline

Required work:
1. Create a separate sidecar image. Do not install TripoSR dependencies into the general worker.
2. Pin the TripoSR commit, model weights, checksums, Python, PyTorch, CUDA, and base-image digest.
3. Record code and weight license details in the plugin metadata.
4. Validate image MIME type, decoded dimensions, pixel count, file size, orientation, alpha behavior, and decompression limits.
5. Add safe defaults and a small approved parameter set. Do not expose arbitrary model arguments.
6. Report download/loading/generation/export progress and support cancellation.
7. Produce a previewable mesh and metadata, then run Phase 7 inspection automatically.
8. Detect unavailable CUDA or low VRAM before accepting a job.
9. Add model-cache startup checks and an offline production mode.
10. Show that AI output is a draft until inspection and user approval.

Tests and gates:
- Versioned fixture images with expected output properties, not fragile byte-for-byte mesh matches.
- Invalid image, huge image, missing weights, checksum mismatch, no GPU, low VRAM, out-of-memory, timeout, cancellation, and sidecar restart tests.
- Full UI flow on desktop and mobile.
- Benchmark target GPU for startup time, peak VRAM, job duration, and artifact size.

Delivery:
- Publish the supported hardware profile and benchmark results.
- Update docs/ROADMAP.md and model/license inventory.
- Do not start Phase 11.
```

## Phase 11 prompt — Integrate Hunyuan3D

```text
Work on Phase 11 only in https://github.com/dhjh24/modumesh-makerlab after Phase 10 is merged.

Goal:
Add a higher-quality Hunyuan3D image-to-3D option as a separate GPU sidecar. Ship shape generation before the larger texture path.

Read before editing:
- docs/ROADMAP.md
- Phase 9 runtime contract
- completed TripoSR sidecar patterns
- official Hunyuan3D 2.1 repository, model cards, code license, weight terms, and requirements at the selected commit

Required work:
1. Complete and commit a code-and-weights license review before enabling the plugin.
2. Create a separate pinned sidecar for shape generation.
3. Add texture generation as a distinct capability and hardware profile, not an automatic step.
4. Pin code, weights, checksums, Python, PyTorch, CUDA, compiled extensions, and base-image digest.
5. Cache models outside job directories and verify checksums at startup.
6. Reject jobs before queueing when no compatible worker has the required VRAM.
7. Validate inputs using the same image safety rules as TripoSR.
8. Produce mesh, optional texture/PBR artifacts, metadata, preview, and automatic Phase 7 inspection.
9. Support progress, cancellation, timeout, out-of-memory recovery, sidecar restart, and bounded logs.
10. Display the selected hardware tier and expected wait time to the user.

Tests and gates:
- Shape-only fixture flow on the supported GPU tier.
- Texture tests on its separate supported tier.
- Missing model, checksum mismatch, compiled-extension failure, low VRAM, out-of-memory, timeout, cancellation, restart, and malformed output tests.
- Benchmarks for cold start, warm start, duration, peak VRAM, RAM, and artifact size.

Delivery:
- Document verified hardware needs rather than copying estimates without testing.
- Update docs/ROADMAP.md and the license/model inventory.
- Do not start Phase 12.
```

## Phase 12 prompt — Build comparison and runtime routing

```text
Work on Phase 12 only in https://github.com/dhjh24/modumesh-makerlab after Phase 11 is merged.

Goal:
Let a user run one image through two compatible generators, compare the outputs, and save one result with full lineage. Add resource-aware routing and limits.

Read before editing:
- docs/ROADMAP.md
- job retry and cancellation rules
- Phase 9 scheduler contract
- TripoSR and Hunyuan3D plugins
- inspection and estimate records

Required work:
1. Add a parent comparison job with independent child jobs.
2. Let users select two compatible generators or accept a server recommendation.
3. Show model version, queue time, generation time, hardware tier, inspection state, dimensions, triangle count, file size, estimated print cost, and preview side by side.
4. Add routing for disabled, unhealthy, busy, local, hosted, CPU, GPU, and insufficient-resource states.
5. Add per-user concurrent-job, daily-job, GPU-minute, storage, and optional spending limits.
6. Keep cancellation independent for each child and provide a cancel-all action.
7. Make output selection explicit and save the chosen child as a project version without deleting the rejected child.
8. Prevent duplicate charges or duplicate generation through idempotency.
9. Add accessible mobile behavior that does not force two tiny 3D canvases beside each other.

Tests and gates:
- Parent and child state-machine tests for mixed success, failure, cancellation, retry, and sidecar restart.
- Resource and quota tests with concurrent users.
- Cost and provenance tests.
- Desktop, tablet, and phone Playwright flows.

Delivery:
- Document routing rules and quotas.
- Update docs/ROADMAP.md with benchmarks for two simultaneous jobs.
- Do not start Phase 13.
```

## Phase 13 prompt — Add the ModuMesh Shop connector

```text
Work on Phase 13 only in https://github.com/dhjh24/modumesh-makerlab after Phase 12 is merged.

Goal:
Connect an approved MakerLab project version to the ModuMesh commerce system through a separate connector package. Keep commerce state out of MakerLab.

Read before editing:
- docs/ROADMAP.md
- artifact lineage, inspection, slicing, and pricing records
- ModuMesh shop API contract and authentication method
- current project/version UI

Required work:
1. Create a separate connector package with a narrow typed interface.
2. Send immutable artifact ID, checksum, preview, dimensions, material/profile choice, print time, material estimate, quantity, and price inputs.
3. Create signed quotes with IDs, expiration times, currency, line-item breakdown, and idempotency keys.
4. Recalculate a quote after any model, profile, material, quantity, or price-rule change.
5. Block submission for failed inspection, missing slice result, missing approved profile, unavailable material, stale artifact, or expired quote.
6. Keep payment, tax, discount, inventory, customer address, fulfillment, and order state in the commerce platform.
7. Store the returned cart-line or order reference without copying payment data.
8. Add retry-safe webhook or polling reconciliation for accepted, rejected, expired, and cancelled quotes.
9. Provide a clear user handoff from MakerLab to cart and back to the saved project.
10. Add admin settings for connector endpoint, credential reference, allowed materials, and kill switch. Never display secrets.

Tests and gates:
- Use a fake commerce server for contract, timeout, retry, signature, idempotency, expiration, and rejection tests.
- Verify matching checksums from project artifact through quote and production file.
- Desktop and mobile purchase-handoff tests.
- Security review for request signing, SSRF, secret handling, replay, and webhook validation.

Delivery:
- Document the connector contract and recovery steps.
- Update docs/ROADMAP.md.
- Do not start Phase 14.
```

## Phase 14 prompt — Add community plugin release controls

```text
Work on Phase 14 only in https://github.com/dhjh24/modumesh-makerlab after Phase 13 is merged.

Goal:
Create safe administrator workflows for installing, testing, activating, rolling back, and quarantining external plugins.

Read before editing:
- docs/ROADMAP.md
- plugin SDK and registry
- worker isolation controls
- all manifest and license metadata
- admin authorization patterns

Required work:
1. Define a signed plugin-package format with manifest, checksums, license record, changelog, host compatibility range, runtime metadata, and reproducible-build reference.
2. Add package upload or approved-registry install for administrators only.
3. Scan for secrets, unsafe paths, unexpected executables, oversized files, unsupported media, forbidden network access, dependency risk, and manifest mismatch.
4. Run contract and sandbox tests before activation.
5. Add publisher identity, review state, installed version, active version, rollback history, quotas, logs, and kill switch.
6. Default all third-party plugins to disabled.
7. Support staged activation, health checks, rollback, quarantine, and deletion of unreferenced package data.
8. Preserve any package version referenced by an existing job or artifact.
9. Add clear admin warnings for licenses, GPU needs, network needs, and hosted-provider costs.
10. Create one signed sample external plugin and one intentionally unsafe test package.

Tests and gates:
- Valid install, invalid signature, checksum mismatch, compatibility failure, unsafe archive, quota breach, activation failure, rollback, quarantine, and referenced-version retention tests.
- Authorization tests for every admin action.
- Audit-log tests with secret redaction.
- Full sample-plugin flow through catalog, job, artifact, disable, rollback, and quarantine.

Delivery:
- Update plugin author, administrator, security, and recovery docs.
- Update docs/ROADMAP.md with shipped status and remaining deferred items.
- Do not integrate TRELLIS.2 unless a separate approved phase covers license clarity and hardware benchmarks.
```
