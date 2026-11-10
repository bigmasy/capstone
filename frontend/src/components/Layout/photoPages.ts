/** Sign-in and account pages: a form beside a photograph on a wide screen. */
export const AUTH_PATHS: ReadonlySet<string> = new Set([
  "/login",
  "/register",
  "/forgot-password",
  "/reset-password",
]);

/** Pages that show a photograph; the licences ask for a credit exactly there. */
export const PHOTO_PATHS: ReadonlySet<string> = new Set(["/", "/about", ...AUTH_PATHS]);
