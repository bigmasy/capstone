import { expect, type BrowserContext, type Locator, type Page } from "@playwright/test";
import { uk } from "../../src/i18n/uk";

/** 1x1 transparent PNG, served instead of map tiles so that no test depends on the tile server. */
const BLANK_TILE = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=",
  "base64",
);

/** Answers map tile requests locally. */
export async function stubTiles(context: BrowserContext): Promise<void> {
  await context.route("https://tile.openstreetmap.org/**", (route) =>
    route.fulfill({ status: 200, contentType: "image/png", body: BLANK_TILE }),
  );
}

/** Waits until the single-page app has rendered its first heading. */
export async function appReady(page: Page): Promise<void> {
  await expect(page.locator("main h1").first()).toBeVisible();
}

/** Keys whose presence in a public response would break the privacy promise. */
export const FORBIDDEN_PUBLIC_KEYS = [
  "latitude",
  "longitude",
  "lat",
  "lng",
  "lon",
  "cell",
  "capabilities",
  "category",
  "equipment",
  "functional_data_consent",
  "email",
  "password",
  "user_id",
];

/** Returns the paths of forbidden keys found anywhere in a parsed JSON value. */
export function findForbiddenKeys(value: unknown, path = "$"): string[] {
  if (Array.isArray(value)) {
    return value.flatMap((item, index) => findForbiddenKeys(item, `${path}[${index}]`));
  }
  if (value !== null && typeof value === "object") {
    return Object.entries(value).flatMap(([key, child]) => [
      ...(FORBIDDEN_PUBLIC_KEYS.includes(key) ? [`${path}.${key}`] : []),
      ...findForbiddenKeys(child, `${path}.${key}`),
    ]);
  }
  return [];
}

/** The main navigation landmark; links with the same text also exist in the footer and on the landing page. */
export function mainNav(page: Page): Locator {
  return page.getByRole("navigation", { name: uk.a11y.mainNavigation });
}
