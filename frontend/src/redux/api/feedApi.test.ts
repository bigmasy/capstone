import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { calls, jsonResponse, makeFeed, makeMatch, makeProfile, routeFetch } from "../../test/api";
import { setupStore } from "../store";
import { feedApi } from "./feedApi";
import { profileApi } from "./profileApi";

describe("feedApi", () => {
  const fetchMock = vi.fn<typeof fetch>();

  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    fetchMock.mockReset();
    vi.unstubAllGlobals();
  });

  it("requests the first page with skip 0 and limit 10 and no filters", async () => {
    routeFetch(fetchMock, { "GET /matches": () => jsonResponse(200, makeFeed([makeMatch()])) });
    const store = setupStore({ auth: { token: "tok" } });

    const result = await store.dispatch(feedApi.endpoints.getMatches.initiate({ page: 0 }));

    expect(result.data?.items).toHaveLength(1);
    expect(calls(fetchMock)).toEqual(["GET /matches?skip=0&limit=10"]);
  });

  it("turns the page number into skip and sends the filters", async () => {
    routeFetch(fetchMock, { "GET /matches": () => jsonResponse(200, makeFeed([])) });
    const store = setupStore({ auth: { token: "tok" } });

    await store.dispatch(
      feedApi.endpoints.getMatches.initiate({ page: 2, radius: 10, sport: "swimming" }),
    );

    expect(calls(fetchMock)).toEqual([
      "GET /matches?skip=20&limit=10&radius_km=10&sport=swimming",
    ]);
  });

  it("reports a caller without a profile as status 404", async () => {
    routeFetch(fetchMock, { "GET /matches": () => jsonResponse(404, { detail: "none" }) });
    const store = setupStore({ auth: { token: "tok" } });

    const result = await store.dispatch(feedApi.endpoints.getMatches.initiate({ page: 0 }));

    expect(result.error).toMatchObject({ status: 404 });
  });

  it("refetches the feed after the caller's profile is saved", async () => {
    routeFetch(fetchMock, {
      "GET /matches": () => jsonResponse(200, makeFeed([makeMatch()])),
      "PUT /profiles/me": () => jsonResponse(200, makeProfile()),
    });
    const store = setupStore({ auth: { token: "tok" } });
    const subscription = store.dispatch(feedApi.endpoints.getMatches.initiate({ page: 0 }));
    await subscription;

    await store.dispatch(
      profileApi.endpoints.saveMyProfile.initiate({
        display_name: "Олена",
        latitude: 50.45,
        longitude: 30.52,
        intensity: 3,
        is_visible: true,
        sports: [{ sport: "swimming", skill: "beginner" }],
        capabilities: [],
        functional_data_consent: false,
        contact: null,
      }),
    );

    await vi.waitFor(() =>
      expect(calls(fetchMock).filter((call) => call.startsWith("GET /matches"))).toHaveLength(2),
    );
    subscription.unsubscribe();
  });
});
