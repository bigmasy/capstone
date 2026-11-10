import { request as playwrightRequest, type APIRequestContext } from "@playwright/test";
import { apiLogin, apiPutProfile, apiRegister, kyivProfile, type TestAccount } from "./api";
import { demoDisplayName, demoEmail, demoPassword } from "./env";

const API = "/api/v1";

export interface DemoSession {
  index: number;
  name: string;
  token: string;
}

/** Accounts and data that the browser tests share; created once per worker (see fixtures.ts). */
export interface World {
  /** Full profile: two sports, consent, two capabilities, a contact; owns invitations of every kind. */
  rich: TestAccount;
  /** Account without a profile (onboarding). */
  bare: TestAccount;
  /** Account with a profile and no contact. */
  noContact: TestAccount;
  /** Account with a profile far from every demo account (empty feed). */
  farAway: TestAccount;
  /** Account with a profile whose e-mail address is not confirmed (banner, notices instead of buttons). */
  unconfirmed: TestAccount;
  /** Demo accounts used for invitations; absent without E2E_DEMO_PASSWORD. */
  demo?: { outgoingTo: DemoSession; incomingPending: DemoSession; accepted: DemoSession };
}

function bearer(token: string): { Authorization: string } {
  return { Authorization: `Bearer ${token}` };
}

async function getJson<T>(request: APIRequestContext, path: string, token: string): Promise<T> {
  const response = await request.get(`${API}${path}`, { headers: bearer(token) });
  if (!response.ok()) throw new Error(`GET ${path} answered ${response.status()}`);
  return (await response.json()) as T;
}

interface StoredProfile {
  id: string;
  display_name: string;
  intensity: number;
  district_code: string | null;
  is_visible: boolean;
  sports: { sport: string; skill: string }[];
  capabilities: { category: string; level: number; equipment?: string | null }[];
  functional_data_consent: boolean;
  contact: string | null;
}

/** Gives a demo account a contact (idempotent); the stored area is kept because no point is sent. */
export async function ensureDemoContact(request: APIRequestContext, session: DemoSession): Promise<string> {
  const stored = await getJson<StoredProfile>(request, "/profiles/me", session.token);
  if (!stored.contact) {
    await apiPutProfile(request, session.token, {
      display_name: stored.display_name,
      intensity: stored.intensity,
      sports: stored.sports,
      capabilities: stored.capabilities,
      functional_data_consent: stored.functional_data_consent,
      is_visible: stored.is_visible,
      contact: `@${session.name.replaceAll(" ", "_").toLowerCase()}`,
      ...(stored.district_code ? { district_code: stored.district_code } : {}),
    });
  }
  return stored.id;
}

export async function demoSession(request: APIRequestContext, index: number): Promise<DemoSession> {
  const token = await apiLogin(request, demoEmail(index), demoPassword ?? "");
  return { index, name: demoDisplayName(index), token };
}

async function invite(
  request: APIRequestContext,
  token: string,
  recipientProfileId: string,
): Promise<string> {
  const response = await request.post(`${API}/invitations`, {
    headers: bearer(token),
    data: { recipient_profile_id: recipientProfileId },
  });
  if (!response.ok()) throw new Error(`invitation failed with status ${response.status()}`);
  return ((await response.json()) as { id: string }).id;
}

/** Creates the shared accounts and the invitations of every kind; returns what the tests need. */
export async function buildWorld(baseURL: string): Promise<World> {
  const request = await playwrightRequest.newContext({ baseURL, ignoreHTTPSErrors: true });
  try {
    const rich = await apiRegister(request, "rich");
    await apiPutProfile(
      request,
      rich.token,
      kyivProfile("E2E Rich", {
        sports: [
          { sport: "swimming", skill: "intermediate" },
          { sport: "cycling", skill: "beginner" },
        ],
        contact: "@e2e_rich",
        functional_data_consent: true,
        capabilities: [
          { category: "mobility_lower", level: 2, equipment: "wheelchair_active" },
          { category: "endurance", level: 3 },
        ],
      }),
    );

    const bare = await apiRegister(request, "bare");

    const noContact = await apiRegister(request, "nocontact");
    await apiPutProfile(request, noContact.token, kyivProfile("E2E No contact"));

    const farAway = await apiRegister(request, "far");
    // Uzhhorod is far outside the 100 km search radius of every demo account
    await apiPutProfile(request, farAway.token, {
      ...kyivProfile("E2E Far away"),
      latitude: 48.62,
      longitude: 22.29,
      contact: "@e2e_far",
    });

    const unconfirmed = await apiRegister(request, "unconfirmed", { confirmed: false });
    await apiPutProfile(request, unconfirmed.token, {
      ...kyivProfile("E2E Unconfirmed"),
      contact: "@e2e_unconfirmed",
    });

    let demo: World["demo"];
    if (demoPassword) {
      const [outgoingTo, incomingPending, accepted] = await Promise.all([
        demoSession(request, 2),
        demoSession(request, 3),
        demoSession(request, 4),
      ]);
      const ids = {
        outgoingTo: await ensureDemoContact(request, outgoingTo),
        incomingPending: await ensureDemoContact(request, incomingPending),
        accepted: await ensureDemoContact(request, accepted),
      };
      const richProfile = await getJson<StoredProfile>(request, "/profiles/me", rich.token);
      await invite(request, rich.token, ids.outgoingTo);
      await invite(request, incomingPending.token, richProfile.id);
      const acceptedId = await invite(request, accepted.token, richProfile.id);
      const response = await request.post(`${API}/invitations/${acceptedId}/accept`, {
        headers: bearer(rich.token),
      });
      if (!response.ok()) throw new Error(`accept failed with status ${response.status()}`);
      demo = { outgoingTo, incomingPending, accepted };
    }

    const world: World = { rich, bare, noContact, farAway, unconfirmed };
    if (demo) world.demo = demo;
    return world;
  } finally {
    await request.dispose();
  }
}

/** Deletes the shared accounts; failures are ignored, the data is throw-away anyway. */
export async function disposeWorld(baseURL: string, world: World): Promise<void> {
  const request = await playwrightRequest.newContext({ baseURL, ignoreHTTPSErrors: true });
  try {
    for (const account of [
      world.rich,
      world.bare,
      world.noContact,
      world.farAway,
      world.unconfirmed,
    ]) {
      await request.delete(`${API}/auth/me`, { headers: bearer(account.token) });
    }
  } finally {
    await request.dispose();
  }
}
