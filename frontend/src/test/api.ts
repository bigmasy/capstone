import { expect, type Mock } from "vitest";
import type {
  Account,
  NewsFeed,
  InvitationIncoming,
  InvitationOut,
  InvitationPartner,
  MatchFeed,
  MatchItem,
  ProfileOwner,
  Taxonomy,
} from "../api/types";

const API = "http://localhost/api/v1";

type FetchMock = Mock<typeof fetch>;

export function jsonResponse(status: number, body: unknown = {}): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

/** An empty 204 answer, as the DELETE routes give it. */
export function noContent(): Response {
  return new Response(null, { status: 204 });
}

export type Handler = (request: Request) => Response | Promise<Response>;

/** A response factory or a handler per route key such as `GET /profiles/me`. */
export type Routes = Record<string, Handler>;

/**
 * Makes a mocked fetch answer by route. A request without a route fails the test, so an
 * unexpected call cannot go unnoticed. Routes can be replaced between steps of a test.
 */
export function routeFetch(fetchMock: FetchMock, routes: Routes) {
  fetchMock.mockImplementation((input) => {
    const request = input as Request;
    const key = `${request.method} ${request.url.replace(API, "")}`;
    // A route written without a query string answers every query of that path
    const handler = routes[key] ?? routes[key.split("?")[0] as string];
    expect(handler, `no mocked route for ${key}`).toBeDefined();
    return Promise.resolve((handler as Handler)(request));
  });
}

/** Requests made so far, as `METHOD /path` strings. */
export function calls(fetchMock: FetchMock): string[] {
  return fetchMock.mock.calls.map(([input]) => {
    const request = input as Request;
    return `${request.method} ${request.url.replace(API, "")}`;
  });
}

/** JSON bodies sent to a route, in order. */
export async function bodiesSentTo(
  fetchMock: FetchMock,
  key: string,
): Promise<unknown[]> {
  const matching = fetchMock.mock.calls
    .map(([input]) => input as Request)
    .filter((request) => `${request.method} ${request.url.replace(API, "")}` === key);
  return Promise.all(matching.map((request) => request.clone().json() as Promise<unknown>));
}

/** The taxonomy as the backend serves it (version 1.0.0). */
export const taxonomy: Taxonomy = {
  version: "1.0.0",
  sports: [
    "swimming",
    "archery",
    "table_tennis",
    "sitting_volleyball",
    "wheelchair_basketball",
    "cycling",
    "handcycling",
    "rowing",
    "athletics",
    "gym_fitness",
    "powerlifting",
    "yoga_stretching",
    "badminton",
    "nordic_walking",
  ],
  categories: [
    "mobility_lower",
    "mobility_upper",
    "balance_posture",
    "endurance",
    "dexterity",
    "vision",
    "hearing",
  ],
  equipment: [
    { code: "wheelchair_active", categories: ["mobility_lower"] },
    { code: "handcycle", categories: ["mobility_lower"] },
    { code: "crutches_or_cane", categories: ["mobility_lower", "balance_posture"] },
    { code: "prosthesis_lower_limb", categories: ["mobility_lower"] },
    { code: "running_blade", categories: ["mobility_lower"] },
    { code: "prosthesis_upper_limb", categories: ["mobility_upper", "dexterity"] },
    { code: "guide_support", categories: ["vision"] },
    { code: "hearing_aid", categories: ["hearing"] },
  ],
  districts: [
    "kyiv_holosiivskyi",
    "kyiv_darnytskyi",
    "kyiv_desnianskyi",
    "kyiv_dniprovskyi",
    "kyiv_obolonskyi",
    "kyiv_pecherskyi",
    "kyiv_podilskyi",
    "kyiv_sviatoshynskyi",
    "kyiv_solomianskyi",
    "kyiv_shevchenkivskyi",
  ],
  skills: ["beginner", "intermediate", "advanced"],
  capability_levels: [0, 1, 2, 3, 4],
  intensities: [1, 2, 3, 4, 5],
};

