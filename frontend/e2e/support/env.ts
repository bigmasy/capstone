import { randomBytes } from "node:crypto";

/** Short random token for unique e-mails and display names of one run. */
export const runId = randomBytes(4).toString("hex");

/** A fresh, unique e-mail on the reserved example.invalid domain. */
export function freshEmail(label = "user"): string {
  return `e2e-${label}-${randomBytes(4).toString("hex")}@example.invalid`;
}

/**
 * Password of the accounts created by the tests: the value of E2E_PASSWORD, or a random strong
 * one generated once per run. It is never printed.
 */
export const e2ePassword: string = process.env.E2E_PASSWORD ?? `Aa1-${randomBytes(12).toString("hex")}`;

/** Shared password of the seeded demo accounts; the tests that need them skip without it. */
export const demoPassword: string | undefined = process.env.E2E_DEMO_PASSWORD;

/** E-mail of the seeded demo account with the given one-based number. */
export function demoEmail(index: number): string {
  return `demo-${String(index).padStart(4, "0")}@example.invalid`;
}

/** Name that `app.tools.seed` gives to the demo account with the given one-based number. */
export function demoDisplayName(index: number): string {
  return `Demo participant ${String(index).padStart(4, "0")}`;
}

/** The demo account number a display name belongs to, or null for any other name. */
export function demoIndexOf(displayName: string): number | null {
  const match = /^Demo participant (\d{4})$/.exec(displayName.trim());
  return match ? Number(match[1]) : null;
}
