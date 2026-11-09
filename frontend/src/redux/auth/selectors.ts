import type { AuthRootState } from "./slice";

export const selectToken = (state: AuthRootState): string | null => state.auth.token;

export const selectIsLoggedIn = (state: AuthRootState): boolean => state.auth.token !== null;

export const selectSessionEndedBy = (state: AuthRootState) => state.auth.endedBy;
