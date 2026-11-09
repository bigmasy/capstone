import { describe, expect, it } from "vitest";
import { selectIsLoggedIn, selectSessionEndedBy, selectToken } from "./selectors";
import {
  accountDeleted,
  authReducer,
  logout,
  sessionEndAcknowledged,
  sessionExpired,
  tokenReceived,
  type AuthState,
} from "./slice";

describe("auth slice", () => {
  it("starts logged out", () => {
    const state = authReducer(undefined, { type: "@@init" });

    expect(state).toEqual({ token: null });
    expect(selectIsLoggedIn({ auth: state })).toBe(false);
  });

  it("stores the token when it is received", () => {
    const state = authReducer({ token: null }, tokenReceived("abc"));

    expect(selectToken({ auth: state })).toBe("abc");
    expect(selectIsLoggedIn({ auth: state })).toBe(true);
  });

  it("clears the token on logout and leaves the redirect to the session watcher", () => {
    const before: AuthState = { token: "abc" };

    const state = authReducer(before, logout());

    expect(state.token).toBeNull();
    expect(state.endedBy).toBe("signedOut");
    expect(selectIsLoggedIn({ auth: state })).toBe(false);
  });

  it("records that the account was deleted and clears the token", () => {
    const state = authReducer({ token: "abc" }, accountDeleted());

    expect(state).toEqual({ token: null, endedBy: "deleted" });
    expect(authReducer(state, sessionEndAcknowledged())).toEqual({ token: null });
    expect(authReducer(state, tokenReceived("new"))).toEqual({ token: "new" });
  });

  it("records that the server ended the session and clears the token", () => {
    const state = authReducer({ token: "abc" }, sessionExpired());

    expect(state).toEqual({ token: null, endedBy: "expired" });
    expect(selectSessionEndedBy({ auth: state })).toBe("expired");
  });

  it("forgets the expiry marker once it is acknowledged, on login and on logout", () => {
    const expired: AuthState = { token: null, endedBy: "expired" };

    expect(authReducer(expired, sessionEndAcknowledged())).toEqual({ token: null });
    expect(authReducer(expired, tokenReceived("new"))).toEqual({ token: "new" });
    expect(authReducer(expired, logout())).toEqual({ token: null, endedBy: "signedOut" });
  });
});
