# Maker Studio UX Overhaul — Phase 3, Wireframe 3: My Models (approved)

Date: 2026-08-15 · Branch: agent/ux-wf3 · Status: **APPROVED with corrections (2026-08-15)**
Base: WF1 (approved, #54) + WF2 (approved, #55)

## Deliverable

**File:** `docs/wireframes/wf3-my-models.html` (open in a browser; fully clickable)

The My Models destination as a visual model library. Proves:

```
My Models (/models)
  → card grid: thumbnail · name · maker tool · last modified · printable state
  → filters: All / Printable / Needs work / Not checked
  → Open → Studio (with the model loaded)
  → Export → Print/Export dialog (WF1)
  → Duplicate → name prompt → new copy opens-ready in Studio
  → Remove → confirm dialog ("hidden from My Models, stays archived, can be restored")
  → empty / loading (skeletons) / error (retry) states demonstrated
```

## IA compliance

- Route: `/models` (fifth destination; reachable from header nav + mobile tab bar)
- Card meta shows the **Maker Tool name** ("Nameplate Maker"), never the plugin ID
- Printable state is a real signal from mesh-inspector/design.json: PASS / WARNING / NOT
  CHECKED — "Not checked" is shown honestly rather than implying a model is printable
- Card actions match the IA: Open · Duplicate · Export · Delete (⋯ overflow on the thumb)

## Card anatomy (locked)

| Element | Source |
|---|---|
| Thumbnail | First viewable output (GLB/STL) rendered by the existing viewer; wireframe uses placeholder SVGs |
| Name | Project name (editable in Studio) |
| Maker tool | Tool presentation-layer name + version (human) — plugin IDs stay hidden |
| Last modified | `updated_at` relative ("2h ago") |
| Printable state | Derived from the job's real checks: all pass → PASS; warnings → WARNING; no inspection ran → NOT CHECKED. **Never infer printable when inspection did not run.** |

## Card actions (locked)

- **Open + Export visible on the card.** Duplicate + Remove live under **⋯**.
- **Remove = archive + hide, not permanent deletion** (v1). Copy is recoverable:
  "This hides the model from My Models. It stays archived in your account and can be
  restored." — UI and backend agree (maps to the existing `POST /projects/{id}/archive`
  endpoint).

## Filters, sorting, duplicate (locked)

- Filters: **All / Printable / Needs work / Not checked**. AI-generated filter stays out
  until AI modes ship.
- Sorting: **last modified descending only for v1** — no sort UI yet.
- Duplicate: keep the pre-filled **"<name> (copy)"** dialog; implementation = create the
  project, then rerun the source's latest `input_payload`.

## States

| State | Behavior |
|---|---|
| Content | Card grid + filters (counts per filter) |
| Empty | "No models yet — start with a nameplate" + CTA → Create (no dev copy) |
| Loading | Skeleton cards (shimmer) — not a text "Loading…" |
| Error | "Couldn't load your models — your models are safe" + Retry (existing ErrorPanel semantics; correlation id in technical detail) |
| Remove | Confirm modal naming the model; **recoverable wording** ("hidden… can be restored") |
| Duplicate | Name prompt pre-filled "<name> (copy)"; creates a new project + reruns latest input_payload |
| Filtered to zero | Empty-state panel ("No models match") with filter-clear action |

## Backend dependencies (recorded, not built here)

1. **Duplicate project** — MVP: `POST /projects` with the source project's
   name+description, then re-run the latest job's `input_payload` (no new endpoint
   strictly required for a first cut; a real duplicate endpoint is cleaner)
2. **Remove (archive + hide)** — the existing `POST /projects/{id}/archive` endpoint
   satisfies v1; My Models lists only non-archived projects. Restore = PATCH status back
   to active (backend affordance; restore UI can be a later wave)
3. **Thumbnails** — client-rendered from the first viewable output in MVP (viewer already
   renders GLB/STL); server thumbnails optional later

## Approval record (2026-08-15)

Approved from the product/UX side with these locked decisions:
- Card actions: **Open + Export visible; Duplicate + Remove under ⋯**
- Remove: **archive + hide, not permanent deletion**; recoverable copy ("hidden from My
  Models, stays archived, can be restored") — UI and backend agree
- Filters: **All / Printable / Needs work / Not checked**; AI-generated out until those
  modes ship
- Sorting: **last modified descending only for v1**; no sort UI yet
- Duplicate: pre-filled **"<name> (copy)"** dialog → create project → rerun latest
  input_payload
- Printability: **PASS / WARNING / NOT CHECKED**, evidence-backed; never infer printable
  when inspection did not run
- Presentation: **Maker Tool names only; plugin IDs hidden**

After WF3 lands: **wireframe phase complete → implementation waves W2.1 → W2.6**, starting
with route/nav scaffolding (W2.1).
