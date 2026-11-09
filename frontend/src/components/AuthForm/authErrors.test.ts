import { describe, expect, it } from "vitest";
import { uk } from "../../i18n/uk";
import { describeAuthError } from "./authErrors";

describe("describeAuthError", () => {
  it("maps 401 on login to a credentials message", () => {
    expect(describeAuthError({ status: 401, data: {} }, "login")).toEqual({
      message: uk.auth.invalidCredentials,
      fields: {},
    });
  });

  it("maps 429 to a too-many-attempts message", () => {
    expect(describeAuthError({ status: 429, data: {} }, "login").message).toBe(
      uk.auth.tooManyAttempts,
    );
  });

  it.each([
    { status: "FETCH_ERROR", error: "x" } as const,
    { status: "PARSING_ERROR", originalStatus: 200, data: "", error: "x" } as const,
    { status: "TIMEOUT_ERROR", error: "x" } as const,
    { status: 500, data: {} } as const,
    { status: 503, data: {} } as const,
  ])("maps %j to a connection or server problem", (error) => {
    expect(describeAuthError(error, "login").message).toBe(uk.auth.connectionProblem);
  });

  it("maps 409 on register to an existing account with a link to the login page", () => {
    expect(describeAuthError({ status: 409, data: {} }, "register")).toEqual({
      message: uk.auth.accountExists,
      fields: {},
      linkToLogin: true,
    });
  });

  it("does not treat 409 on login as an existing account", () => {
    expect(describeAuthError({ status: 409, data: {} }, "login").linkToLogin).toBeUndefined();
  });

  it("maps a 422 list to the matching field with our own wording, not the server text", () => {
    const error = {
      status: 422,
      data: [
        { type: "string_too_short", loc: ["body", "password"], msg: "SECRET server text" },
        { type: "value_error", loc: ["body", "email"], msg: "a@b.c is bad" },
      ],
    };

    const result = describeAuthError(error, "register");

    expect(result.fields).toEqual({
      email: uk.auth.serverRejectedEmail,
      password: uk.auth.serverRejectedPassword,
    });
    expect(JSON.stringify(result)).not.toContain("SECRET");
    expect(JSON.stringify(result)).not.toContain("a@b.c");
  });

  it("accepts the 422 list wrapped in a detail key", () => {
    const result = describeAuthError(
      { status: 422, data: { detail: [{ type: "x", loc: ["body", "email"], msg: "m" }] } },
      "login",
    );

    expect(result.fields).toEqual({ email: uk.auth.serverRejectedEmail });
  });

  it("falls back to the generic message for a 422 without a known field", () => {
    const result = describeAuthError(
      { status: 422, data: [{ type: "x", loc: ["body", "extra"], msg: "m" }] },
      "register",
    );

    expect(result.fields).toEqual({});
    expect(result.message).toBe(uk.auth.registerFailed);
  });

  it("falls back to the per-mode generic message for other statuses", () => {
    expect(describeAuthError({ status: 400, data: {} }, "login").message).toBe(uk.auth.loginFailed);
    expect(describeAuthError({ status: 400, data: {} }, "register").message).toBe(
      uk.auth.registerFailed,
    );
  });

  it("falls back to the generic message for a value that is not a fetch error", () => {
    expect(describeAuthError(new Error("boom"), "login").message).toBe(uk.auth.loginFailed);
  });
});
