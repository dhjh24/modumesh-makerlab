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
