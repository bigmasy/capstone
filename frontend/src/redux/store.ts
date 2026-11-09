import {
  combineReducers,
  configureStore,
  createListenerMiddleware,
  isAnyOf,
} from "@reduxjs/toolkit";
import { baseApi } from "./api/baseApi";
import { accountDeleted, authReducer, logout, sessionExpired } from "./auth/slice";
import { readToken, writeToken } from "./auth/tokenStorage";

/** The Redux DevTools hook exposes the whole state, token included: development builds only. */
export const devToolsEnabled: boolean = import.meta.env.DEV === true;

const rootReducer = combineReducers({
  auth: authReducer,
  [baseApi.reducerPath]: baseApi.reducer,
});

export type RootState = ReturnType<typeof rootReducer>;

/**
 * Builds the store. Nothing happens at import time: the token is restored from
 * sessionStorage and mirrored back only for stores created here.
 *
 * @param preloadedState Overrides the restored state (used by tests).
 */
export function setupStore(preloadedState?: Partial<RootState>) {
  // Cached data of one user must not survive a logout (privacy of the next user of the tab)
  const listener = createListenerMiddleware();
  listener.startListening({
    matcher: isAnyOf(logout, sessionExpired, accountDeleted),
    effect: (_action, api) => {
      api.dispatch(baseApi.util.resetApiState());
    },
  });

  const store = configureStore({
    reducer: rootReducer,
    devTools: devToolsEnabled,
    preloadedState: { auth: { token: readToken() }, ...preloadedState },
    middleware: (getDefaultMiddleware) =>
      getDefaultMiddleware().prepend(listener.middleware).concat(baseApi.middleware),
  });

  let persistedToken = store.getState().auth.token;
  store.subscribe(() => {
    const { token } = store.getState().auth;
    if (token !== persistedToken) {
      persistedToken = token;
      writeToken(token);
    }
  });

  return store;
}

export type AppStore = ReturnType<typeof setupStore>;
export type AppDispatch = AppStore["dispatch"];
