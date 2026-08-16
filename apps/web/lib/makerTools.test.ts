/**
 * Unit tests for the Create landing's intent → maker-tool resolution
 * (lib/makerTools.ts). The resolver must never leak plugin IDs and must
 * produce deterministic, useful matches for free-text descriptions.
 */

import { describe, expect, it } from 'vitest';
import { hasClearIntentWinner, listMakerTools, resolveIntent, STARTER_INTENTS } from './makerTools';

describe('resolveIntent', () => {
  it('returns no matches for empty input', () => {
    expect(resolveIntent('')).toEqual([]);
    expect(resolveIntent('   ')).toEqual([]);
  });

  it('resolves a nameplate description to Nameplate Maker only', () => {
    const matches = resolveIntent('a nameplate for my workshop');
    expect(matches).toHaveLength(1);
    expect(matches[0].tool.slug).toBe('nameplate');
    expect(matches[0].score).toBeGreaterThanOrEqual(1);
  });

  it('resolves a storage description to Box & Organizer Maker', () => {
    const matches = resolveIntent('a storage box with compartments');
    expect(matches[0].tool.slug).toBe('openscad-template');
    expect(hasClearIntentWinner(matches)).toBe(true);
  });

  it('resolves a light box description with a clear winner over generic box', () => {
    const matches = resolveIntent('a light box for my logo');
    expect(matches[0].tool.slug).toBe('logo-lightbox');
    // "box" also matches Box & Organizer Maker, but Light Box Maker wins by
    // two keywords ("light box" + "logo") — an unambiguous intent.
    expect(hasClearIntentWinner(matches)).toBe(true);
    expect(matches.map((m) => m.tool.slug)).toContain('openscad-template');
  });

  it('treats a bare "qr sign" as ambiguous (two sign tools)', () => {
    const matches = resolveIntent('qr sign');
    const slugs = matches.map((m) => m.tool.slug);
    expect(slugs).toContain('qr-code-sign');
    expect(slugs).toContain('nameplate');
    expect(hasClearIntentWinner(matches)).toBe(false);
  });

  it('matches whole words, not substrings', () => {
    // "fix" is an intent keyword but must not match "fixtures"-style text
    // through substring matching of arbitrary words; "fixing" is a whole
    // word of its own and should not hit the "fix" keyword.
    expect(resolveIntent('a fixing bracket')).toEqual([]);
  });

  it('returns no matches for unknown objects', () => {
    expect(resolveIntent('a phone stand')).toEqual([]);
    expect(resolveIntent('a wall bracket')).toEqual([]);
  });

  it('matches multi-word intents non-contiguously', () => {
    const matches = resolveIntent('check my model for printing issues');
    expect(matches.some((m) => m.tool.slug === 'mesh-inspector')).toBe(true);
  });
});

describe('hasClearIntentWinner', () => {
  it('is false for no matches', () => {
    expect(hasClearIntentWinner([])).toBe(false);
  });

  it('is true for a single match', () => {
    expect(hasClearIntentWinner(resolveIntent('nameplate'))).toBe(true);
  });

  it('is false for an even tie', () => {
    expect(hasClearIntentWinner(resolveIntent('qr sign'))).toBe(false);
  });
});

describe('STARTER_INTENTS', () => {
  it('every starter chip resolves to a clear winner (no dead ends)', () => {
    for (const chip of STARTER_INTENTS) {
      const matches = resolveIntent(chip.prompt);
      expect(
        matches.length,
        `chip "${chip.label}" (prompt: "${chip.prompt}") must resolve`,
      ).toBeGreaterThan(0);
      expect(
        hasClearIntentWinner(matches),
        `chip "${chip.label}" (prompt: "${chip.prompt}") must have a clear winner`,
      ).toBe(true);
    }
  });

  it('chips reference tools that exist on the user-facing list', () => {
    const slugs = new Set(listMakerTools().map((t) => t.slug));
    for (const chip of STARTER_INTENTS) {
      const winner = resolveIntent(chip.prompt)[0];
      expect(winner).toBeDefined();
      expect(slugs.has(winner.tool.slug)).toBe(true);
    }
  });
});
