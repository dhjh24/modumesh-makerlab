# Maker Studio UX Overhaul — Phase 3, Wireframe 3: My Models

Date: 2026-08-15 · Branch: agent/ux-wf3 · Status: FOR REVIEW
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
  → Delete → confirm dialog ("removes model and its history, can't be undone")
  → empty / loading (skeletons) / error (retry) states demonstrated
```

## IA compliance

- Route: `/models` (fifth destination; reachable from header nav + mobile tab bar)
- Card meta shows the **Maker Tool name** ("Nameplate Maker"), never the plugin ID
- Printable state is a real signal from mesh-inspector/design.json: PASS / WARNING / NOT
  CHECKED — "Not checked" is shown honestly rather than implying a model is printable
- Card actions match the IA: Open · Duplicate · Export · Delete (⋯ overflow on the thumb)

## Card anatomy

| Element | Source |
|---|---|
| Thumbnail | First viewable output (GLB/STL) rendered by the existing viewer; wireframe uses placeholder SVGs |
| Name | Project name (editable in Studio) |
| Maker tool | Tool presentation-layer name + version (human) |
| Last modified | `updated_at` relative ("2h ago") |
| Printable state | Derived from the job's real checks: all pass → PASS; warnings → WARNING; no inspection ran → NOT CHECKED |

## States

| State | Behavior |
|---|---|
| Content | Card grid + filters (counts per filter) |
| Empty | "No models yet — start with a nameplate" + CTA → Create (no dev copy) |
| Loading | Skeleton cards (shimmer) — not a text "Loading…" |
| Error | "Couldn't load your models — your models are safe" + Retry (existing ErrorPanel semantics; correlation id in technical detail) |
| Delete | Confirm modal naming the model; destructive wording ("can't be undone") |
| Duplicate | Name prompt pre-filled "<name> (copy)"; creates a new project with the same settings (backend gap: duplicate endpoint — MVP can create a new project + copy input_payload) |
| Filtered to zero | Empty-state panel ("No models match") with filter-clear action |

## Backend dependencies (recorded, not built here)

1. **Duplicate project** — MVP path: `POST /projects` with the source project's
   name+description, then re-run the latest job's `input_payload` (no new endpoint
   strictly required for a first cut; a real duplicate endpoint is cleaner)
2. **Delete project/model** — only `archive` exists today; delete = archive + hide, or a
   new DELETE endpoint with the ownership check (404-not-403 pattern)
3. **Thumbnails** — client-rendered from the first viewable output in MVP (viewer already
   renders GLB/STL); server thumbnails optional later

## Review questions

1. Card actions: four buttons (Open/Export/Duplicate/Delete) or a leaner card (Open +
   ⋯ overflow) with actions in a menu?
2. Delete: hard delete vs archive-and-hide (recoverable)? The wireframe shows destructive
   confirm — safe default, but recoverable delete is friendlier.
3. Filter set: All / Printable / Needs work / Not checked — or add "AI-generated" now
   (it's gated anyway, so probably later)?
4. Sorting: default = last modified desc; need name/size/date sort controls in v1?
5. Duplicate naming: pre-filled "<name> (copy)" — good, or open Studio immediately with
   an inline rename?

After WF3 approval: **implementation waves begin (W2.1 → W2.6)**.
