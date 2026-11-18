import type { Page } from "@playwright/test";
import { uk } from "../src/i18n/uk";
import { startSession } from "./support/api";
import { expect, test } from "./support/fixtures";
import { measureFocusIndicator, smallTargets } from "./support/probes";
import { appReady, stubTiles } from "./support/ui";
import type { World } from "./support/world";

/** Reflow, zoom and text size, text spacing, reduced motion, forced colours and target size. */
interface Target {
  name: string;
  path: string;
  as?: (world: World) => string;
  /** Brings the page into a heavier state (map shown, long lists, open confirmations). */
  prepare?: (page: Page) => Promise<void>;
}

const TARGETS: Target[] = [
  { name: "landing", path: "/" },
  { name: "about", path: "/about" },
  { name: "login", path: "/login" },
  { name: "register", path: "/register" },
  { name: "not found", path: "/there-is-no-such-page" },
  {
    name: "profile with map",
    path: "/profile",
    as: (w) => w.rich.token,
    prepare: async (page) => {
      await page.getByRole("combobox", { name: uk.profile.location.place }).selectOption("kyiv");
      await expect(page.locator(".leaflet-container")).toBeVisible();
      await page.getByRole("button", { name: uk.profile.manage.deleteAll.trigger }).click();
    },
  },
  { name: "matches", path: "/matches", as: (w) => w.rich.token },
  { name: "invitations", path: "/invitations", as: (w) => w.rich.token },
];

async function open(page: Page, world: World, target: Target): Promise<void> {
  await stubTiles(page.context());
  if (target.as) await startSession(page.context(), target.as(world));
  await page.goto(target.path);
  await appReady(page);
  await page.waitForLoadState("networkidle");
  if (target.path === "/matches") await expect(page.getByRole("article").first()).toBeVisible();
  if (target.prepare) await target.prepare(page);
}

/** Horizontal overflow of the document, in CSS px (positive when the page scrolls sideways). */
async function horizontalOverflow(page: Page): Promise<number> {
  return page.evaluate(() => {
    const root = document.scrollingElement ?? document.documentElement;
    return root.scrollWidth - root.clientWidth;
  });
}

/** Elements that cut their text off: overflow clipped while the content is larger than the box. */
async function clippedText(page: Page): Promise<string[]> {
  return page.evaluate(() => {
    const clipped: string[] = [];
    for (const element of document.querySelectorAll<HTMLElement>("body *")) {
      if (element.closest(".leaflet-container, .visually-hidden")) continue;
      const style = getComputedStyle(element);
      if (style.visibility === "hidden" || style.display === "none") continue;
      const clips = (value: string) => value === "hidden" || value === "clip";
      const horizontally = clips(style.overflowX) && element.scrollWidth > element.clientWidth + 1;
      const vertically = clips(style.overflowY) && element.scrollHeight > element.clientHeight + 1;
      if ((horizontally || vertically) && (element.textContent ?? "").trim() !== "") {
        clipped.push(`${element.tagName.toLowerCase()}.${String(element.className).slice(0, 30)}`);
      }
    }
    return clipped;
  });
}

test.describe("reflow at 320 px (WCAG 1.4.10)", () => {
  test.use({ viewport: { width: 320, height: 640 } });

  for (const target of TARGETS) {
    test(`${target.name}: no horizontal scroll`, async ({ page, world }) => {
      await open(page, world, target);
      expect(await horizontalOverflow(page)).toBeLessThanOrEqual(0);
    });
  }

  test("the open menu does not scroll sideways either", async ({ page, world }) => {
    await open(page, world, { name: "matches", path: "/matches", as: (w) => w.rich.token });
    await page.getByRole("button", { name: uk.nav.menu }).click();
    expect(await horizontalOverflow(page)).toBeLessThanOrEqual(0);
  });
});

test.describe("zoom and text size (WCAG 1.4.4, 1.4.12)", () => {
  // 200 % zoom of a 1280 px window leaves 640 CSS px; 400 % leaves 320 (covered above)
  test.describe("200 % zoom", () => {
    test.use({ viewport: { width: 640, height: 450 } });
    for (const target of TARGETS) {
      test(`${target.name}: no horizontal scroll, no clipped text`, async ({ page, world }) => {
        await open(page, world, target);
        expect(await horizontalOverflow(page)).toBeLessThanOrEqual(0);
        expect(await clippedText(page)).toEqual([]);
      });
    }
  });

  test.describe("text enlarged to 200 %", () => {
    test.use({ viewport: { width: 1280, height: 800 } });
    for (const target of TARGETS) {
      test(`${target.name}: nothing is cut off`, async ({ page, world }) => {
        await open(page, world, target);
        await page.addStyleTag({ content: "html { font-size: 200% !important; }" });
        expect(await horizontalOverflow(page)).toBeLessThanOrEqual(0);
        expect(await clippedText(page)).toEqual([]);
      });
    }
  });

  test.describe("text spacing of WCAG 1.4.12", () => {
    test.use({ viewport: { width: 1280, height: 800 } });
    for (const target of TARGETS) {
      test(`${target.name}: nothing is cut off`, async ({ page, world }) => {
        await open(page, world, target);
        await page.addStyleTag({
          content: `* { line-height: 1.5 !important; letter-spacing: 0.12em !important; word-spacing: 0.16em !important; }
            p { margin-bottom: 2em !important; }`,
        });
        expect(await horizontalOverflow(page)).toBeLessThanOrEqual(0);
        expect(await clippedText(page)).toEqual([]);
      });
    }
  });
});

