import type { Page } from "@playwright/test";
import { uk } from "../src/i18n/uk";
import { startSession } from "./support/api";
import { expect, test } from "./support/fixtures";
import { measureFocusIndicator } from "./support/probes";
import { appReady, mainNav, stubTiles } from "./support/ui";
import type { World } from "./support/world";

/**
 * Keyboard-only use: the skip link, a logical tab order, a visible focus indicator with enough
 * contrast, no trap (the map and the menu included), Escape, and focus after a route change.
 */
const MAX_STOPS = 400;

interface Stop {
  /** Position of the element in document order. */
  order: number;
  label: string;
}

/** Presses Tab from the top of the page until focus leaves the document or wraps; records every stop. */
async function tabThrough(page: Page, check?: (page: Page) => Promise<void>): Promise<Stop[]> {
  await page.evaluate(() => {
    (document.activeElement as HTMLElement | null)?.blur();
    window.scrollTo(0, 0);
  });
  const stops: Stop[] = [];
  for (let step = 0; step < MAX_STOPS; step += 1) {
    await page.keyboard.press("Tab");
    const stop = await page.evaluate(() => {
      const element = document.activeElement;
      if (!element || element === document.body) return null;
      const all = [...document.querySelectorAll("*")];
      return {
        order: all.indexOf(element),
        label: `${element.tagName.toLowerCase()} "${(element.getAttribute("aria-label") ?? element.textContent ?? "").trim().slice(0, 30)}"`,
      };
    });
    // Focus has left the page content (browser chrome or the start again): the walk is complete
    if (stop === null) return stops;
    if (stops.length > 0 && stop.order <= (stops[stops.length - 1] as Stop).order) {
      // A wrap to the first element is the end of the walk; going backwards in the middle is a defect
      if (stop.order === (stops[0] as Stop).order) return stops;
      throw new Error(`Tab order goes backwards: ${(stops[stops.length - 1] as Stop).label} -> ${stop.label}`);
    }
    stops.push(stop);
    if (check) await check(page);
  }
  throw new Error(`Focus never left the page in ${MAX_STOPS} steps: a keyboard trap`);
}

/** Every stop must show an outline of at least 2 px with 3:1 contrast against what lies behind it. */
async function expectVisibleFocus(page: Page): Promise<void> {
  const indicator = await measureFocusIndicator(page);
  expect(indicator, "something has focus").not.toBeNull();
  if (!indicator) return;
  const visible =
    indicator.outlineStyle !== "none" && indicator.outlineWidthPx >= 2 && (indicator.contrast ?? 0) >= 3;
  expect(visible, `focus indicator of ${indicator.label}: ${JSON.stringify(indicator)}`).toBe(true);
  expect(indicator.inViewport, `${indicator.label} is scrolled into view`).toBe(true);
}

const PAGES: { name: string; path: string; as?: (world: World) => string }[] = [
  { name: "landing", path: "/" },
  { name: "login", path: "/login" },
  { name: "profile", path: "/profile", as: (w) => w.rich.token },
  { name: "matches", path: "/matches", as: (w) => w.rich.token },
  { name: "invitations", path: "/invitations", as: (w) => w.rich.token },
];

for (const scheme of ["light", "dark"] as const) {
  test.describe(`tab order and focus indicator, ${scheme}`, () => {
    test.use({ colorScheme: scheme, viewport: { width: 1280, height: 900 } });

    for (const entry of PAGES) {
      test(entry.name, async ({ page, world }) => {
        await stubTiles(page.context());
        if (entry.as) await startSession(page.context(), entry.as(world));
        await page.goto(entry.path);
        await appReady(page);
        await page.waitForLoadState("networkidle");
        const stops = await tabThrough(page, expectVisibleFocus);
        expect(stops.length).toBeGreaterThan(3);
        // The skip link is the first stop, as the browser would have it on a fresh load
        expect(stops[0]?.label).toContain(uk.a11y.skipToContent);
      });
    }
  });
}

