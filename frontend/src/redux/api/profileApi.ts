import type { FetchBaseQueryError } from "@reduxjs/toolkit/query/react";
import type { ProfileOwner, ProfilePut, Taxonomy } from "../../api/types";
import { baseApi } from "./baseApi";

/** Taxonomy codes change only with a release, so a long cache lifetime is safe. */
const TAXONOMY_CACHE_SECONDS = 60 * 60;

/**
 * True when the answer to GET /profiles/me means "no profile yet" (HTTP 404). It is the
 * normal state of a new account, not a failure.
 */
export function isNoProfile(error: unknown): boolean {
  return (error as Partial<FetchBaseQueryError> | undefined)?.status === 404;
}

export const profileApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    /** Code lists for the profile form; public reference data, cached for a long time. */
    getTaxonomy: build.query<Taxonomy, void>({
      query: () => "/taxonomy",
      keepUnusedDataFor: TAXONOMY_CACHE_SECONDS,
    }),
    /** The caller's own profile; the error status is 404 while there is none. */
    getMyProfile: build.query<ProfileOwner, void>({
      query: () => "/profiles/me",
      providesTags: ["Profile"],
    }),
    /** Creates or replaces the caller's profile. */
    saveMyProfile: build.mutation<ProfileOwner, ProfilePut>({
      query: (body) => ({ url: "/profiles/me", method: "PUT", body }),
      // The feed is built from the caller's own profile, so a saved change makes it stale
      invalidatesTags: ["Profile", "Match"],
      async onQueryStarted(_body, { dispatch, queryFulfilled }) {
        try {
          const { data } = await queryFulfilled;
          // The answer is the new profile: show it at once instead of an interim "no profile"
          void dispatch(profileApi.util.upsertQueryData("getMyProfile", undefined, data));
        } catch {
          // The caller reports the failure; the cache stays as it was.
        }
      },
    }),
    /** Deletes the account with all data under it; the caller then ends the session. */
    deleteAccount: build.mutation<void, void>({
      query: () => ({ url: "/auth/me", method: "DELETE" }),
    }),
  }),
});

export const {
  useGetTaxonomyQuery,
  useGetMyProfileQuery,
  useSaveMyProfileMutation,
  useDeleteAccountMutation,
} = profileApi;
