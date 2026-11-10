import type {
  FetchArgs,
  FetchBaseQueryError,
} from "@reduxjs/toolkit/query/react";
import type { Account, Credentials, TokenResponse } from "../../api/types";
import { tokenReceived } from "../auth/slice";
import { baseApi } from "./baseApi";

/**
 * Result of the login and register mutations. It never carries the token: everything in
 * the API cache lives in `state.api`, which the Redux DevTools and error reports can show.
 * The token goes straight into the auth slice instead.
 */
export interface LoginResult {
  /** False only when an account was created but the following login failed. */
  loggedIn: boolean;
}

type Sent =
  | { data: unknown; error?: undefined }
  | { error: FetchBaseQueryError; data?: undefined };
type Send = (args: FetchArgs) => Sent | PromiseLike<Sent>;

function isTokenResponse(value: unknown): value is TokenResponse {
  return (
    typeof value === "object" &&
    value !== null &&
    typeof (value as Partial<TokenResponse>).access_token === "string"
  );
}

/** Posts the credentials to /auth/login; returns the token or the error. */
async function requestToken(
  send: Send,
  credentials: Credentials,
): Promise<{ token: string } | { error: FetchBaseQueryError }> {
  const response = await send({
    url: "/auth/login",
    method: "POST",
    body: credentials,
  });
  if (response.error) return { error: response.error };
  if (!isTokenResponse(response.data)) {
    return {
      error: {
        status: "PARSING_ERROR",
        originalStatus: 200,
        data: "",
        error: "Unexpected login response",
      },
    };
  }
  return { token: response.data.access_token };
}

export const authApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    login: build.mutation<LoginResult, Credentials>({
      async queryFn(credentials, api, _extra, send) {
        const result = await requestToken(send, credentials);
        if ("error" in result) return { error: result.error };
        api.dispatch(tokenReceived(result.token));
        return { data: { loggedIn: true } };
      },
    }),
    /**
     * Creates the account and then logs in, as one operation. If the account was created
     * but the login step fails, the result is `{ loggedIn: false }` rather than an error,
     * because retrying the registration would only answer 409.
     */
    register: build.mutation<LoginResult, Credentials>({
      async queryFn(credentials, api, _extra, send) {
        const created = await send({
          url: "/auth/register",
          method: "POST",
          body: credentials,
        });
        if (created.error) return { error: created.error };

        const result = await requestToken(send, credentials);
        if ("error" in result) return { data: { loggedIn: false } };
        api.dispatch(tokenReceived(result.token));
        return { data: { loggedIn: true } };
      },
    }),
    /**
     * The caller's own account. It validates the restored token at bootstrap (a 401 ends the
     * session in the base query) and tells whether the e-mail address is confirmed.
     */
    me: build.query<Account, void>({
      query: () => "/auth/me",
      providesTags: ["Account"],
    }),
    /** Confirms the address with the token from the e-mailed link; no session is needed. */
    verifyEmail: build.mutation<void, string>({
      query: (token) => ({
        url: "/auth/verify-email",
        method: "POST",
        body: { token },
      }),
      // The confirmation changes what the account may do, so the account is read again
      invalidatesTags: ["Account"],
    }),
    /** Asks for the confirmation message again; the answer is always 204. */
    resendVerification: build.mutation<void, void>({
      query: () => ({ url: "/auth/resend-verification", method: "POST" }),
    }),
    /** Asks for a password-reset link; the answer is 204 for every address, known or not. */
    forgotPassword: build.mutation<void, string>({
      query: (email) => ({
        url: "/auth/forgot-password",
        method: "POST",
        body: { email },
      }),
    }),
    /** Sets a new password with the token from the e-mailed link; no session is needed. */
    resetPassword: build.mutation<void, { token: string; password: string }>({
      query: (body) => ({ url: "/auth/reset-password", method: "POST", body }),
    }),
  }),
});

export const {
  useLoginMutation,
  useRegisterMutation,
  useMeQuery,
  useVerifyEmailMutation,
  useResendVerificationMutation,
  useForgotPasswordMutation,
  useResetPasswordMutation,
} = authApi;
