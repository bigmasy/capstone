import type { FetchBaseQueryError } from "@reduxjs/toolkit/query/react";
import type { EmailNotVerifiedResponse } from "../../api/types";

/** Machine code of the 403 that asks for a confirmed e-mail address, from the generated contract. */
const EMAIL_NOT_VERIFIED_CODE: EmailNotVerifiedResponse["code"] = "email_not_verified";

/**
 * Tells whether a failed request was refused because the caller has not confirmed the e-mail
 * address. Only the status and the stable `code` are read; the wording the server sends is
 * never shown, and any other 403 (such as answering one's own invitation) is not this problem.
 */
export function isEmailNotVerified(error: unknown): boolean {
  if (typeof error !== "object" || error === null) return false;
  const { status, data } = error as Partial<FetchBaseQueryError>;
  if (status !== 403) return false;
  if (typeof data !== "object" || data === null) return false;
  return (data as Partial<EmailNotVerifiedResponse>).code === EMAIL_NOT_VERIFIED_CODE;
}
