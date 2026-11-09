import type { MatchFeed, SearchRadius, SportCode } from "../../api/types";
import { baseApi } from "./baseApi";

/** Number of candidates on one page of the feed. */
export const FEED_PAGE_SIZE = 10;

export interface MatchesArgs {
  /** Zero-based page number; the request sends `skip` and `limit` computed from it. */
  page: number;
  /** Narrower search radius; absent means the whole radius. */
  radius?: SearchRadius;
  sport?: SportCode;
}

export const feedApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    /** One page of the caller's feed; the error status is 404 while the caller has no profile. */
    getMatches: build.query<MatchFeed, MatchesArgs>({
      query: ({ page, radius, sport }) => ({
        url: "/matches",
        // Undefined values are left out of the query string
        params: {
          skip: page * FEED_PAGE_SIZE,
          limit: FEED_PAGE_SIZE,
          radius_km: radius,
          sport,
        },
      }),
      providesTags: ["Match"],
    }),
  }),
});

export const { useGetMatchesQuery } = feedApi;
