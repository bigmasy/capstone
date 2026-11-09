import type { Locator, Page } from "@playwright/test";

/** What the focus indicator of the focused element looks like, measured in the page. */
export interface FocusIndicator {
  label: string;
  outlineStyle: string;
  outlineWidthPx: number;
  /** Contrast of the outline against the colour behind it; null when it could not be measured. */
  contrast: number | null;
  hasBoxShadow: boolean;
  /** Part of the focused element that lies inside the viewport, to catch an off-screen focus. */
  inViewport: boolean;
}

/** Measures the focus indicator of `document.activeElement`. */
export async function measureFocusIndicator(page: Page): Promise<FocusIndicator | null> {
  return page.evaluate(() => {
    const element = document.activeElement;
    if (!element || element === document.body || element === document.documentElement) return null;

    const parse = (value: string): [number, number, number, number] | null => {
      const match = /rgba?\(([^)]+)\)/.exec(value);
      if (!match?.[1]) return null;
      const parts = match[1].split(/[ ,/]+/).filter(Boolean).map(Number);
      const [r, g, b] = parts;
      if (r === undefined || g === undefined || b === undefined) return null;
      return [r, g, b, parts[3] ?? 1];
    };
    const channel = (v: number) => {
      const c = v / 255;
      return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
    };
    const luminance = (c: [number, number, number, number]) =>
      0.2126 * channel(c[0]) + 0.7152 * channel(c[1]) + 0.0722 * channel(c[2]);
    const blend = (top: [number, number, number, number], bottom: [number, number, number, number]) =>
      [
        top[0] * top[3] + bottom[0] * (1 - top[3]),
        top[1] * top[3] + bottom[1] * (1 - top[3]),
        top[2] * top[3] + bottom[2] * (1 - top[3]),
        1,
      ] as [number, number, number, number];

    // The outline is drawn outside the element, over whatever lies behind its parent
    let behind: [number, number, number, number] = [255, 255, 255, 1];
    const stack: [number, number, number, number][] = [];
    for (let node = element.parentElement; node; node = node.parentElement) {
      const colour = parse(getComputedStyle(node).backgroundColor);
      if (colour && colour[3] > 0) {
        stack.push(colour);
        if (colour[3] === 1) break;
      }
    }
    for (const layer of stack.reverse()) behind = blend(layer, behind);

    const style = getComputedStyle(element);
    const outline = parse(style.outlineColor);
    let contrast: number | null = null;
    if (outline) {
      const ink = blend(outline, behind);
      const [light, dark] = [luminance(ink), luminance(behind)].sort((a, b) => b - a) as [number, number];
      contrast = (light + 0.05) / (dark + 0.05);
    }
    const box = element.getBoundingClientRect();
    return {
      label: `${element.tagName.toLowerCase()}${element.id ? `#${element.id}` : ""} "${(
        element.getAttribute("aria-label") ?? element.textContent ?? ""
      )
        .trim()
        .slice(0, 40)}"`,
      outlineStyle: style.outlineStyle,
      outlineWidthPx: parseFloat(style.outlineWidth) || 0,
      contrast,
      hasBoxShadow: style.boxShadow !== "none",
      inViewport:
        box.bottom > 0 && box.right > 0 && box.top < window.innerHeight && box.left < window.innerWidth,
    };
  });
}

/** Walks the headings of the page in document order; returns the problems found. */
export async function headingProblems(page: Page): Promise<string[]> {
  return page.evaluate(() => {
    const problems: string[] = [];
    const headings = [...document.querySelectorAll<HTMLElement>("h1,h2,h3,h4,h5,h6,[role=heading]")].filter(
      (heading) => heading.getClientRects().length > 0,
    );
    const levels = headings.map((heading) => {
      const aria = heading.getAttribute("aria-level");
      return aria ? Number(aria) : Number(heading.tagName.slice(1));
    });
    const h1Count = levels.filter((level) => level === 1).length;
    if (h1Count !== 1) problems.push(`expected exactly one h1, found ${h1Count}`);
    let previous = 0;
    headings.forEach((heading, index) => {
      const level = levels[index] ?? 0;
      if (level > previous + 1) {
        problems.push(
          `h${level} "${(heading.textContent ?? "").trim().slice(0, 40)}" follows h${previous}`,
        );
      }
      previous = level;
    });
    return problems;
  });
}

