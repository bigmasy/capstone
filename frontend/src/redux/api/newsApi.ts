import type { NewsFeed } from "../../api/types";
import { baseApi } from "./baseApi";

/** Items shown in each column of the landing page. */
export const NEWS_PER_COLUMN = 6;

export const newsApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    /** The digest of the landing page; public, so it works without a session. */
    getNews: build.query<NewsFeed, void>({
      query: () => ({ url: "/news", params: { limit: NEWS_PER_COLUMN } }),
    }),
  }),
});

export const { useGetNewsQuery } = newsApi;