/** Longest animation or transition on the page, in seconds, over all elements and pseudo-elements. */
async function longestMotion(page: Page): Promise<{ seconds: number; where: string }> {
  return page.evaluate(() => {
    const seconds = (list: string) =>
      Math.max(...list.split(",").map((part) => (part.trim().endsWith("ms") ? parseFloat(part) / 1000 : parseFloat(part)) || 0));
    let longest = { seconds: 0, where: "" };
    for (const element of document.querySelectorAll("body, body *")) {
      for (const pseudo of [null, "::before", "::after"]) {
        const style = getComputedStyle(element, pseudo);
        const total = Math.max(
          seconds(style.transitionDuration) + seconds(style.transitionDelay),
          style.animationName === "none" ? 0 : seconds(style.animationDuration) + seconds(style.animationDelay),
        );
        if (total > longest.seconds) {
          longest = { seconds: total, where: `${element.tagName.toLowerCase()}.${String(element.className).slice(0, 30)}${pseudo ?? ""}` };
        }
      }
    }
    return longest;
  });
}

test.describe("prefers-reduced-motion (WCAG 2.3.3)", () => {
  test("without the preference the interface does move", async ({ page }) => {
    await page.emulateMedia({ reducedMotion: "no-preference" });
    await page.goto("/login");
    await appReady(page);
    expect((await longestMotion(page)).seconds).toBeGreaterThan(0.05);
  });

  for (const target of TARGETS) {
    test(`${target.name}: transitions and animations are negligible`, async ({ page, world }) => {
      await page.emulateMedia({ reducedMotion: "reduce" });
      await open(page, world, target);
      const longest = await longestMotion(page);
      expect(longest.seconds, longest.where).toBeLessThanOrEqual(0.05);
      expect(await page.evaluate(() => getComputedStyle(document.documentElement).scrollBehavior)).not.toBe("smooth");
    });
  }

  test("a pending request shows a spinner that does not rotate", async ({ page, world }) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    await startSession(page.context(), world.rich.token);
    await page.route("**/api/v1/matches**", async (route) => {
      await new Promise((resolve) => setTimeout(resolve, 1500));
      await route.continue();
    });
    await page.goto("/matches");
    const loader = page.getByRole("status").filter({ hasText: uk.feed.loading });
    await expect(loader).toBeVisible();
    const duration = await loader.locator("span").first().evaluate((spinner) => getComputedStyle(spinner).animationDuration);
    expect(parseFloat(duration)).toBeLessThanOrEqual(0.05);
  });
});

test.describe("forced colours (Windows high contrast)", () => {
  test.use({ viewport: { width: 1280, height: 900 } });

  test("focus and borders remain visible", async ({ page, world }) => {
    await page.emulateMedia({ forcedColors: "active" });
    await stubTiles(page.context());
    await startSession(page.context(), world.rich.token);
    await page.goto("/profile");
    await appReady(page);
    await page.waitForLoadState("networkidle");
    expect(await page.evaluate(() => matchMedia("(forced-colors: active)").matches)).toBe(true);

    // Every kind of control keeps a border that the system colours can paint
    const unbordered = await page.evaluate(() => {
      const missing: string[] = [];
      const kinds = ["input[type=text]", "select", "button.button", "textarea", "input[type=checkbox]"];
      for (const selector of kinds) {
        for (const element of document.querySelectorAll<HTMLElement>(selector)) {
          if (element.getClientRects().length === 0) continue;
          const style = getComputedStyle(element);
          const hasBorder = style.borderStyle !== "none" && parseFloat(style.borderTopWidth) > 0;
          // A native checkbox is drawn by the browser in the system colours
          const native = style.appearance !== "none" && selector.includes("checkbox");
          if (!hasBorder && !native) missing.push(`${selector} ${element.getAttribute("name") ?? ""}`);
        }
      }
      return missing;
    });
    expect(unbordered).toEqual([]);

    // The focus indicator is still an outline of a visible width
    for (const label of [uk.profile.about.displayName, uk.profile.submit]) {
      const control = page.getByLabel(label).or(page.getByRole("button", { name: label })).first();
      await control.focus();
      const indicator = await measureFocusIndicator(page);
      expect(indicator?.outlineStyle, label).not.toBe("none");
      expect(indicator?.outlineWidthPx ?? 0, label).toBeGreaterThanOrEqual(2);
    }
    await page.keyboard.press("Tab");
    expect((await measureFocusIndicator(page))?.outlineStyle).not.toBe("none");
  });

  test("cards and badges keep an edge", async ({ page, world }) => {
    await page.emulateMedia({ forcedColors: "active" });
    await startSession(page.context(), world.rich.token);
    await page.goto("/matches");
    const card = page.getByRole("article").first();
    await expect(card).toBeVisible();
    const edges = await card.evaluate((element) => {
      const border = (target: Element) => {
        const style = getComputedStyle(target);
        return style.borderStyle !== "none" && parseFloat(style.borderTopWidth) > 0;
      };
      const badge = element.querySelector("span[class*=badge]");
      return { card: border(element), badge: badge ? border(badge) : true };
    });
    expect(edges).toEqual({ card: true, badge: true });
  });
});

test.describe("target size (WCAG 2.5.8, level AA of WCAG 2.2)", () => {
  for (const width of [320, 1280]) {
    test.describe(`${width}px`, () => {
      test.use({ viewport: { width, height: 900 } });
      for (const target of TARGETS) {
        test(`${target.name}: controls are at least 24 x 24 CSS px`, async ({ page, world }, testInfo) => {
          await open(page, world, target);
          const small = await smallTargets(page);
          if (small.length > 0) testInfo.annotations.push({ type: "target-size", description: small.join(" | ") });
          expect(small).toEqual([]);
        });
      }
    });
  }
});
