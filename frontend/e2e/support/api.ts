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
  capabilities?: { category: string; level: number; equipment?: string | null }[];
}

/** Waits for a rate-limit budget to refill instead of failing; the limits themselves are not under test. */
async function withRateLimitWait(call: () => ReturnType<APIRequestContext["post"]>) {
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
  if (!response.ok()) throw new Error(`login failed with status ${response.status()}`);
  const body = (await response.json()) as { access_token: string };
  return body.access_token;
}

/** Registers a throw-away account through the API (setup for tests that are not about registration). */
export async function apiRegister(request: APIRequestContext, label = "user"): Promise<TestAccount> {
  const email = freshEmail(label);
  const response = await withRateLimitWait(() =>
    request.post(`${API}/auth/register`, { data: { email, password: e2ePassword } }),
  );
  if (!response.ok()) throw new Error(`registration failed with status ${response.status()}`);
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
  if (!response.ok()) throw new Error(`profile save failed with status ${response.status()}`);
}

/** Deletes the account of a token; used to clean up throw-away users. Failures are ignored. */
export async function apiDeleteAccount(request: APIRequestContext, token: string): Promise<void> {
  await request.delete(`${API}/auth/me`, { headers: { Authorization: `Bearer ${token}` } });
}

/**
 * Makes every page of the context start with the given session, the way a reload keeps it: the
 * client mirrors its token to sessionStorage, which is per tab, so it is set before the scripts run.
 */
export async function startSession(context: BrowserContext, token: string): Promise<void> {
  await context.addInitScript(
    ([key, value]) => {
      window.sessionStorage.setItem(key as string, value as string);
    },
    [TOKEN_KEY, token],
  );
}

/** Opens a path with the given session already in place. */
export async function openAs(page: Page, token: string, path: string): Promise<void> {
  await startSession(page.context(), token);
  await page.goto(path);
}

/** A profile near the centre of Kyiv with one sport, as the demo population is anchored there. */
export function kyivProfile(name: string, extra: Partial<ProfileBody> = {}): ProfileBody {
  return {
    display_name: name,
    intensity: 3,
    sports: [{ sport: "swimming", skill: "beginner" }],
    latitude: 50.45,
    longitude: 30.52,
    ...extra,
  };
}
