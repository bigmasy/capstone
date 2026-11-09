import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ProfilePut } from "../../api/types";
import {
  bodiesSentTo,
  calls,
  jsonResponse,
  makeProfile,
  noContent,
  routeFetch,
  taxonomy,
} from "../../test/api";
import { setupStore } from "../store";
import { isNoProfile, profileApi } from "./profileApi";

const body: ProfilePut = {
  display_name: "Олена",
  district_code: null,
  intensity: 3,
  is_visible: true,
  latitude: 50.45,
  longitude: 30.52,
  sports: [{ sport: "swimming", skill: "beginner" }],
  capabilities: [],
  functional_data_consent: false,
  contact: null,
};

describe("profileApi", () => {
  const fetchMock = vi.fn<typeof fetch>();

  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    fetchMock.mockReset();
    vi.unstubAllGlobals();
  });

  const loggedInStore = () => setupStore({ auth: { token: "tok" } });

  it("getTaxonomy is requested once and served from the cache afterwards", async () => {
    routeFetch(fetchMock, { "GET /taxonomy": () => jsonResponse(200, taxonomy) });
    const store = loggedInStore();

    const first = await store.dispatch(profileApi.endpoints.getTaxonomy.initiate());
    const second = await store.dispatch(profileApi.endpoints.getTaxonomy.initiate());

    expect(first.data).toEqual(taxonomy);
    expect(second.data).toEqual(taxonomy);
    expect(calls(fetchMock)).toEqual(["GET /taxonomy"]);
  });

  it("getMyProfile reports a missing profile as status 404", async () => {
    routeFetch(fetchMock, { "GET /profiles/me": () => jsonResponse(404, { detail: "none" }) });
    const store = loggedInStore();

    const result = await store.dispatch(profileApi.endpoints.getMyProfile.initiate());

    expect(isNoProfile(result.error)).toBe(true);
    expect(result.data).toBeUndefined();
  });

  it("isNoProfile is false for other failures", () => {
    expect(isNoProfile({ status: 500 })).toBe(false);
    expect(isNoProfile({ status: "FETCH_ERROR" })).toBe(false);
    expect(isNoProfile(undefined)).toBe(false);
  });

  it("saveMyProfile sends a PUT with the body and refreshes the cached profile", async () => {
    const stored = makeProfile();
    let storedNow = false;
    routeFetch(fetchMock, {
      "GET /profiles/me": () =>
        storedNow ? jsonResponse(200, stored) : jsonResponse(404, { detail: "none" }),
      "PUT /profiles/me": () => {
        storedNow = true;
        return jsonResponse(200, stored);
      },
    });
    const store = loggedInStore();
    const subscription = store.dispatch(profileApi.endpoints.getMyProfile.initiate());
    await subscription;
    expect(profileApi.endpoints.getMyProfile.select()(store.getState()).error).toMatchObject({
      status: 404,
    });

    const result = await store.dispatch(profileApi.endpoints.saveMyProfile.initiate(body));

    expect(result).toEqual({ data: stored });
    expect(await bodiesSentTo(fetchMock, "PUT /profiles/me")).toEqual([body]);
    // The tag invalidation makes the active query ask the server again
    await vi.waitFor(() =>
      expect(calls(fetchMock).filter((call) => call === "GET /profiles/me")).toHaveLength(2),
    );
    await vi.waitFor(() =>
      expect(profileApi.endpoints.getMyProfile.select()(store.getState()).data).toEqual(stored),
    );
    subscription.unsubscribe();
  });

  it("saveMyProfile leaves the cache alone when the server rejects the profile", async () => {
    routeFetch(fetchMock, {
      "GET /profiles/me": () => jsonResponse(200, makeProfile()),
      "PUT /profiles/me": () =>
        jsonResponse(422, { detail: [{ type: "missing", loc: ["body", "latitude"], msg: "x" }] }),
    });
    const store = loggedInStore();
    const subscription = store.dispatch(profileApi.endpoints.getMyProfile.initiate());
    await subscription;

    const result = await store.dispatch(profileApi.endpoints.saveMyProfile.initiate(body));

    expect(result.error).toMatchObject({ status: 422 });
    expect(profileApi.endpoints.getMyProfile.select()(store.getState()).data).toEqual(
      makeProfile(),
    );
    subscription.unsubscribe();
  });

  it("deleteAccount sends DELETE /auth/me and treats 204 as success", async () => {
    routeFetch(fetchMock, { "DELETE /auth/me": () => noContent() });
    const store = loggedInStore();

    const result = await store.dispatch(profileApi.endpoints.deleteAccount.initiate());

    expect(result.error).toBeUndefined();
    expect(calls(fetchMock)).toEqual(["DELETE /auth/me"]);
  });

  it("sends the bearer token with every profile request", async () => {
    routeFetch(fetchMock, { "GET /profiles/me": () => jsonResponse(200, makeProfile()) });
    const store = loggedInStore();

    await store.dispatch(profileApi.endpoints.getMyProfile.initiate());

    const request = fetchMock.mock.calls[0]?.[0] as Request;
    expect(request.headers.get("Authorization")).toBe("Bearer tok");
  });
});
