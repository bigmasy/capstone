import type {
  InvitationCreate,
  InvitationDirection,
  InvitationOut,
  InvitationStatus,
} from "../../api/types";
import { baseApi } from "./baseApi";

/** Number of invitations shown on one page. */
export const INVITATIONS_PAGE_SIZE = 10;

export interface InvitationsArgs {
  direction: InvitationDirection;
  /** Absent means every status. */
  status?: InvitationStatus;
  /** Zero-based page number. */
  page: number;
}

/**
 * The list route has no total, so one invitation more than the page is requested: its
 * presence tells that a next page exists, and it is cut off before display.
 */
export function pageOfInvitations(items: readonly InvitationOut[]): {
  items: InvitationOut[];
  hasNext: boolean;
} {
  return {
    items: items.slice(0, INVITATIONS_PAGE_SIZE),
    hasNext: items.length > INVITATIONS_PAGE_SIZE,
  };
}

const LIST_TAG = { type: "Invitation", id: "LIST" } as const;

/** Answering an invitation changes the list whatever the outcome (409 means it changed already). */
const refreshList = () => [LIST_TAG];

export const invitationsApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    getInvitations: build.query<InvitationOut[], InvitationsArgs>({
      query: ({ direction, status, page }) => ({
        url: "/invitations",
        params: {
          direction,
          status,
          skip: page * INVITATIONS_PAGE_SIZE,
          limit: INVITATIONS_PAGE_SIZE + 1,
        },
      }),
      providesTags: (result) => [
        LIST_TAG,
        ...(result ?? []).map(({ id }) => ({ type: "Invitation" as const, id })),
      ],
    }),
    sendInvitation: build.mutation<InvitationOut, InvitationCreate>({
      query: (body) => ({ url: "/invitations", method: "POST", body }),
      invalidatesTags: refreshList,
    }),
    acceptInvitation: build.mutation<InvitationOut, string>({
      query: (id) => ({ url: `/invitations/${id}/accept`, method: "POST" }),
      invalidatesTags: refreshList,
    }),
    declineInvitation: build.mutation<InvitationOut, string>({
      query: (id) => ({ url: `/invitations/${id}/decline`, method: "POST" }),
      invalidatesTags: refreshList,
    }),
    cancelInvitation: build.mutation<InvitationOut, string>({
      query: (id) => ({ url: `/invitations/${id}/cancel`, method: "POST" }),
      invalidatesTags: refreshList,
    }),
  }),
});

export const {
  useGetInvitationsQuery,
  useSendInvitationMutation,
  useAcceptInvitationMutation,
  useDeclineInvitationMutation,
  useCancelInvitationMutation,
} = invitationsApi;