test("the skip link appears on focus and moves focus to the main region", async ({ page }) => {
  await page.goto("/about");
  await appReady(page);
  await page.keyboard.press("Tab");
  const skip = page.getByRole("link", { name: uk.a11y.skipToContent });
  await expect(skip).toBeFocused();
  const box = await skip.boundingBox();
  expect(box?.y ?? -1).toBeGreaterThanOrEqual(0);
  await page.keyboard.press("Enter");
  await expect(page.locator("#main-content")).toBeFocused();
  // The next Tab starts inside the content, not in the navigation again
  await page.keyboard.press("Tab");
  expect(await page.evaluate(() => document.activeElement?.closest("nav, header") === null)).toBe(true);
});

test.describe("the location map", () => {
  test("is no keyboard trap and the whole picker works without a pointer", async ({ page, world }) => {
    await stubTiles(page.context());
    await startSession(page.context(), world.bare.token);
    await page.goto("/profile");
    await expect(page.getByRole("heading", { name: uk.profile.onboarding.title })).toBeVisible();

    // A native list is operated by the browser (type-ahead differs between platforms), so the
    // place is chosen directly; the map and the buttons after it are driven with keys
    await page.getByRole("combobox", { name: uk.profile.location.place }).selectOption("kyiv");
    await expect(page.locator(".leaflet-container")).toBeVisible();

    const map = page.locator(".leaflet-container");
    await map.focus();
    await expect(map).toBeFocused();
    // The map and its own controls show where focus is, like the rest of the page
    await expectVisibleFocus(page);
    for (const name of [uk.profile.location.zoomIn, uk.profile.location.zoomOut]) {
      await page.getByRole("button", { name }).focus();
      await expectVisibleFocus(page);
    }
    // A link inside running text must not rely on colour alone (WCAG 1.4.1)
    const credit = page.locator(".leaflet-control-attribution a");
    expect(await credit.evaluate((link) => getComputedStyle(link).textDecorationLine)).toContain("underline");
    // Nothing on the map speaks English to a Ukrainian page (WCAG 3.1.2): no English titles or labels
    const english = await map.evaluate((container) =>
      [...container.querySelectorAll("[title], [aria-label]")]
        .map((element) => element.getAttribute("title") ?? element.getAttribute("aria-label") ?? "")
        .filter((label) => /[A-Za-z]{3}/.test(label) && !/[Ѐ-ӿ]/.test(label)),
    );
    expect(english).toEqual([]);
    await map.focus();
    await page.keyboard.press("ArrowRight");
    await page.keyboard.press("Equal");
    await expect(map).toBeFocused();

    // Tab leaves the map in both directions
    await page.keyboard.press("Tab");
    expect(await page.evaluate(() => document.activeElement?.className.includes("leaflet-container"))).toBe(false);
    await page.keyboard.press("Shift+Tab");
    await page.keyboard.press("Shift+Tab");
    await expect(page.getByRole("button", { name: uk.profile.location.hideMap })).toBeFocused();

    // Forward again until the next field group: the walk reaches the save button
    await map.focus();
    let reached = false;
    for (let step = 0; step < 60 && !reached; step += 1) {
      await page.keyboard.press("Tab");
      reached = await page
        .getByRole("button", { name: uk.profile.submit })
        .evaluate((button) => button === document.activeElement);
    }
    expect(reached, "the save button is reachable after the map").toBe(true);

    // The size of the area is one group of radio buttons: the arrow keys move the choice, and a
    // city or district alone leaves no map to pass through
    const place = uk.profile.location.precision.place.name;
    await page.getByRole("radio", { name: new RegExp(`^${uk.profile.location.precision["4km"].name}`) }).focus();
    await page.keyboard.press("ArrowLeft");
    await expect(page.getByRole("radio", { name: new RegExp(`^${place}`) })).toBeChecked();
    await expect(page.getByRole("button", { name: uk.profile.location.hideMap })).toHaveCount(0);
    await expect(page.locator(".leaflet-container")).toHaveCount(0);
  });
});

