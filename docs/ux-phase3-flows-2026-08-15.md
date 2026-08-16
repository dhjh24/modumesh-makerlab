# Maker Studio UX Overhaul — Phase 3: UX flows & wireframes

Date: 2026-08-15 · Branch: agent/ux-phase3 · Status: FOR REVIEW
Base: Phase 2 IA (approved, merged PR #53)

## Deliverable 1 — Wireframe: complete nameplate path

**File:** `docs/wireframes/wf1-nameplate-path.html` (open in a browser; fully clickable)

This first wireframe proves the entire journey in one screen sequence:

```
Create ("a nameplate with my workshop name")
  → intent resolved automatically → Nameplate Maker (Best match)
  → Studio: grouped params (Dimensions / Text / Mounting / Print settings)
  → 3D preview with build plate + dims overlay + parts tree + history
  → staged generation progress (Preparing → … → Ready) on regenerate
  → Printability bar: Manifold / Watertight / Fits build volume / Min wall (PASS)
  → Print / Export dialog: 3MF | STL | GLB, real summary (name, dims, checks, tool+version)
  → Download → toast → appears in My Models with "Printable" state
```

### What the wireframe demonstrates (and locks for implementation)

1. **Intent → Maker Tool, zero plugin knowledge.** Typing "nameplate" or tapping the chip resolves to the Nameplate Maker automatically; the alternatives shown are other _maker tools_ (QR Sign Maker, Light Box Maker), never plugin IDs.
2. **AI modes are visible but gated** ("Coming soon") — per locked note #5, no half-working AI. Text→3D / Image→3D appear only as mode cards until `productionReady: true`.
3. **Studio layout** exactly as IA'd: parts tree + history (L), viewport with build plate/grid/dims overlay (C), **grouped** parameters (R: Dimensions, Text, Mounting, Print settings, Advanced), status bar with real checks + the single **Print / Export** primary action (bottom).
4. **Grouped SchemaForm**: the wireframe shows the nameplate schema (12 fields) rendered in 4 groups — this requires adding `x-group` support to `SchemaForm` (W2.5) with a group order from the tool definition.
5. **Staged progress** replaces raw `queued/running/validating/uploading` — user-visible stages mapped from job status + progress_message.
6. **Printability bar**: only real checks shown (from mesh-inspector/design.json); "Print estimate" stays `—` (not run) rather than fabricating a slicer number. **Never claim printable when checks haven't run.**
7. **Export dialog** carries the honest summary: dimensions, validation 4/4, tool name + version, format choice (3MF preferred).
8. **My Models card** shows thumbnail, tool name (not plugin_id), dims, and the printable state badge.

## Deliverable 2 — Create screen flow detail

### States

| State                       | Behavior                                                                                               |
| --------------------------- | ------------------------------------------------------------------------------------------------------ |
| First visit                 | Hero prompt + example chips + mode cards; empty intro copy ("Make your first thing")                   |
| Typing intent               | Live resolution: if the text matches a tool keyword → show Best-match panel (tool card + 2 alternates) |
| No match                    | Mode cards remain; user picks a mode (Parametric → Explore picker)                                     |
| AI intent ("make me a mug") | "Coming soon" — explainer card: "AI text-to-3D is on the way. Try a maker tool:" + 3 tool cards        |
| Offline / API down          | Existing OfflineState + retry                                                                          |
| Auth expired                | `/login?next=/` (existing pattern)                                                                     |

### Intent → tool resolution (MVP heuristic, no backend change)

- Keyword map over the MakerTool catalog: `nameplate`, `sign`, `qr`, `box`, `organizer`, `bracket`, `keychain`, `light box`, `tray`, `holder`, …
- Multi-match → best-match panel (top pick + 2 alternates, visually identical to the wireframe)
- No match → parametric path (Explore picker) — **never** a raw plugin dropdown
- Later: text→3D AI provider (Phase 9) becomes the fallback for unmatched intents, still gated

## Deliverable 3 — Studio flow detail (this screen is the "wow" gate)

| Interaction           | Behavior                                                                                                                                               |
| --------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Open model            | Load latest terminal job's first viewable output; staged "Opening…" if job active                                                                      |
| Regenerate            | Same tool + current params, new idempotency key, staged progress overlay, result replaces preview; new history entry (v4…)                             |
| Compare (Studio mode) | "Try another maker tool with the same input" — pick 2–6 tools, runs jobs, side-by-side cards (existing compare API, friendly payload = current params) |
| Edit params           | Any change marks "Not regenerated" hint on the Regenerate button (prevents stale preview + new model mismatch)                                         |
| Parts tree            | v1: single model + mounting holes read-only; add-part = future multi-body (no backend change)                                                          |
| History               | Job list rendered as versions v1..vn (attempt_number), click to load that job's output                                                                 |
| Print/Export          | Dialog as wireframed; disabled state when checks failed/warnings pending review                                                                        |

### Error/recovery states (Studio)

| Failure                 | Recovery                                                                                              |
| ----------------------- | ----------------------------------------------------------------------------------------------------- |
| Generator unavailable   | Error panel: "This maker tool is unavailable" + Explore other tools + retry                           |
| Generation failed       | Panel with job error message (sanitized) + Retry / Try another tool                                   |
| Invalid mesh            | Printability bar shows FAIL on manifold/watertight + repair action only if mesh-inspector supports it |
| Missing artifact        | "Output not found" + regenerate                                                                       |
| Viewer failure          | Retry load + fallback file list download                                                              |
| API/worker/storage down | Offline/retry + correlation id in technical detail (existing ErrorPanel)                              |

## Not in this wave (recorded)

- Backend: upload endpoint, delete/duplicate, password change, AI providers (Phase 9) — all tracked in the IA §8 gaps
- Compare wireframe detail (next wireframe after this one is approved)
- My Models full wireframe (cards sketched here; refine in W2.4)

## Review questions

1. Does the nameplate path feel like "one coherent creation app" — any step that still smells like a plugin/dashboard?
2. Intent resolution: keyword-map MVP acceptable, or do you want a schema-search fallback now?
3. Staged progress copy (approved): **Preparing → Building geometry → Processing model → Checking printability → Creating preview → Ready** (reworded from the dev-sounding "Generating geometry"/"Processing mesh" per 2026-08-15 review)
4. Export: 3MF-first default correct, or should STL remain default until a real slicer ships 3MF?
5. Compare as a Studio mode — sketch it next, or wireframe My Models/Settings first?
