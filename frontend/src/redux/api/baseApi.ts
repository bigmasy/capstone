import {
  createApi,
  fetchBaseQuery,
  type BaseQueryFn,
  type FetchArgs,
  type FetchBaseQueryError,
} from "@reduxjs/toolkit/query/react";
import { selectToken } from "../auth/selectors";
import { sessionExpired, type AuthRootState } from "../auth/slice";

export const API_BASE_URL: string = import.meta.env.VITE_API_BASE_URL ?? "/api/v1";

const rawBaseQuery = fetchBaseQuery({
  baseUrl: API_BASE_URL,
  prepareHeaders: (headers, { getState }) => {
    const token = selectToken(getState() as AuthRootState);
    if (token) {
      headers.set("Authorization", `Bearer ${token}`);
    }
    return headers;
  },
});

/**
 * Wraps the fetch base query: a 401 answer to a request that carried a token means the
 * session is no longer valid, so it is ended. A 401 without a token (for example wrong
 * credentials on the login form) is left to the caller.
 *
 * The session is ended only if the token in the state is still the one that was sent:
 * a slow request from a previous session must not log out the user who has just logged in.
 */
export const baseQueryWithAuth: BaseQueryFn<string | FetchArgs, unknown, FetchBaseQueryError> = async (
  args,
  api,
  extraOptions,
) => {
  const sentToken = selectToken(api.getState() as AuthRootState);
  const result = await rawBaseQuery(args, api, extraOptions);
  if (
    sentToken !== null &&
    result.error?.status === 401 &&
    selectToken(api.getState() as AuthRootState) === sentToken
  ) {
    api.dispatch(sessionExpired());
  }
  return result;
};

/** Empty API slice; feature endpoints are added with `baseApi.injectEndpoints`. */
export const baseApi = createApi({
  reducerPath: "api",
  baseQuery: baseQueryWithAuth,
  // Feature APIs add their own tag types here
  tagTypes: ["Profile", "Match", "Invitation", "Account", "Photo"],
  endpoints: () => ({}),
});
