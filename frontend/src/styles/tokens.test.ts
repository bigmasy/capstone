import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const css = readFileSync(join(dirname(fileURLToPath(import.meta.url)), "tokens.css"), "utf8");

const DARK_MARKER = "@media (prefers-color-scheme: dark)";

/** Collects `--name: #rrggbb;` declarations. */
function readColors(source: string): Record<string, string> {
  const colors: Record<string, string> = {};
  for (const match of source.matchAll(/--([\w-]+):\s*(#[0-9a-fA-F]{6})\s*;/g)) {
    colors[match[1] as string] = match[2] as string;
  }
  return colors;
}

/** Relative luminance as defined by WCAG 2.1. */
function luminance(hex: string): number {
  const [r, g, b] = [1, 3, 5].map((start) => {
    const channel = parseInt(hex.slice(start, start + 2), 16) / 255;
    return channel <= 0.03928 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4;
  }) as [number, number, number];
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function contrast(foreground: string, background: string): number {
  const [light, dark] = [luminance(foreground), luminance(background)].sort((a, b) => b - a) as [
    number,
    number,
  ];
  return (light + 0.05) / (dark + 0.05);
}

const darkStart = css.indexOf(DARK_MARKER);
const light = readColors(css.slice(0, darkStart));
// The dark block overrides the light values; tokens it does not mention keep their light value
const dark = { ...light, ...readColors(css.slice(darkStart)) };

const palettes: [string, Record<string, string>][] = [
  ["light", light],
  ["dark", dark],
];

const surfaces = ["color-bg", "color-surface", "color-card", "color-tint"];

// [foreground token, background token]
const textPairs: [string, string][] = [
  ...surfaces.flatMap((surface): [string, string][] => [
    ["color-text", surface],
    ["color-text-muted", surface],
    ["color-primary", surface],
    ["color-primary-hover", surface],
    ["color-accent", surface],
  ]),
  ["color-on-primary", "color-primary"],
  ["color-on-primary", "color-primary-hover"],
  ["color-primary", "color-primary-soft"],
  ["color-on-primary-soft", "color-primary-soft"],
  ["color-text", "color-primary-soft"],
  ["color-on-accent", "color-accent"],
  ["color-on-accent-soft", "color-accent-soft"],
  ["color-error", "color-bg"],
  ["color-error", "color-card"],
  ["color-error", "color-error-bg"],
  ["color-on-error", "color-error"],
  ["color-success", "color-success-bg"],
  ["color-success", "color-card"],
  ["color-warning", "color-warning-bg"],
  ["color-text", "color-success-bg"],
  ["color-text", "color-warning-bg"],
  ["color-text", "color-error-bg"],
  ["color-on-inverse", "color-inverse-bg"],
  ["color-on-inverse-muted", "color-inverse-bg"],
  ["color-inverse-link", "color-inverse-bg"],
];

const componentPairs: [string, string][] = [
  ...surfaces.flatMap((surface): [string, string][] => [
    ["color-border", surface],
    ["color-focus", surface],
    ["color-primary", surface],
  ]),
  ["color-focus", "color-primary-soft"],
  ["color-error", "color-bg"],
  ["color-error", "color-card"],
  ["color-focus-inverse", "color-inverse-bg"],
  ["color-on-inverse", "color-inverse-bg"],
];

describe.each(palettes)("design tokens (%s palette)", (_name, colors) => {
  it.each(textPairs)("text %s on %s has contrast of at least 4.5:1", (foreground, background) => {
    expect(contrast(colors[foreground] as string, colors[background] as string)).toBeGreaterThanOrEqual(4.5);
  });

  it.each(componentPairs)(
    "component colour %s against %s has contrast of at least 3:1",
    (foreground, background) => {
      expect(contrast(colors[foreground] as string, colors[background] as string)).toBeGreaterThanOrEqual(3);
    },
  );

  it("defines every colour used in the pairs", () => {
    for (const name of [...textPairs, ...componentPairs].flat()) {
      expect(colors[name], name).toBeDefined();
    }
  });
});

describe("token file", () => {
  it("has a dark palette that overrides the surfaces and the text", () => {
    expect(darkStart).toBeGreaterThan(0);
    for (const name of ["color-bg", "color-card", "color-text", "color-primary", "color-inverse-bg"]) {
      expect(dark[name], name).not.toBe(light[name]);
    }
  });

  it("declares reduced motion handling next to the duration tokens in global.css", () => {
    const global = readFileSync(join(dirname(fileURLToPath(import.meta.url)), "global.css"), "utf8");
    expect(global).toContain("prefers-reduced-motion: reduce");
    expect(global).toContain("forced-colors: active");
  });
});