test.describe("the menu on a narrow screen", () => {
  test.use({ viewport: { width: 360, height: 800 } });

  test("opens with Enter, is reachable by Tab and closes with Escape, which returns focus", async ({
    page,
  }) => {
    await page.goto("/");
    await appReady(page);
    const button = page.getByRole("button", { name: uk.nav.menu });
    await expect(button).toHaveAttribute("aria-expanded", "false");
    await button.focus();
    await page.keyboard.press("Enter");
    await expect(button).toHaveAttribute("aria-expanded", "true");

    await page.keyboard.press("Tab");
    await expect(mainNav(page).getByRole("link").first()).toBeFocused();
    // Escape works from inside the menu and puts focus back on the button
    await page.keyboard.press("Escape");
    await expect(button).toHaveAttribute("aria-expanded", "false");
    await expect(button).toBeFocused();
    await expect(mainNav(page)).toBeHidden();
  });

  test("closes after a link was followed and the new page heading has focus", async ({ page }) => {
    await page.goto("/");
    await appReady(page);
    const button = page.getByRole("button", { name: uk.nav.menu });
    await button.focus();
    await page.keyboard.press("Enter");
    await page.keyboard.press("Tab");
    await page.keyboard.press("Tab");
    await page.keyboard.press("Enter");
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(uk.pages.about.title);
    await expect(page.getByRole("heading", { level: 1 })).toBeFocused();
    await expect(button).toHaveAttribute("aria-expanded", "false");
  });
});

test.describe("main flows with the keyboard only", () => {
  test("open the partner list and cancel an invitation question", async ({ page, world }) => {
    await startSession(page.context(), world.rich.token);
    await page.goto("/");
    await appReady(page);

    await mainNav(page).getByRole("link", { name: uk.nav.matches }).focus();
    await page.keyboard.press("Enter");
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(uk.pages.matches.title);
    await expect(page.getByRole("heading", { level: 1 })).toBeFocused();
    const first = page.getByRole("article").first();
    await expect(first).toBeVisible();

    const trigger = first.getByRole("button", { name: uk.feed.invite.trigger });
    await trigger.focus();
    await page.keyboard.press("Enter");
    await expect(first.getByRole("heading", { name: uk.feed.invite.title })).toBeFocused();
    await page.keyboard.press("Tab");
    await expect(first.getByRole("button", { name: uk.profile.manage.cancel })).toBeFocused();
    await page.keyboard.press("Enter");
    await expect(trigger).toBeFocused();
  });

  test("sports rows: adding moves focus to the new row, removing hands it to the add button", async ({
    page,
    world,
  }) => {
    await startSession(page.context(), world.bare.token);
    await page.goto("/profile");
    const add = page.getByRole("button", { name: uk.profile.sports.add });
    await add.focus();
    await page.keyboard.press("Enter");
    await expect(page.getByLabel(uk.profile.sports.sport).nth(1)).toBeFocused();
    await page.getByRole("button", { name: uk.profile.sports.remove(2) }).focus();
    await page.keyboard.press("Enter");
    await expect(add).toBeFocused();
  });

  test("tabs of the invitations page follow the arrow-key pattern", async ({ page, world }) => {
    test.skip(!world.demo, "E2E_DEMO_PASSWORD is not set");
    await startSession(page.context(), world.rich.token);
    await page.goto("/invitations");
    const incoming = page.getByRole("tab", { name: uk.invitations.incoming });
    await incoming.focus();
    await page.keyboard.press("ArrowRight");
    const outgoing = page.getByRole("tab", { name: uk.invitations.outgoing });
    await expect(outgoing).toBeFocused();
    await expect(outgoing).toHaveAttribute("aria-selected", "true");
    await page.keyboard.press("Home");
    await expect(incoming).toHaveAttribute("aria-selected", "true");
  });
});