/** Checks that the landmarks are unique where they must be, and that repeated ones are labelled. */
export async function landmarkProblems(page: Page): Promise<string[]> {
  return page.evaluate(() => {
    const problems: string[] = [];
    // A header or footer inside a section, article, aside, main or nav is not a page landmark
    const topLevel = (tag: string) =>
      [...document.querySelectorAll(tag)].filter(
        (element) => element.closest("article, aside, main, nav, section") === null,
      ).length;
    const single: [string, number][] = [
      ["banner", topLevel("header") + document.querySelectorAll("[role=banner]").length],
      ["main", document.querySelectorAll("main, [role=main]").length],
      ["contentinfo", topLevel("footer") + document.querySelectorAll("[role=contentinfo]").length],
    ];
    for (const [name, found] of single) {
      if (found !== 1) problems.push(`expected one ${name}, found ${found}`);
    }
    const navs = [...document.querySelectorAll("nav, [role=navigation]")];
    const names = navs.map((nav) => nav.getAttribute("aria-label") ?? nav.getAttribute("aria-labelledby") ?? "");
    if (navs.length > 1) {
      if (names.some((name) => name === "")) problems.push("a navigation landmark has no name");
      if (new Set(names).size !== names.length) problems.push("navigation landmarks share a name");
    }
    return problems;
  });
}

/** Elements whose box is smaller than 24 x 24 CSS px, inline links in running text excepted. */
export async function smallTargets(page: Page): Promise<string[]> {
  return page.evaluate(() => {
    const selector =
      'a[href], button, input:not([type="hidden"]), select, textarea, [role="tab"], [role="button"], summary';
    const small: string[] = [];
    for (const element of document.querySelectorAll<HTMLElement>(selector)) {
      const box = element.getBoundingClientRect();
      if (box.width === 0 || box.height === 0) continue;
      const style = getComputedStyle(element);
      if (style.visibility === "hidden") continue;
      // The skip link sits above the viewport until it is focused
      if (box.bottom <= 0) continue;
      // WCAG 2.5.8 exempts a link that sits inside a sentence
      const inline = element.tagName === "A" && style.display === "inline" && element.closest("p, li, dd, span") !== null;
      if (inline) continue;
      if (box.width < 24 || box.height < 24) {
        small.push(
          `${element.tagName.toLowerCase()} "${(element.getAttribute("aria-label") ?? element.textContent ?? "")
            .trim()
            .slice(0, 30)}" ${Math.round(box.width)}x${Math.round(box.height)}`,
        );
      }
    }
    return small;
  });
}

/**
 * Contrast of the text of an element as it is really painted, including `opacity` of the element
 * and of its ancestors (axe skips controls that are marked disabled, so this measures them).
 */
export async function paintedContrast(locator: Locator): Promise<number> {
  return locator.evaluate((element) => {
    type Rgba = [number, number, number, number];
    const parse = (value: string): Rgba => {
      const match = /rgba?\(([^)]+)\)/.exec(value);
      const parts = (match?.[1] ?? "0,0,0,0").split(/[ ,/]+/).filter(Boolean).map(Number);
      return [parts[0] ?? 0, parts[1] ?? 0, parts[2] ?? 0, parts[3] ?? 1];
    };
    const mix = (top: Rgba, alpha: number, bottom: Rgba): Rgba => {
      const a = top[3] * alpha;
      return [
        top[0] * a + bottom[0] * (1 - a),
        top[1] * a + bottom[1] * (1 - a),
        top[2] * a + bottom[2] * (1 - a),
        1,
      ];
    };
    const channel = (v: number) => {
      const c = v / 255;
      return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
    };
    const luminance = (c: Rgba) => 0.2126 * channel(c[0]) + 0.7152 * channel(c[1]) + 0.0722 * channel(c[2]);

    // What lies behind the element, from the page background outwards
    const chain: Element[] = [];
    for (let node: Element | null = element; node; node = node.parentElement) chain.push(node);
    let behind: Rgba = [255, 255, 255, 1];
    for (const node of chain.slice(1).reverse()) {
      const style = getComputedStyle(node);
      behind = mix(parse(style.backgroundColor), Number(style.opacity), behind);
    }
    // Opacity of the element and of everything above it applies to the whole group
    const opacity = chain.reduce((product, node) => product * Number(getComputedStyle(node).opacity), 1);
    const own = getComputedStyle(element);
    const ownBackground = mix(parse(own.backgroundColor), 1, behind);
    const paintedBackground = mix(ownBackground, opacity, behind);
    const paintedText = mix(parse(own.color), opacity, behind);
    const [light, dark] = [luminance(paintedText), luminance(paintedBackground)].sort((a, b) => b - a) as [
      number,
      number,
    ];
    return (light + 0.05) / (dark + 0.05);
  });
}
