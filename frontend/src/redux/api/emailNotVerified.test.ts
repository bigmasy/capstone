import { describe, expect, it } from "vitest";
import { isEmailNotVerified } from "./emailNotVerified";

describe("isEmailNotVerified", () => {
  it("recognises the coded 403 only", () => {
    expect(isEmailNotVerified({ status: 403, data: { detail: "x", code: "email_not_verified" } })).toBe(true);
    // Any other 403, such as answering one's own invitation, is a different problem
    expect(isEmailNotVerified({ status: 403, data: { detail: "x" } })).toBe(false);
    expect(isEmailNotVerified({ status: 403, data: { code: "something_else" } })).toBe(false);
    expect(isEmailNotVerified({ status: 409, data: { code: "email_not_verified" } })).toBe(false);
  });

  it("is false for anything that is not an error body", () => {
    expect(isEmailNotVerified(undefined)).toBe(false);
    expect(isEmailNotVerified("403")).toBe(false);
    expect(isEmailNotVerified({ status: 403, data: "email_not_verified" })).toBe(false);
    expect(isEmailNotVerified({ status: "FETCH_ERROR", error: "x" })).toBe(false);
  });
});
