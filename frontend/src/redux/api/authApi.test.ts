import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { setupStore } from "../store";
import { authApi } from "./authApi";

const credentials = { email: "a@example.com", password: "very-secret-password" };
const TOKEN = "tok-9f3c1d";

function jsonResponse(status: number, body: unknown = {}): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const tokenBody = { access_token: TOKEN, token_type: "bearer" };

describe("authApi", () => {
  const fetchMock = vi.fn<typeof fetch>();

  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    fetchMock.mockReset();
    vi.unstubAllGlobals();
  });

  const urls = () => fetchMock.mock.calls.map(([request]) => (request as Request).url);

  it("login moves the token to the auth slice and keeps it out of the API cache", async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, tokenBody));
    const store = setupStore();

    const result = await store.dispatch(authApi.endpoints.login.initiate(credentials));

    expect(result).toEqual({ data: { loggedIn: true } });
    expect(store.getState().auth.token).toBe(TOKEN);
    const cached = JSON.stringify(store.getState().api);
    expect(cached).not.toContain(TOKEN);
    expect(cached).not.toContain(credentials.password);
  });

  it("login reports the error and stores nothing on a rejected login", async () => {
    fetchMock.mockResolvedValue(jsonResponse(401, { detail: "bad" }));
    const store = setupStore();

    const result = await store.dispatch(authApi.endpoints.login.initiate(credentials));

    expect(result.error).toMatchObject({ status: 401 });
    expect(store.getState().auth.token).toBeNull();
  });

  it("login treats a body without an access token as a parsing error", async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, { token_type: "bearer" }));
    const store = setupStore();

    const result = await store.dispatch(authApi.endpoints.login.initiate(credentials));

    expect(result.error).toMatchObject({ status: "PARSING_ERROR" });
    expect(store.getState().auth.token).toBeNull();
  });

  it("register creates the account and then logs in without leaking secrets into the cache", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(201, {}));
    fetchMock.mockResolvedValueOnce(jsonResponse(200, tokenBody));
    const store = setupStore();

    const result = await store.dispatch(authApi.endpoints.register.initiate(credentials));

    expect(result).toEqual({ data: { loggedIn: true } });
    expect(urls()).toEqual(["http://localhost/api/v1/auth/register", "http://localhost/api/v1/auth/login"]);
    expect(store.getState().auth.token).toBe(TOKEN);
    const cached = JSON.stringify(store.getState().api);
    expect(cached).not.toContain(TOKEN);
    expect(cached).not.toContain(credentials.password);
  });

  it("register does not log in when the account cannot be created", async () => {
    fetchMock.mockResolvedValue(jsonResponse(409, { detail: "exists" }));
    const store = setupStore();

    const result = await store.dispatch(authApi.endpoints.register.initiate(credentials));

    expect(result.error).toMatchObject({ status: 409 });
    expect(urls()).toHaveLength(1);
    expect(store.getState().auth.token).toBeNull();
  });

  it("register reports loggedIn false when the account exists but the login step failed", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(201, {}));
    fetchMock.mockResolvedValueOnce(jsonResponse(500));
    const store = setupStore();

    const result = await store.dispatch(authApi.endpoints.register.initiate(credentials));

    expect(result).toEqual({ data: { loggedIn: false } });
    expect(store.getState().auth.token).toBeNull();
  });

  it("me requests /auth/me with the stored token", async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, {}));
    const store = setupStore({ auth: { token: "abc" } });

    await store.dispatch(authApi.endpoints.me.initiate());

    const request = fetchMock.mock.calls[0]?.[0] as Request;
    expect(request.url).toBe("http://localhost/api/v1/auth/me");
    expect(request.headers.get("Authorization")).toBe("Bearer abc");
  });
});