/** The digest of the landing page: one item in the first two columns and none in the last. */
export function makeNews(overrides: Partial<NewsFeed> = {}): NewsFeed {
  return {
    columns: [
      {
        id: "world",
        items: [
          {
            title: "Meet in Brescia",
            url: "https://www.paralympic.org/n/1",
            source: "Міжнародний паралімпійський комітет",
            published_at: "2026-11-06T09:00:00Z",
          },
        ],
      },
      {
        id: "ukraine",
        items: [
          {
            title: "Паралімпійці отримають премії",
            url: "https://suspilne.media/2",
            source: "Суспільне",
            published_at: "2026-11-09T07:00:00Z",
          },
        ],
      },
      { id: "veterans", items: [] },
    ],
    ...overrides,
  };
}

/** The caller's own account as `GET /auth/me` answers; confirmed unless stated otherwise. */
export function makeAccount(overrides: Partial<Account> = {}): Account {
  return {
    id: "6f1c1c0e-0000-4000-8000-0000000000ff",
    email: "olena@example.org",
    created_at: "2026-11-01T10:00:00Z",
    email_verified: true,
    ...overrides,
  };
}

/** A stored profile as the owner receives it; the location is not part of it. */
export function makeProfile(overrides: Partial<ProfileOwner> = {}): ProfileOwner {
  return {
    id: "6f1c1c0e-0000-4000-8000-000000000001",
    display_name: "Олена",
    district_code: "kyiv_podilskyi",
    intensity: 3,
    sports: [{ sport: "swimming", skill: "intermediate" }],
    is_visible: true,
    functional_data_consent: false,
    functional_consent_at: null,
    capabilities: [],
    contact: null,
    created_at: "2026-11-01T10:00:00Z",
    updated_at: "2026-11-01T10:00:00Z",
    ...overrides,
  };
}

/** A baseline feed candidate: public fields, a distance band and the points per criterion. */
export function makeMatch(overrides: Partial<MatchItem> = {}): MatchItem {
  return {
    id: "6f1c1c0e-0000-4000-8000-0000000000a1",
    display_name: "Андрій",
    district_code: "kyiv_obolonskyi",
    intensity: 4,
    sports: [
      { sport: "swimming", skill: "advanced" },
      { sport: "cycling", skill: "beginner" },
    ],
    distance_band: "5–10 km",
    breakdown: { sport: 15, distance: 20, intensity: 11.2, functional: "high", total: 71.2 },
    rank_source: "baseline",
    rank_influence: null,
    ...overrides,
  };
}

/** One page of the feed; `total` defaults to the number of items. */
export function makeFeed(
  items: MatchItem[],
  overrides: Partial<Omit<MatchFeed, "items">> = {},
): MatchFeed {
  return {
    items,
    skip: 0,
    limit: 10,
    total: items.length,
    max_points: { sport: 30, distance: 30, intensity: 15 },
    ...overrides,
  };
}

/** The other party of an invitation; the contact is null until the invitation is accepted. */
export function makePartner(overrides: Partial<InvitationPartner> = {}): InvitationPartner {
  return {
    id: "6f1c1c0e-0000-4000-8000-0000000000b1",
    display_name: "Марія",
    district_code: "kyiv_pecherskyi",
    intensity: 2,
    sports: [{ sport: "yoga_stretching", skill: "intermediate" }],
    contact: null,
    ...overrides,
  };
}

/**
 * An invitation as the caller sees it. The cast keeps the builder independent of fields
 * that the contract may drop; only the fields the client reads are set here.
 */
export function makeInvitation(
  direction: "incoming" | "outgoing",
  overrides: Partial<Omit<InvitationIncoming, "direction" | "sender">> & {
    partner?: InvitationPartner | null;
  } = {},
): InvitationOut {
  const { partner = makePartner(), ...fields } = overrides;
  const common = {
    id: "6f1c1c0e-0000-4000-8000-0000000000c1",
    status: "pending",
    created_at: "2026-11-01T10:00:00Z",
    expires_at: "2026-11-15T10:00:00Z",
    responded_at: null,
    ...fields,
  };
  return direction === "incoming"
    ? ({ ...common, direction, sender: partner } as InvitationOut)
    : ({ ...common, direction, recipient: partner } as InvitationOut);
}
