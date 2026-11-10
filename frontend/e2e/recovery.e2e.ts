import { expect, test } from "@playwright/test";
import { uk } from "../src/i18n/uk";
import {
  apiDeleteAccount,
  apiLogin,
  apiRegister,
  resetLink,
} from "./support/api";
import { e2ePassword } from "./support/env";
import { passwordLabel } from "./support/ui";

/**
 * Password recovery with a real browser and the real API. The test has no mailbox: the link
 * the message carries is issued by the API image, as for the confirmation link.
 */
const NEW_PASSWORD = `${e2ePassword}-renewed`;

test("a forgotten password is replaced through the e-mailed link", async ({
  page,
  request,
}) => {
  const account = await apiRegister(request, "recovery");
  try {
    // Asking for the link: the page answers the same way for any address
    await page.goto("/login");
    await page.getByRole("link", { name: uk.passwordReset.forgotLink }).click();
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(
      uk.passwordReset.forgot.title,
    );
    await page.getByLabel(uk.auth.email).fill(account.email);
    await page
      .getByRole("button", { name: uk.passwordReset.forgot.submit })
      .click();
    await expect(page.getByText(uk.passwordReset.forgot.sent)).toBeVisible();

    // A session that existed before the change must not survive it (tokens carry whole seconds)
    await page.waitForTimeout(1200);

    // Following the link: the token leaves the address bar at once
    await page.goto(resetLink(account.email));
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(
      uk.passwordReset.reset.title,
    );
    expect(page.url()).not.toContain("token");
    await page
      .getByLabel(new RegExp(`^${uk.passwordReset.reset.newPassword}`))
      .fill(NEW_PASSWORD);
    await page
      .getByLabel(new RegExp(uk.passwordReset.reset.confirmPassword))
      .fill(NEW_PASSWORD);
    await page
      .getByRole("button", { name: uk.passwordReset.reset.submit })
      .click();
    await expect(page.getByText(uk.passwordReset.reset.saved)).toBeVisible();

    // The old password and the old session are dead, the new password works
    const stale = await request.get("/api/v1/auth/me", {
      headers: { Authorization: `Bearer ${account.token}` },
    });
    expect(stale.status()).toBe(401);
    const old = await request.post("/api/v1/auth/login", {
      data: { email: account.email, password: account.password },
    });
    expect(old.status()).toBe(401);

    await page
      .getByRole("link", { name: uk.passwordReset.reset.toLogin })
      .click();
    await page.getByLabel(uk.auth.email).fill(account.email);
    await page.getByLabel(passwordLabel).fill(NEW_PASSWORD);
    await page.getByRole("button", { name: uk.auth.submitLogin }).click();
    // After a whole suite the proxy may still hold this address in its sign-in budget (5 a
    // minute): wait for it to refill and press the button again, a few times at most
    const limited = page.getByText(uk.auth.tooManyAttempts);
    for (let attempt = 0; attempt < 6; attempt += 1) {
      const signedIn = await page
        .waitForURL((url) => !url.pathname.endsWith("/login"), { timeout: 4000 })
        .then(() => true)
        .catch(() => false);
      if (signedIn || !(await limited.isVisible())) break;
      await page.waitForTimeout(13_000);
      await page.getByRole("button", { name: uk.auth.submitLogin }).click();
    }
    await expect(page).not.toHaveURL(/\/login$/);

    // The link works once
    await page.goto(
      resetLink(account.email).replace(/token=.*/, "token=" + "x".repeat(43)),
    );
    await page
      .getByLabel(new RegExp(`^${uk.passwordReset.reset.newPassword}`))
      .fill(NEW_PASSWORD);
    await page
      .getByLabel(new RegExp(uk.passwordReset.reset.confirmPassword))
      .fill(NEW_PASSWORD);
    await page
      .getByRole("button", { name: uk.passwordReset.reset.submit })
      .click();
    await expect(
      page.getByText(uk.passwordReset.reset.invalidLink),
    ).toBeVisible();
  } finally {
    const token = await apiLogin(request, account.email, NEW_PASSWORD).catch(
      () => null,
    );
    if (token) await apiDeleteAccount(request, token);
  }
});
