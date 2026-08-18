/**
 * Maker-Tool presentation layer (IA §5, approved).
 *
 * Plugins stay the engine; user screens only ever see Maker Tools. This module
 * is the single mapping from plugin_id → user-facing tool. Normal pages must
 * never read PluginRecord/CatalogItem fields (engine, sdk_version, license,
 * plugin_id, maturity) directly — use `makerToolFor` / `listMakerTools`.
 */

export type ToolCategory = 'signs' | 'containers' | 'decor' | 'utility';

export interface MakerTool {
  /** Stable route slug — derived from the plugin_id (never shown to users). */
  slug: string;
  /** User-facing name: "Nameplate Maker" — never "nameplate". */
  name: string;
  /** One-line promise. */
  promise: string;
  category: ToolCategory;
  categoryLabel: string;
  icon: string;
  difficulty: 'Beginner' | 'Intermediate' | 'Advanced';
  /** Human input description, e.g. "Type the text to engrave". */
  inputModeLabel: string;
  /** Example uses shown on the tool detail page. */
  examples: string[];
  /** Hidden from normal screens until a real provider ships (locked note #5). */
  productionReady: boolean;
  /** Fixture/test plugins never surface (locked). */
  surfaceable: boolean;
  /**
   * User-intent keywords that resolve to this tool (lowercase; multi-word
   * phrases and single words). Used by the Create landing's intent resolver —
   * users describe what they want to make, never pick a plugin.
   */
  intents: string[];
}

const TOOLS: Record<string, MakerTool> = {
  nameplate: {
    slug: 'nameplate',
    name: 'Nameplate Maker',
    promise: 'Engrave text on a clean plate with mounting holes.',
    category: 'signs',
    categoryLabel: 'Signs & Labels',
    icon: '🪧',
    difficulty: 'Beginner',
    inputModeLabel: 'Type the text, pick a font, set the size.',
    examples: ['Workshop and studio signs', 'Office door plates', 'Gift tags and labels'],
    intents: [
      'nameplate',
      'name plate',
      'name badge',
      'badge',
      'plaque',
      'sign',
      'label',
      'tag',
      'door plate',
    ],
    productionReady: true,
    surfaceable: true,
  },
  'qr-code-sign': {
    slug: 'qr-code-sign',
    name: 'QR Sign Maker',
    promise: 'A printable sign with a scannable QR code.',
    category: 'signs',
    categoryLabel: 'Signs & Labels',
    icon: '🔳',
    difficulty: 'Beginner',
    inputModeLabel: 'Enter a link or text to encode.',
    examples: ['Wi-Fi login cards', 'Studio door signs', 'Equipment labels'],
    intents: ['qr', 'qr code', 'qrcode', 'wifi card', 'login card', 'link card', 'wifi sign'],
    productionReady: true,
    surfaceable: true,
  },
  'logo-lightbox': {
    slug: 'logo-lightbox',
    name: 'Light Box Maker',
    promise: 'Backlit LED sign from your artwork or logo.',
    category: 'decor',
    categoryLabel: 'Decor',
    icon: '💡',
    difficulty: 'Intermediate',
    inputModeLabel: 'Upload artwork (SVG/PNG) or type text.',
    examples: ['Business logos', 'Room signs', 'Event backdrops'],
    intents: ['lightbox', 'light box', 'logo', 'backlit', 'illuminated', 'led sign'],
    productionReady: true,
    surfaceable: true,
  },
  'openscad-template': {
    slug: 'openscad-template',
    name: 'Box & Organizer Maker',
    promise: 'Storage boxes and grid organizers in any size.',
    category: 'containers',
    categoryLabel: 'Containers & Organization',
    icon: '📦',
    difficulty: 'Beginner',
    inputModeLabel: 'Set the size, compartments, and wall thickness.',
    examples: ['Parts trays', 'Desk organizers', 'Small-parts storage'],
    intents: [
      'storage box',
      'box',
      'organizer',
      'organiser',
      'tray',
      'container',
      'bin',
      'drawer',
      'storage',
      'compartment',
    ],
    productionReady: true,
    surfaceable: true,
  },
  'mesh-inspector': {
    slug: 'mesh-inspector',
    name: 'Print Check & Repair',
    promise: 'Check a model for printability and fix problems.',
    category: 'utility',
    categoryLabel: 'Utility',
    icon: '🛠️',
    difficulty: 'Intermediate',
    inputModeLabel: 'Open a model file to analyze it.',
    examples: ['Check downloaded models', 'Verify wall thickness', 'Find broken geometry'],
    intents: [
      'print check',
      'repair',
      'fix',
      'inspect',
      'printable',
      'wall thickness',
      'broken model',
      'check model',
      'validate',
    ],
    productionReady: true,
    surfaceable: true,
  },
  // AI generators stay hidden until productionReady: true (locked note #5).
  triposr: {
    slug: 'triposr',
    name: 'Image-to-3D (fast)',
    promise: 'Turn a photo into a 3D model.',
    category: 'utility',
    categoryLabel: 'Utility',
    icon: '🖼️',
    difficulty: 'Advanced',
    inputModeLabel: 'Upload a photo.',
    examples: [],
    intents: [],
    productionReady: false,
    surfaceable: false,
  },
  hunyuan3d: {
    slug: 'hunyuan3d',
    name: 'Image-to-3D (quality)',
    promise: 'High-quality 3D model from a photo.',
    category: 'utility',
    categoryLabel: 'Utility',
    icon: '🖼️',
    difficulty: 'Advanced',
    inputModeLabel: 'Upload a photo.',
    examples: [],
    intents: [],
    productionReady: false,
    surfaceable: false,
  },
};

