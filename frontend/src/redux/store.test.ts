import { afterEach, describe, expect, it } from "vitest";
import { logout, sessionExpired, tokenReceived } from "./auth/slice";
import { devToolsEnabled, setupStore } from "./store";

describe("setupStore token persistence", () => {
  afterEach(() => {
    window.localStorage.clear();
  });

  it("restores the token from sessionStorage", () => {
    window.sessionStorage.setItem("auth.token", "stored");

    const store = setupStore();

    expect(store.getState().auth.token).toBe("stored");
  });

  it("mirrors the token to sessionStorage and never to localStorage", () => {
    const store = setupStore();

    store.dispatch(tokenReceived("secret"));

    expect(window.sessionStorage.getItem("auth.token")).toBe("secret");
    expect(window.localStorage.length).toBe(0);
  });

  it("enables the Redux DevTools only in development builds", () => {
    expect(typeof devToolsEnabled).toBe("boolean");
    expect(devToolsEnabled).toBe(import.meta.env.DEV);
  });

  it("removes the stored token when the server ends the session", () => {
    const store = setupStore({ auth: { token: "secret" } });
    store.dispatch(tokenReceived("secret-2"));

    store.dispatch(sessionExpired());

    expect(window.sessionStorage.getItem("auth.token")).toBeNull();
  });

  it("removes the stored token on logout", () => {
    const store = setupStore({ auth: { token: "secret" } });
    store.dispatch(tokenReceived("secret-2"));

    store.dispatch(logout());

    expect(window.sessionStorage.getItem("auth.token")).toBeNull();
  });
});
