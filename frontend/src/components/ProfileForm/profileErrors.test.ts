import { describe, expect, it } from "vitest";
import { uk } from "../../i18n/uk";
import { describeProfileError } from "./profileErrors";

const server = uk.profile.server;

function validation(...items: { type: string; loc: (string | number)[] }[]) {
  return {
    status: 422,
    data: { detail: items.map((item) => ({ ...item, msg: "SERVER-TEXT secret" })) },
  };
}

describe("describeProfileError", () => {
  it("maps a 422 to field paths and uses only the fixed texts", () => {
    const failure = describeProfileError(
      validation(
        { type: "missing", loc: ["body", "display_name"] },
        { type: "less_than_equal", loc: ["body", "latitude"] },
        { type: "enum", loc: ["body", "sports", 1, "sport"] },
        { type: "enum", loc: ["body", "capabilities", 0, "equipment"] },
      ),
    );

    expect(failure.fields).toEqual({
      display_name: server.required,
      location: server.outOfRange,
      "sports.1.sport": server.notAllowed,
      "capabilities.0.equipment": server.notAllowed,
    });
    expect(failure.message).toBe(uk.profile.saveFailed);
    expect(JSON.stringify(failure)).not.toContain("SERVER-TEXT");
  });

  it("places list-level and row-level validator errors on the inputs of the list", () => {
    const failure = describeProfileError(
      validation(
        { type: "value_error", loc: ["body", "sports"] },
        { type: "value_error", loc: ["body", "capabilities"] },
        { type: "value_error", loc: ["body", "capabilities", 2] },
      ),
    );

    expect(failure.fields).toEqual({
      "sports.0.sport": server.duplicateSport,
      "capabilities.0.category": server.duplicateCategory,
      "capabilities.2.equipment": server.equipmentMismatch,
    });
  });

  it("explains a text validator error on the name and the contact", () => {
    const failure = describeProfileError(
      validation(
        { type: "value_error", loc: ["body", "display_name"] },
        { type: "value_error", loc: ["body", "contact"] },
      ),
    );

    expect(failure.fields).toEqual({
      display_name: server.noControlCharacters,
      contact: server.noControlCharacters,
    });
  });

  it("maps location_required of either coordinate to the one location picker with a fixed text", () => {
    const failure = describeProfileError(
      validation(
        { type: "location_required", loc: ["body", "latitude"] },
        { type: "location_required", loc: ["body", "longitude"] },
      ),
    );

    expect(failure.fields).toEqual({ location: server.locationRequired });
    expect(JSON.stringify(failure)).not.toContain("SERVER-TEXT");
  });

  it("maps location_incomplete, reported against the whole body, to the location picker", () => {
    const failure = describeProfileError(
      validation({ type: "location_incomplete", loc: ["body"] }),
    );

    expect(failure.fields).toEqual({ location: server.locationIncomplete });
    expect(JSON.stringify(failure)).not.toContain("SERVER-TEXT");
  });

  it("does not map other errors against the whole body", () => {
    const failure = describeProfileError(validation({ type: "value_error", loc: ["body"] }));

    expect(failure.fields).toEqual({});
  });

  it("keeps the first error of a field and skips locations without an input", () => {
    const failure = describeProfileError(
      validation(
        { type: "missing", loc: ["body", "contact"] },
        { type: "string_too_long", loc: ["body", "contact"] },
        { type: "missing", loc: ["body", "is_visible"] },
        { type: "extra_forbidden", loc: ["body", "?"] },
      ),
    );

    expect(failure.fields).toEqual({ contact: server.required });
  });

  it("falls back to the generic text for an unknown error type", () => {
    const failure = describeProfileError(validation({ type: "invalid", loc: ["body", "intensity"] }));

    expect(failure.fields).toEqual({ intensity: server.rejected });
  });

  it("accepts a bare list as the 422 body", () => {
    const failure = describeProfileError({
      status: 422,
      data: [{ type: "missing", loc: ["body", "longitude"], msg: "x" }],
    });

    expect(failure.fields).toEqual({ location: server.required });
  });

  it.each([
    { name: "429", error: { status: 429 }, message: uk.profile.tooManyRequests },
    { name: "500", error: { status: 500 }, message: uk.profile.connectionProblem },
    { name: "network", error: { status: "FETCH_ERROR" }, message: uk.profile.connectionProblem },
    { name: "403", error: { status: 403 }, message: uk.profile.saveFailed },
    { name: "unknown", error: undefined, message: uk.profile.saveFailed },
  ])("describes $name without field errors", ({ error, message }) => {
    expect(describeProfileError(error)).toEqual({ message, fields: {} });
  });
});
