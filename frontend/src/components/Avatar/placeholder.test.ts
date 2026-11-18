import { describe, expect, it } from "vitest";
import { hashOf, initialOf, MOTIFS, PALETTES, placeholderLook } from "./placeholder";

const ids = Array.from(
  { length: 400 },
  (_, index) => `6f1c1c0e-0000-4000-8000-${index.toString(16).padStart(12, "0")}`,
);

describe("placeholderLook", () => {
  it("gives the same profile the same picture every time", () => {
    for (const id of ids.slice(0, 20)) {
      expect(placeholderLook(id)).toEqual(placeholderLook(id));
    }
  });

  it("uses every scene and every colour pair across many profiles", () => {
    const looks = ids.map(placeholderLook);

    expect(new Set(looks.map((look) => look.motif))).toEqual(new Set(MOTIFS));
    expect(new Set(looks.map((look) => look.background)).size).toBe(PALETTES.length);
    expect(new Set(looks.map((look) => look.flipped))).toEqual(new Set([true, false]));
  });

  it("takes its colours from the design tokens only, so both themes are covered", () => {
    for (const look of ids.slice(0, 50).map(placeholderLook)) {
      expect(look.background).toMatch(/^var\(--color-[a-z-]+\)$/);
      expect(look.ink).toMatch(/^var\(--color-[a-z-]+\)$/);
    }
  });
});

describe("hashOf", () => {
  it("is a stable unsigned 32-bit number", () => {
    expect(hashOf("")).toBe(0x811c9dc5);
    expect(hashOf("a")).toBe(0xe40c292c);
    expect(hashOf("Поруч")).toBe(hashOf("Поруч"));
    expect(hashOf("a")).not.toBe(hashOf("b"));
  });
});

describe("initialOf", () => {
  it.each([
    ["Олена", "О"],
    ["  іван", "І"],
    ["єва", "Є"],
    ["@nick", "N"],
    ["42-й", "4"],
    ["—", ""],
    ["", ""],
  ])("takes the first letter or digit of %j in upper case", (name, initial) => {
    expect(initialOf(name)).toBe(initial);
  });
});
