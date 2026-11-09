import { uk } from "../../i18n/uk";

export interface ProfileFailure {
  /** Form-level message in Ukrainian. */
  message: string;
  /** Messages by Formik field path (for example `sports.0.sport`) for a 422 answer. */
  fields: Record<string, string>;
}

const server = uk.profile.server;

/** Fields of the form; a location outside this set has no input and is reported on the form. */
const TOP_LEVEL_FIELDS = new Set(["display_name", "district_code", "intensity", "contact"]);

/** The two coordinates of the API are one choice in the form: the location picker. */
const LOCATION_PATH = "location";
const LOCATION_FIELDS = new Set(["latitude", "longitude"]);

/** The first input of a list, where an error about the list as a whole is shown. */
const LIST_ANCHORS: Record<string, string> = {
  sports: "sports.0.sport",
  capabilities: "capabilities.0.category",
};

const LIST_ITEM_FIELDS: Record<string, readonly string[]> = {
  sports: ["sport", "skill"],
  capabilities: ["category", "level", "equipment"],
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

/** Fixed text for a pydantic error type; the text sent by the server is never shown. */
function messageFor(type: unknown, path: string, depth: number): string {
  switch (type) {
    case "missing":
      return server.required;
    case "enum":
    case "literal_error":
      return server.notAllowed;
    case "greater_than":
    case "greater_than_equal":
    case "less_than":
    case "less_than_equal":
      return server.outOfRange;
    case "string_too_long":
    case "too_long":
      return server.tooLong;
    case "string_too_short":
      return server.tooShort;
    case "too_short":
      return server.tooFewItems;
    case "location_required":
      return server.locationRequired;
    case "location_incomplete":
      return server.locationIncomplete;
    case "int_type":
    case "int_parsing":
    case "float_type":
    case "float_parsing":
      return server.number;
    case "value_error":
      // The custom validators of the contract: each has its own field and nesting depth
      if (path === "display_name" || path === "contact") return server.noControlCharacters;
      if (path.startsWith("sports")) return server.duplicateSport;
      if (path.startsWith("capabilities")) {
        return depth <= 1 ? server.duplicateCategory : server.equipmentMismatch;
      }
      return server.rejected;
    default:
      return server.rejected;
  }
}

/** Maps one error location (`["body", "sports", 0, "sport"]`) to a Formik path, or null. */
function formPath(loc: unknown[]): { path: string; depth: number } | null {
  const parts = loc[0] === "body" ? loc.slice(1) : loc;
  const [name, index, field] = parts;
  if (typeof name !== "string") return null;

  if (TOP_LEVEL_FIELDS.has(name)) return { path: name, depth: parts.length };
  if (LOCATION_FIELDS.has(name)) return { path: LOCATION_PATH, depth: parts.length };

  const itemFields = LIST_ITEM_FIELDS[name];
  if (itemFields === undefined) return null;
  if (typeof index !== "number") {
    return { path: LIST_ANCHORS[name] ?? name, depth: parts.length };
  }
  if (typeof field === "string" && itemFields.includes(field)) {
    return { path: `${name}.${index}.${field}`, depth: parts.length };
  }
  // An error about a whole row: attach it to the field that decides the row's validity
  const anchor = name === "capabilities" ? "equipment" : "sport";
  return { path: `${name}.${index}.${anchor}`, depth: parts.length };
}

/** Field errors of a 422 answer; an item without a field in the form is left out. */
function describeValidation(data: unknown): Record<string, string> {
  const items = Array.isArray(data) ? data : isRecord(data) ? data.detail : undefined;
  const fields: Record<string, string> = {};
  if (!Array.isArray(items)) return fields;

  for (const item of items as unknown[]) {
    if (!isRecord(item) || !Array.isArray(item.loc)) continue;
    const target = formPath(item.loc as unknown[]);
    if (target === null) {
      // The server reports half a location against the whole body: show it on the picker
      if (item.type === "location_incomplete") {
        fields[LOCATION_PATH] ??= server.locationIncomplete;
      }
      continue;
    }
    // The first error of a field wins; later ones would only repeat it
    fields[target.path] ??= messageFor(item.type, target.path.split(".")[0] ?? "", target.depth);
  }
  return fields;
}

/**
 * Turns a failed profile request into text for the user.
 *
 * Only the HTTP status, the error type and the location are used; text sent by the server
 * is never shown, because it could echo what the user typed.
 *
 * @param error The `error` of an RTK Query result (any value is accepted).
 */
export function describeProfileError(error: unknown): ProfileFailure {
  if (!isRecord(error)) return { message: uk.profile.saveFailed, fields: {} };

  const { status } = error;
  if (status === 429) return { message: uk.profile.tooManyRequests, fields: {} };
  if (
    status === "FETCH_ERROR" ||
    status === "PARSING_ERROR" ||
    status === "TIMEOUT_ERROR" ||
    (typeof status === "number" && status >= 500)
  ) {
    return { message: uk.profile.connectionProblem, fields: {} };
  }
  if (status === 422) {
    return { message: uk.profile.saveFailed, fields: describeValidation(error.data) };
  }
  return { message: uk.profile.saveFailed, fields: {} };
}
