import { uk } from "../../i18n/uk";

/**
 * Text for a failed password-recovery request. Only the HTTP status decides it; text from the
 * server is never shown, because it could echo what the person typed.
 *
 * @param error The `error` of an RTK Query result (any value is accepted).
 * @param fallback What to say when the status gives no better reason.
 */
export function recoveryErrorMessage(
  error: unknown,
  fallback: string = uk.auth.connectionProblem,
) {
  if (typeof error !== "object" || error === null) return fallback;
  const { status } = error as { status?: unknown };
  if (status === 429) return uk.auth.tooManyAttempts;
  if (
    status === "FETCH_ERROR" ||
    status === "PARSING_ERROR" ||
    status === "TIMEOUT_ERROR" ||
    (typeof status === "number" && status >= 500)
  ) {
    return uk.auth.connectionProblem;
  }
  return fallback;
}
