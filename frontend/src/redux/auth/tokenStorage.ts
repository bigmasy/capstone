/*
 * The token lives in Redux state (memory) and is mirrored to sessionStorage so a page
 * reload keeps the session. It is never written to localStorage: sessionStorage is
 * scoped to one tab and is wiped when the tab closes.
 */
const KEY = "auth.token";

/** Reads the persisted token; storage may be unavailable (private mode, blocked). */
export function readToken(): string | null {
  try {
    return window.sessionStorage.getItem(KEY);
  } catch {
    return null;
  }
}

/** Persists the token, or removes it when null. Failures are ignored on purpose. */
export function writeToken(token: string | null): void {
  try {
    if (token === null) {
      window.sessionStorage.removeItem(KEY);
    } else {
      window.sessionStorage.setItem(KEY, token);
    }
  } catch {
    // The session then simply does not survive a reload.
  }
}
