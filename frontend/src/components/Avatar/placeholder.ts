/**
 * The picture shown for a profile without a photograph: one of six small sport scenes in the
 * colours of the product, chosen from the profile identifier. The same profile always gets the
 * same scene, so a person stays recognisable in a list without having uploaded anything.
 */

export const MOTIFS = ["track", "waves", "peaks", "target", "net", "sunrise"] as const;
export type Motif = (typeof MOTIFS)[number];

/** Colour pairs taken from the design tokens: [background, drawing]. */
export const PALETTES = [
  ["var(--color-primary-soft)", "var(--color-primary)"],
  ["var(--color-accent-soft)", "var(--color-accent)"],
  ["var(--color-tint)", "var(--color-primary-hover)"],
  ["var(--color-surface)", "var(--color-accent)"],
] as const;

/** A small stable hash of a string (FNV-1a, 32 bit); not for anything secret. */
export function hashOf(text: string): number {
  let hash = 0x811c9dc5;
  for (let index = 0; index < text.length; index += 1) {
    hash ^= text.charCodeAt(index);
    hash = Math.imul(hash, 0x01000193);
  }
  return hash >>> 0;
}

export interface PlaceholderLook {
  motif: Motif;
  background: string;
  ink: string;
  /** True when the scene is mirrored, which doubles the number of distinct pictures. */
  flipped: boolean;
}

/** The look of the placeholder of a profile; the same seed always gives the same look. */
export function placeholderLook(seed: string): PlaceholderLook {
  const hash = hashOf(seed);
  const palette = PALETTES[(hash >>> 8) % PALETTES.length] ?? PALETTES[0];
  return {
    motif: MOTIFS[hash % MOTIFS.length] ?? MOTIFS[0],
    background: palette[0],
    ink: palette[1],
    flipped: ((hash >>> 16) & 1) === 1,
  };
}

/** The first letter of a name in upper case, or an empty string for a name without letters. */
export function initialOf(name: string): string {
  const first = Array.from(name.trim()).find((char) => /\p{L}|\p{N}/u.test(char));
  return first ? first.toLocaleUpperCase("uk") : "";
}
