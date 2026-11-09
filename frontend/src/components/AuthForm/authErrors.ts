import { uk } from "../../i18n/uk";

export type AuthMode = "login" | "register";
export type AuthField = "email" | "password";

export interface AuthFailure {
  /** Form-level message in Ukrainian. */
  message: string;
  /** Field-level messages for a validation answer of the server. */
  fields: Partial<Record<AuthField, string>>;
  /** True when the message should be followed by a link to the login page. */
  linkToLogin?: true;
}

const fieldMessages: Record<AuthField, string> = {
  email: uk.auth.serverRejectedEmail,
  password: uk.auth.serverRejectedPassword,
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

/** Field names that a 422 answer points at; the server's own wording is never used. */
function rejectedFields(data: unknown): AuthField[] {
  const items = Array.isArray(data) ? data : isRecord(data) ? data.detail : undefined;
  if (!Array.isArray(items)) return [];

  const fields: AuthField[] = [];
  for (const item of items as unknown[]) {
    if (!isRecord(item) || !Array.isArray(item.loc)) continue;
    const name = (item.loc as unknown[]).at(-1);
    if ((name === "email" || name === "password") && !fields.includes(name)) {
      fields.push(name);
    }
  }
  return fields;
}

/**
 * Turns a failed auth request into text for the user.
 *
 * Only the HTTP status and the name of the offending field are used; text sent by the
 * server is never shown, because it could echo what the user typed.
 *
 * @param error The `error` of an RTK Query result (any value is accepted).
 */
export function describeAuthError(error: unknown, mode: AuthMode): AuthFailure {
  const generic = mode === "login" ? uk.auth.loginFailed : uk.auth.registerFailed;
  if (!isRecord(error)) return { message: generic, fields: {} };

  const { status } = error;
  if (status === 401 && mode === "login") {
    return { message: uk.auth.invalidCredentials, fields: {} };
  }
  if (status === 429) {
    return { message: uk.auth.tooManyAttempts, fields: {} };
  }
  if (status === 409 && mode === "register") {
    return { message: uk.auth.accountExists, fields: {}, linkToLogin: true };
  }
  if (
    status === "FETCH_ERROR" ||
    status === "PARSING_ERROR" ||
    status === "TIMEOUT_ERROR" ||
    (typeof status === "number" && status >= 500)
  ) {
    return { message: uk.auth.connectionProblem, fields: {} };
  }
  if (status === 422) {
    const names = rejectedFields(error.data);
    if (names.length > 0) {
      return {
        message: generic,
        fields: Object.fromEntries(names.map((name) => [name, fieldMessages[name]])),
      };
    }
  }
  return { message: generic, fields: {} };
}
