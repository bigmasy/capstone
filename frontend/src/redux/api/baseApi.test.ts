import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { logout, tokenReceived } from "../auth/slice";
import { setupStore } from "../store";
import { baseApi } from "./baseApi";

const probeApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    probe: build.query<{ ok: boolean }, void>({ query: () => "/probe" }),
  }),
});

function jsonResponse(status: number, body: unknown = {}): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("baseApi base query", () => {
  const fetchMock = vi.fn<typeof fetch>();

  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    fetchMock.mockReset();
    vi.unstubAllGlobals();
  });

  it("sends the Bearer token from the state", async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, { ok: true }));
    const store = setupStore({ auth: { token: "abc" } });

    await store.dispatch(probeApi.endpoints.probe.initiate());

    const request = fetchMock.mock.calls[0]?.[0] as Request;
    expect(request.headers.get("Authorization")).toBe("Bearer abc");
    expect(request.url).toBe("http://localhost/api/v1/probe");
  });

  it("omits the Authorization header while logged out", async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, { ok: true }));
    const store = setupStore();

    await store.dispatch(probeApi.endpoints.probe.initiate());

    const request = fetchMock.mock.calls[0]?.[0] as Request;
    expect(request.headers.has("Authorization")).toBe(false);
  });

  it("logs out and clears the stored token on 401 when a token was sent", async () => {
    fetchMock.mockResolvedValue(jsonResponse(401, { detail: "expired" }));
    const store = setupStore({ auth: { token: "expired-token" } });
    window.sessionStorage.setItem("auth.token", "expired-token");

    await store.dispatch(probeApi.endpoints.probe.initiate());

    expect(store.getState().auth.token).toBeNull();
    expect(window.sessionStorage.getItem("auth.token")).toBeNull();
  });

  it("drops cached API data on logout", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(200, { ok: true }));
    const store = setupStore({ auth: { token: "abc" } });
    await store.dispatch(probeApi.endpoints.probe.initiate());
    expect(Object.keys(store.getState().api.queries)).toHaveLength(1);

    fetchMock.mockResolvedValueOnce(jsonResponse(401));
    await store.dispatch(probeApi.endpoints.probe.initiate(undefined, { forceRefetch: true }));

    expect(Object.keys(store.getState().api.queries)).toHaveLength(0);
  });

  it("marks the session as ended by the server on 401", async () => {
    fetchMock.mockResolvedValue(jsonResponse(401));
    const store = setupStore({ auth: { token: "expired-token" } });

    await store.dispatch(probeApi.endpoints.probe.initiate());

    expect(store.getState().auth.endedBy).toBe("expired");
  });

  it("ignores a stale 401 that answers a request sent with a previous token", async () => {
    let answer: (response: Response) => void = () => undefined;
    fetchMock.mockReturnValue(new Promise<Response>((resolve) => (answer = resolve)));
    const store = setupStore({ auth: { token: "old" } });

    const pending = store.dispatch(probeApi.endpoints.probe.initiate());
    // wait until the request has been sent with the old token
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    store.dispatch(logout());
    store.dispatch(tokenReceived("new"));
    answer(jsonResponse(401));
    await pending;

    expect(store.getState().auth.token).toBe("new");
    expect(store.getState().auth.endedBy).toBeUndefined();
  });

  it("keeps the session for 401 answers to requests without a token", async () => {
    fetchMock.mockResolvedValue(jsonResponse(401));
    const store = setupStore();

    const result = await store.dispatch(probeApi.endpoints.probe.initiate());

    expect(result.isError).toBe(true);
    expect(store.getState().auth.token).toBeNull();
  });

  it("keeps the session for other errors", async () => {
    fetchMock.mockResolvedValue(jsonResponse(500));
    const store = setupStore({ auth: { token: "abc" } });

    await store.dispatch(probeApi.endpoints.probe.initiate());

    expect(store.getState().auth.token).toBe("abc");
  });
});
