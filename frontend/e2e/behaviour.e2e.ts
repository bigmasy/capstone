import { uk } from "../src/i18n/uk";
import { startSession } from "./support/api";
import { expect, test } from "./support/fixtures";

test("logged-out visitors see the landing page with the way in", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(uk.pages.home.title);
  await expect(page.getByRole("link", { name: uk.landing.hero.registerCta }).first()).toBeVisible();
  // Nothing of a member area is rendered
  await expect(page.getByRole("link", { name: uk.nav.invitations })).toHaveCount(0);
});

test("a rejected token ends the session with a notice on the login page", async ({ page }) => {
  await startSession(page.context(), "not.a.valid.token");
  await page.goto("/matches");
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByRole("status").filter({ hasText: uk.auth.sessionEnded })).toBeVisible();
  await expect(page.getByRole("heading", { level: 1 })).toBeFocused();
  // The member navigation is gone with the session
  await expect(page.getByRole("button", { name: uk.nav.logout })).toHaveCount(0);
});

test("inviting without a contact shows the notice, which links to the profile", async ({ page, world }) => {
  await startSession(page.context(), world.noContact.token);
  await page.goto("/matches");
  const first = page.getByRole("article").first();
  await first.getByRole("button", { name: uk.feed.invite.trigger }).click();
  await first.getByRole("button", { name: uk.feed.invite.confirm }).click();
  const notice = page.getByRole("alert").filter({ hasText: uk.contactRequired.message });
  await expect(notice).toBeVisible();
  await expect(notice).toBeFocused();
  await notice.getByRole("link", { name: uk.contactRequired.link }).click();
  await expect(page).toHaveURL(/\/profile$/);
  await expect(page.getByText(uk.profile.contact.missing)).toBeVisible();
});

test("logging out returns to the landing page", async ({ page, world }) => {
  await startSession(page.context(), world.rich.token);
  await page.goto("/matches");
  await page.getByRole("navigation", { name: uk.a11y.mainNavigation }).getByRole("button", { name: uk.nav.logout }).click();
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(uk.pages.home.title);
  await expect(page.getByRole("heading", { level: 1 })).toBeFocused();
});
