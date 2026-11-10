import { execFileSync } from "node:child_process";
import type { APIRequestContext, BrowserContext, Page } from "@playwright/test";
import { e2ePassword, freshEmail } from "./env";

const API = "/api/v1";
const TOKEN_KEY = "auth.token";

export interface TestAccount {
  email: string;
  password: string;
  token: string;
}

export interface ProfileBody {
  display_name: string;
  intensity: number;
  sports: { sport: string; skill: string }[];
  latitude?: number;
  longitude?: number;
  contact?: string | null;
  district_code?: string;
  is_visible?: boolean;
  functional_data_consent?: boolean;
  capabilities?: {
    category: string;
    level: number;
    equipment?: string | null;
  }[];
}

/** Waits for a rate-limit budget to refill instead of failing; the limits themselves are not under test. */
async function withRateLimitWait(
  call: () => ReturnType<APIRequestContext["post"]>,
) {
  for (let attempt = 0; attempt < 8; attempt += 1) {
    const response = await call();
    if (response.status() !== 429) return response;
    await new Promise((resolve) => setTimeout(resolve, 13_000));
  }
  return call();
}

/** Logs in through the API and returns the bearer token. */
export async function apiLogin(
  request: APIRequestContext,
  email: string,
  password: string,
): Promise<string> {
  const response = await withRateLimitWait(() =>
    request.post(`${API}/auth/login`, { data: { email, password } }),
  );
  if (!response.ok())
    throw new Error(`login failed with status ${response.status()}`);
  const body = (await response.json()) as { access_token: string };
  return body.access_token;
}

/** Container of the API service, where the confirmation command runs (see the README, "Develop and test"). */
function apiContainer(): string {
  const project = process.env.COMPOSE_PROJECT_NAME ?? "adaptive-sport";
  return process.env.E2E_API_CONTAINER ?? `${project}-api-1`;
}

function runInApi(args: string[]): string {
  return execFileSync(
    "docker",
    [
      "exec",
      "-i",
      apiContainer(),
      "python",
      "-m",
      "app.tools.verify_email",
      ...args,
    ],
    {
      encoding: "utf8",
    },
  ).trim();
}

/**
 * Confirms an account's e-mail address the way an administrator would, with the command of the
 * API image. No mail server is involved; the end-to-end tests have no mailbox to read.
 */
export function confirmEmail(email: string): void {
  runInApi([email]);
}

/** Issues a fresh confirmation link for an account, the one the e-mailed message carries. */
export function confirmationLink(email: string): string {
  return runInApi(["--link", email]);
}

/** Issues a fresh password-reset link for an account, the one the e-mailed message carries. */
export function resetLink(email: string): string {
  return runInApi(["--reset-link", email]);
}

/**
 * Registers a throw-away account through the API (setup for tests that are not about
 * registration). The address is confirmed, because an unconfirmed account cannot invite, accept
 * or be found; pass `confirmed: false` for the tests that are about exactly that.
 */
export async function apiRegister(
  request: APIRequestContext,
  label = "user",
  { confirmed = true }: { confirmed?: boolean } = {},
): Promise<TestAccount> {
  const email = freshEmail(label);
  const response = await withRateLimitWait(() =>
    request.post(`${API}/auth/register`, {
      data: { email, password: e2ePassword },
    }),
  );
  if (!response.ok())
    throw new Error(`registration failed with status ${response.status()}`);
  if (confirmed) confirmEmail(email);
  const token = await apiLogin(request, email, e2ePassword);
  return { email, password: e2ePassword, token };
}

/** Creates or replaces the profile of an account through the API. */
export async function apiPutProfile(
  request: APIRequestContext,
  token: string,
  profile: ProfileBody,
): Promise<void> {
  const response = await withRateLimitWait(() =>
    request.put(`${API}/profiles/me`, {
      data: profile,
      headers: { Authorization: `Bearer ${token}` },
    }),
  );
  if (!response.ok())
    throw new Error(`profile save failed with status ${response.status()}`);
}

/** Deletes the account of a token; used to clean up throw-away users. Failures are ignored. */
export async function apiDeleteAccount(
  request: APIRequestContext,
  token: string,
): Promise<void> {
  await request.delete(`${API}/auth/me`, {
    headers: { Authorization: `Bearer ${token}` },
  });
}

/**
 * Makes every page of the context start with the given session, the way a reload keeps it: the
 * client mirrors its token to sessionStorage, which is per tab, so it is set before the scripts run.
 */
export async function startSession(
  context: BrowserContext,
  token: string,
): Promise<void> {
  await context.addInitScript(
    ([key, value]) => {
      window.sessionStorage.setItem(key as string, value as string);
    },
    [TOKEN_KEY, token],
  );
}

/** Opens a path with the given session already in place. */
export async function openAs(
  page: Page,
  token: string,
  path: string,
): Promise<void> {
  await startSession(page.context(), token);
  await page.goto(path);
}

/** A profile near the centre of Kyiv with one sport, as the demo population is anchored there. */
export function kyivProfile(
  name: string,
  extra: Partial<ProfileBody> = {},
): ProfileBody {
  return {
    display_name: name,
    intensity: 3,
    sports: [{ sport: "swimming", skill: "beginner" }],
    latitude: 50.45,
    longitude: 30.52,
    ...extra,
  };
}
