import { describe, expect, it } from "vitest";
import { isContactRequired } from "./contactRequired";

describe("isContactRequired", () => {
  it("accepts a 409 that carries the contact_required code", () => {
    expect(
      isContactRequired({ status: 409, data: { detail: "x", code: "contact_required" } }),
    ).toBe(true);
  });

  it.each([
    ["a 409 without a code", { status: 409, data: { detail: "x" } }],
    ["a 409 with another code", { status: 409, data: { detail: "x", code: "other" } }],
    ["a 409 without a body", { status: 409, data: null }],
    ["a 409 with a text body", { status: 409, data: "contact_required" }],
    ["another status with the code", { status: 404, data: { code: "contact_required" } }],
    ["a network error", { status: "FETCH_ERROR", error: "failed" }],
    ["nothing", undefined],
    ["a string", "contact_required"],
  ])("rejects %s", (_name, error) => {
    expect(isContactRequired(error)).toBe(false);
  });
});
