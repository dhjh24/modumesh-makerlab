# Maker Studio UX Overhaul — Phase 3, Wireframe 2: Compare mode (approved)

Date: 2026-08-15 · Branch: agent/ux-wf2 · Status: **APPROVED with corrections (2026-08-15)**
Base: Phase 2 IA (approved) + WF1 (approved, merged #54/26f6d124)

## Deliverable

**File:** `docs/wireframes/wf2-compare-mode.html` (open in a browser; fully clickable)

Proves the exact locked flow:

```
Studio → Compare
  → current Nameplate
  → Compare
  → choose comparison kind (one command, two intents — no API concepts)
  → suggested compatible Maker Tools (tools kind) / saved versions (versions kind)
  → select 2–4
  → shared parameters clearly marked ("Shared — applies to all")
  → incompatible parameters handled per-tool, without JSON
  → Generate comparisons
  → independent progress per candidate (staged: Preparing → … → Ready)
  → side-by-side 3D previews
  → dimensions + printability under each
  → select winner
  → "Use this version"
  → winner becomes current Studio model
  → comparison remains in History
```

## The two comparison kinds (one command, no API concepts)

Your correction is baked in: Compare is ONE command; the user then picks what they're
comparing, phrased as intent, never as "compare versions/tools" API terms.

| Kind | User-facing question | What's compared | UX |
|---|---|---|---|
| **Versions** | "Which settings look better?" | Saved attempts of the SAME maker tool (v1…vn from job history) | Version picker cards, each with its param summary |
| **Tools** | "Which way should I make this?" | Current tool vs compatible Maker Tools (2–4) | Tool picker cards with compatibility tags |

- The kind switch is a segmented control: **"⚖️ Which settings look better?"** / **"🧩 Which way should I make this?"** — "Versions" is never the main UI label
- **Default: Tools** ("Which way should I make this?") — a new user is more likely to ask this before accumulating several versions

## Selection contract (corrected)

- **Both modes: minimum 2, maximum 4** selections. The Run button stays disabled until ≥2; hint reads **"Select at least 2 items to compare."**

## Compatibility model (tools kind)

- A tool is suggested only when it can consume a **compatible parameter set** — same input
  family as the current tool (text-based plate tools are all mutually compatible:
  Nameplate, QR Sign, Sign; Light Box needs artwork → tagged "Needs artwork", still
  selectable but its per-tool input is explicit).
- Tags: **Fully compatible** (green) / **Needs [X]** (amber) — the user always sees WHY a
  tool is or isn't a drop-in.
- **No ML in MVP; compatibility uses a small hand-authored map plus schema-family matching.**

## Parameter handling (the anti-JSON contract)

- **Shared parameters** (present in every selected tool): one editable panel, labeled
  "Shared — applies to all". Editing once copies to all candidates.
- **Per-tool parameters**: each selected tool's unique fields render in its own
  "Only in <Tool Name>" box (e.g. Nameplate: text/font/raised; QR: link/corner style).
  Never hidden, never dumped into a JSON textarea, never shown with raw keys.
- A parameter a tool can't use simply **doesn't render for that tool** — no dead fields,
  no "incompatible" errors, no JSON.
- MVP: shared-set = intersection of schema keys; per-tool = remainder. (x-group work in
  W2.5 lands the grouping primitives this reuses.)

## Results & winner flow

- Cards run **independently** — each shows its own staged progress (Preparing → Building
  geometry → Processing model → Checking printability → Creating preview → Ready, per
  approved copy).
- **Printability checks appear only once that candidate has finished** — no ✓ marks during
  Preparing/Building (honesty rule from WF1; checks render hidden until completion).
- On ready, each card shows: 3D preview (existing viewer), **dimensions**, **printability
  checks** (real, from mesh-inspector/design.json), and its param summary.
- **Winner selection waits for every candidate** — no choosing before the comparison is
  complete. A candidate whose failure is **final** stops blocking the others (failed cards
  show the failure + "Try again" instead of ✓ checks).
- **Select winner** → "Use this version" → confirm modal → winner becomes the Studio
  model; the comparison is recorded in Studio History as a **descriptive entry** —
  e.g. **"Compare · Nameplate vs QR Sign vs Sign"** — with the count as secondary
  metadata ("3 tools"). History count is always the actual selection count.

## States

| State | Behavior |
|---|---|
| <2 selected | Run disabled, hint "Select at least 2 items to compare" |
| Versions kind, <2 versions exist | Versions picker shows empty state → "Generate a new version first" + back to Studio |
| Tool has no compatible tools | Tools picker empty state → "No other maker tools fit this design yet" + Explore CTA |
| A candidate fails | Card shows FAIL state + error message (sanitized) + "Try again" per-card; stops blocking others once final |
| Candidate still running | Other cards run independently; winner buttons stay hidden until every candidate is done (ready or failed-final) |
| API/worker down | Existing OfflineState / ErrorPanel + correlation id in technical detail |

## Per-tool parameter display (locked)

- **2–3 candidates: per-tool unique sections stay expanded.**
- **4 candidates: the unique sections collapse** (accordion) to keep the comparison readable.
- Shared panel is always expanded.

## Approval record (2026-08-15)

WF2 conceptually approved with four implementation-neutral wireframe corrections:
1. Min 2 / max 4 selections in both modes ("Select at least 2 items to compare")
2. Default kind = Tools (matches design doc)
3. Printability checks hidden until that candidate finishes
4. History count dynamic (descriptive name + actual count)

Locked design choices: "Which settings look better?" / "Which way should I make this?"
phrasing (no "Versions" main label) · Fully compatible / Needs artwork tags · per-tool
boxes expanded at 2–3, collapsed at 4 · winner selection waits for all candidates
(failed-final stops blocking) · descriptive History names ("Compare · Nameplate vs QR
Sign vs Sign") with count as secondary · wording: "No ML in MVP; compatibility uses a
small hand-authored map plus schema-family matching."

After WF2 lands: **WF3 = My Models**, then implementation waves (W2.1 → W2.6).
