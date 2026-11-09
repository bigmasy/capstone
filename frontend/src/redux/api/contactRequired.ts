import type { FetchBaseQueryError } from "@reduxjs/toolkit/query/react";
import type { ContactRequiredResponse } from "../../api/types";

/** Machine code of the 409 that asks for a contact, taken from the generated contract. */
const CONTACT_REQUIRED_CODE: ContactRequiredResponse["code"] = "contact_required";

/**
 * Tells whether a failed request was refused because the caller's profile has no contact.
 *
 * Only the status and the stable `code` are read; the wording the server sends is never
 * shown. Anything that does not match, including a plain 409, is not a contact problem.
 */
export function isContactRequired(error: unknown): boolean {
  if (typeof error !== "object" || error === null) return false;
  const { status, data } = error as Partial<FetchBaseQueryError>;
  if (status !== 409) return false;
  if (typeof data !== "object" || data === null) return false;
  return (data as Partial<ContactRequiredResponse>).code === CONTACT_REQUIRED_CODE;
}
