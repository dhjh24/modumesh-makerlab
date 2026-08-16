# Maker Studio UX Overhaul — Phase 3, Wireframe 2: Compare mode

Date: 2026-08-15 · Branch: agent/ux-wf2 · Status: FOR REVIEW
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

- The kind switch is a segmented control: **"⚖️ Which settings look better?"** / **"🧩 Which way should I make this?"**
- Default: Tools (the more common "should I use something else?" case), one tap to Versions

## Compatibility model (tools kind)

- A tool is suggested only when it can consume a **compatible parameter set** — same input
  family as the current tool (text-based plate tools are all mutually compatible:
  Nameplate, QR Sign, Sign; Light Box needs artwork → tagged "Needs artwork", still
  selectable but its per-tool input is explicit).
- Tags: **Fully compatible** (green) / **Needs [X]** (amber) — the user always sees WHY a
  tool is or isn't a drop-in.
- MVP rule: compatibility = overlapping schema key families (width/height/thickness +
  input mode). No ML, no manual matrix in v1 — a small hand-authored map in the tool
  presentation layer, extended as tools land.

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
- On ready, each card shows: 3D preview (existing viewer), **dimensions**, **printability
  checks** (real, from mesh-inspector/design.json — same honesty rule as WF1), and its
  param summary.
- **Select winner** → "Use this version" → confirm modal → winner becomes the Studio
  model; the comparison is recorded in Studio History as one entry
  ("Compare · 3 versions" / "Compare · 3 tools") so the user can return and see what was
  compared.

## States

| State | Behavior |
|---|---|
| 0 selected | Run disabled, hint "Select at least one item" |
| Versions kind, <2 versions exist | Versions picker shows empty state → "Generate a new version first" + back to Studio |
| Tool has no compatible tools | Tools picker empty state → "No other maker tools fit this design yet" + Explore CTA |
| A candidate fails | Card shows FAIL checks + error message (sanitized) + "Try again" per-card |
| Candidate still running | Other cards remain interactive; winner selection waits for all (or allow partial: pick from ready cards) |
| API/worker down | Existing OfflineState / ErrorPanel + correlation id in technical detail |

## Review questions

1. Two-kind switch (settings vs tools) — is the phrasing right, or should "Versions" be
   labeled "My saved versions" for clarity?
2. Compatibility tags: "Fully compatible" / "Needs artwork" — OK, or prefer different labels?
3. Per-tool params in separate boxes — right granularity, or should each tool's unique
   params collapse into an accordion to save space with 4 tools?
4. Winner selection: allow picking a winner while other candidates still run, or wait for all?
5. History entry naming: "Compare · 3 tools" — good enough, or name it by tools
   ("Compare · Nameplate vs QR Sign vs Sign")?

After WF2 approval: **WF3 = My Models**, then the implementation waves (W2.1 → W2.6) begin.
