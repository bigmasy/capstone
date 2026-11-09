import { createSlice, type PayloadAction } from "@reduxjs/toolkit";

export interface AuthState {
  /** Bearer access token; null while logged out. */
  token: string | null;
  /**
   * Set when the session ended: the server rejected the token (`expired`), the user deleted
   * the account (`deleted`) or pressed "log out" (`signedOut`). The session watcher reads it
   * once to redirect (to the login page, or to the landing page) and then acknowledges it.
   * The redirect is done there, after the routes, so that it wins over the redirect that a
   * private page makes as soon as the token is gone.
   */
  endedBy?: "expired" | "deleted" | "signedOut";
}

/** Minimal shape of the root state that auth selectors and the base query rely on. */
export interface AuthRootState {
  auth: AuthState;
}

const initialState: AuthState = { token: null };

const authSlice = createSlice({
  name: "auth",
  initialState,
  reducers: {
    tokenReceived(state, action: PayloadAction<string>) {
      state.token = action.payload;
      delete state.endedBy;
    },
    /** The user chose to end the session. */
    logout(state) {
      state.token = null;
      state.endedBy = "signedOut";
    },
    /** The server rejected the token (HTTP 401). */
    sessionExpired(state) {
      state.token = null;
      state.endedBy = "expired";
    },
    /** The account was deleted on the server: the token is void and the user goes to the landing page. */
    accountDeleted(state) {
      state.token = null;
      state.endedBy = "deleted";
    },
    sessionEndAcknowledged(state) {
      delete state.endedBy;
    },
  },
});

export const { tokenReceived, logout, sessionExpired, accountDeleted, sessionEndAcknowledged } =
  authSlice.actions;
export const authReducer = authSlice.reducer;
