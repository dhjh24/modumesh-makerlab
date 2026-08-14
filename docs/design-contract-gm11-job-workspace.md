# Job Result Workspace — Design Contract (GM-11)

Author: Technical Architect (orchestrator) · Branch: `agent/job-workspace` (stacked on `agent/auth-rbac`)
Status: design contract — implementation delegated to `frontend-developer` role.

## Goal
Surface the features that exist in the API/plugins but have zero UI today (audit finding, `docs/team-audit-2026-08-14.md` line 98):
validation report (mesh-inspector), slicer panel, compare mode, and shop handoff cart with gate status.

Scope: **frontend only** (`apps/web`). No backend changes — the API surface below is complete and auth-gated.

## API surface (all auth-gated, owner-scoped, Bearer via existing apiFetch)

| Endpoint | Shape | Purpose |
|---|---|---|
| `GET /api/v1/projects/{pid}/jobs?limit=` | `JobList {items: Job[], total}` | existing, used |
| `GET /api/v1/jobs/{jid}/files` | `FileList {items: FileObject[], total}` | output files for a job (design.json, slicing-report.json, preview.glb, STLs, output.gcode, output.3mf) |
| `GET /api/v1/files/{fid}/download` | binary | protected download — must use existing `fetchFileBlob` |
| `GET /api/v1/projects/{pid}/jobs/{jid}/pricing` | `{job_id, project_id, currency, price_breakdown{materials,labor,machine_time,shipping_handling}, markup_pct, markup_amount, total, includes[], disclaimer}` | price for a completed job; 400 if no `material_estimate` |
| `POST /api/v1/projects/{pid}/jobs/{jid}/shop-handoff` | `{handoff{...}, pricing{...}, note}` | Vendure-compatible cart payload; 400 unless job `status == completed` |
| `POST /api/v1/compare` | body `{project_id, input_payload, generators[]}` → `{project_id, comparison{generator_count}, jobs[{generator, job_id}], note}` | same input to N generators (max 6) |
| `GET /api/v1/compare/{project_id}?generators=a,b` | `{project_id, results[{id, job_type, status, progress_pct, error_message}], total}` | comparison results |

## Data shapes in job outputs (for the result panels)

- **design.json** (generator outputs): `{generator_version, parameters, outputs{face.stl,enclosure.stl,back-panel.stl,preview.glb → {size_bytes}}, generation_duration_s, warnings[], material_estimate{filament_cost_usd, led_kit_cost_usd, ...}, generated_at}`
- **slicing-report.json** (slicer plugin): `{plugin_id: "slicer", slice{printer_profile, nozzle_mm, layer_height_mm, infill_pct, supports, material}, estimated{print_time_estimate, filament_length_mm, filament_weight_g}, return_code, generated_at}`

## UI design

### 1. Result panel in project editor (`apps/web/pages/projects/[id].tsx`)
New section in the right-hand "project" pane (below Files), keyed to the **active job**:
- **When active job is terminal (completed/failed/cancelled)**, fetch `GET /jobs/{id}/files` and render:
  - *Validation report* — from `design.json`: generation duration, warnings list, material estimate (filament USD + LED kit USD)
  - *Slicer panel* — from `slicing-report.json` if present: printer profile, nozzle/layer/infill/material, estimated print time + filament length/weight
  - *Pricing + Shop handoff* — "Get price" button → `GET .../pricing` renders price_breakdown + total + includes; "Send to shop" button → `POST .../shop-handoff` renders the handoff payload (collapsed JSON or key fields) + gate status. **Gate status display**: pricing requires material estimate (400 → show reason); handoff requires completed status (400 → show "Job must be completed").
- Loading and empty states for each sub-block; errors via existing `ErrorPanel` pattern.

### 2. Compare mode
- Entry: button in the project pane "Compare generators" (visible when ≥2 enabled plugins exist).
- New page `apps/web/pages/projects/[id]/compare.tsx` (or modal — architect prefers a page; keep URL-navigable):
  - Loads enabled plugins (`GET /api/v1/plugins?enabled_only=true`), multi-select up to 6 generators.
  - Reuses the active job's `input_payload` as the default input (or a param form for job_type-specific payloads).
  - "Run comparison" → `POST /api/v1/compare` → then poll each job via existing `useJobPolling`-style logic; render a per-generator card: job_type, status badge, progress bar, error message, output files (design.json summary, download buttons via `fetchFileBlob`).
  - Also supports loading an existing comparison: `GET /api/v1/compare/{project_id}` and rendering the result rows.

## Existing building blocks (do NOT reinvent)
- `apps/web/lib/api.ts`: `apiFetch<T>` (attaches Bearer, 401→clearToken), `fetchFileBlob(fileId, fallbackName)` → `{blob, filename, contentType}`, `api` object (extend it with `listJobFiles`, `getJobPricing`, `createShopHandoff`, `createComparison`, `getComparison`).
- `apps/web/lib/auth.ts`: token plumbing. `apps/web/lib/hooks.ts`: `useJobPolling`.
- Components: `AppShell`, `LazyModelViewer`, `@modumesh/ui` (`Button`, `EmptyState`, `JobStatusBadge`, `isTerminalJobStatus`, `formatRelativeTime`, `inferModelFormat`).
- Styling: `mm-*` utility classes already used in `[id].tsx` (mm-panel, mm-list, mm-meta, mm-row, mm-linkish, mm-tabs, mm-progress). Keep consistent; no new design tokens.
- Pages use `api` methods, not raw fetch.

## Guardrails (repo-wide, from .hermes.md / team doc)
- No commits to `main`; work only on `agent/job-workspace`.
- No `.env`, no secrets. Never commit `node_modules`.
- All API calls through `apiFetch` (Bearer attached automatically).
- Files preview/download ONLY via `fetchFileBlob` (never bare URLs — auth).
- Mobile-first responsive: keep the existing `mm-tabs` (parameters/preview/project) working; new compare page responsive.
- TypeScript strict; no `any` leaks from new API response types — define interfaces in the page or `apps/web/lib/api.ts` matching the backend shapes above.

## Definition of done / acceptance
1. Result panel renders for a completed job: validation report, slicer panel (when slicing-report.json exists), pricing, shop handoff with correct gate states.
2. Compare page: select ≤6 generators, run comparison, poll statuses, render per-generator results + files, and load an existing comparison.
3. `esbuild`/`tsc` parse clean; no new `fileDownloadUrl`/`window.open` for protected files.
4. API methods added to `apps/web/lib/api.ts` `api` object.
5. No backend files modified.
6. HANDOFF block complete with state=done and evidence.

## Handoff
End the handoff with the `HANDOFF:` block (owner: frontend-developer, state, scope, evidence, changes, tests_required, acceptance, rollback, dependencies, blocker).