/** Resolve a tool by plugin_id/slug; null when unknown or not surfaceable. */
export function makerToolFor(slug: string | null | undefined): MakerTool | null {
  if (!slug) return null;
  const tool = TOOLS[slug];
  if (!tool || !tool.surfaceable || !tool.productionReady) return null;
  return tool;
}

/** All tools that may appear on user screens (production-ready + surfaceable). */
export function listMakerTools(): MakerTool[] {
  return Object.values(TOOLS).filter((t) => t.surfaceable && t.productionReady);
}

/** User-facing category list, ordered for discovery. */
export const TOOL_CATEGORIES: Array<{ key: ToolCategory; label: string }> = [
  { key: 'signs', label: 'Signs & Labels' },
  { key: 'containers', label: 'Containers & Organization' },
  { key: 'decor', label: 'Decor' },
  { key: 'utility', label: 'Utility' },
];

// ── Intent resolution (Create landing, IA §4.1) ───────────────────────

/** A tool matched by the intent resolver, ranked by keyword hits. */
export interface IntentMatch {
  tool: MakerTool;
  /** Number of distinct intent keywords that hit. */
  score: number;
}

/** Whole-word match with an optional plural: "nameplates" hits "nameplate",
 * but "fixing" never hits "fix" (substring matches are wrong for intents). */
function wordBoundaryMatch(haystack: string, needle: string): boolean {
  const escaped = needle.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  return new RegExp(`(^|[^a-z])${escaped}s?($|[^a-z])`).test(haystack);
}

/**
 * Resolve a free-text "what do you want to make?" description to maker
 * tools — never to plugins (locked note #1). Multi-word intents match when
 * they appear in the text (contiguous or as all of their words); single-word
 * intents match as whole words (with plurals). Results are ranked best-first.
 */
export function resolveIntent(raw: string): IntentMatch[] {
  const input = raw.toLowerCase().trim().replace(/\s+/g, ' ');
  if (!input) return [];
  const words = new Set(input.split(' ').filter((w) => w.length >= 3));
  const scored: IntentMatch[] = [];
  for (const tool of listMakerTools()) {
    let score = 0;
    for (const intent of tool.intents) {
      if (intent.includes(' ')) {
        const parts = intent.split(' ');
        if (input.includes(intent) || parts.every((w) => words.has(w))) score += 1;
      } else if (wordBoundaryMatch(input, intent)) {
        score += 1;
      }
    }
    if (score > 0) scored.push({ tool, score });
  }
  scored.sort((a, b) => b.score - a.score);
  return scored;
}

/**
 * True when one tool is an unambiguous intent match: either it is the only
 * match, or it outscores every runner-up by at least one keyword (e.g.
 * "a light box for my logo" → Light Box Maker beats Box & Organizer).
 */
export function hasClearIntentWinner(matches: IntentMatch[]): boolean {
  if (matches.length === 0) return false;
  if (matches.length === 1) return true;
  return matches[0].score - matches[1].score >= 1;
}

/** Starter chips under the hero prompt — each resolves via the real resolver. */
export const STARTER_INTENTS: Array<{ label: string; prompt: string }> = [
  { label: 'Nameplate', prompt: 'a nameplate for my workshop' },
  { label: 'Storage box', prompt: 'a storage box with compartments' },
  { label: 'Organizer', prompt: 'a desk organizer' },
  { label: 'QR sign', prompt: 'a QR sign for my wifi' },
  { label: 'Light box', prompt: 'a light box for my logo' },
  { label: 'Print check', prompt: 'check a model for printability' },
];
