import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  bodiesSentTo,
  calls,
  jsonResponse,
  makeInvitation,
  routeFetch,
} from "../../test/api";
import { setupStore } from "../store";
import { INVITATIONS_PAGE_SIZE, invitationsApi, pageOfInvitations } from "./invitationsApi";

const ID = "6f1c1c0e-0000-4000-8000-0000000000c1";

describe("invitationsApi", () => {
  const fetchMock = vi.fn<typeof fetch>();

  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    fetchMock.mockReset();
    vi.unstubAllGlobals();
  });

  const loggedInStore = () => setupStore({ auth: { token: "tok" } });

  it("asks for one invitation more than a page so that a next page can be detected", async () => {
    routeFetch(fetchMock, { "GET /invitations": () => jsonResponse(200, []) });

    await loggedInStore().dispatch(
      invitationsApi.endpoints.getInvitations.initiate({
        direction: "incoming",
        status: "pending",
        page: 1,
      }),
    );

    expect(calls(fetchMock)).toEqual([
      `GET /invitations?direction=incoming&status=pending&skip=${INVITATIONS_PAGE_SIZE}&limit=${INVITATIONS_PAGE_SIZE + 1}`,
    ]);
  });

  it("leaves the status out of the request when no status is chosen", async () => {
    routeFetch(fetchMock, { "GET /invitations": () => jsonResponse(200, []) });

    await loggedInStore().dispatch(
      invitationsApi.endpoints.getInvitations.initiate({ direction: "outgoing", page: 0 }),
    );

    expect(calls(fetchMock)).toEqual(["GET /invitations?direction=outgoing&skip=0&limit=11"]);
  });

  it("pageOfInvitations cuts the extra invitation and reports the next page", () => {
    const many = Array.from({ length: INVITATIONS_PAGE_SIZE + 1 }, () => makeInvitation("incoming"));

    expect(pageOfInvitations(many)).toMatchObject({ hasNext: true });
    expect(pageOfInvitations(many).items).toHaveLength(INVITATIONS_PAGE_SIZE);
    expect(pageOfInvitations(many.slice(0, 3))).toMatchObject({ hasNext: false });
  });

  it("sendInvitation posts only the recipient profile id", async () => {
    routeFetch(fetchMock, {
      "POST /invitations": () => jsonResponse(201, makeInvitation("outgoing")),
    });

    await loggedInStore().dispatch(
      invitationsApi.endpoints.sendInvitation.initiate({ recipient_profile_id: ID }),
    );

    expect(await bodiesSentTo(fetchMock, "POST /invitations")).toEqual([
      { recipient_profile_id: ID },
    ]);
  });

  it.each([
    ["acceptInvitation", "accept"],
    ["declineInvitation", "decline"],
    ["cancelInvitation", "cancel"],
  ] as const)("%s posts to the %s route", async (endpoint, action) => {
    routeFetch(fetchMock, {
      [`POST /invitations/${ID}/${action}`]: () => jsonResponse(200, makeInvitation("incoming")),
    });

    await loggedInStore().dispatch(invitationsApi.endpoints[endpoint].initiate(ID));

    expect(calls(fetchMock)).toEqual([`POST /invitations/${ID}/${action}`]);
  });

  it("refetches the list after an answer, also when the answer is a conflict", async () => {
    routeFetch(fetchMock, {
      "GET /invitations": () => jsonResponse(200, [makeInvitation("incoming")]),
      [`POST /invitations/${ID}/accept`]: () => jsonResponse(409, { detail: "gone" }),
    });
    const store = loggedInStore();
    const subscription = store.dispatch(
      invitationsApi.endpoints.getInvitations.initiate({ direction: "incoming", page: 0 }),
    );
    await subscription;

    const result = await store.dispatch(invitationsApi.endpoints.acceptInvitation.initiate(ID));

    expect(result).toMatchObject({ error: { status: 409 } });
    await vi.waitFor(() =>
      expect(calls(fetchMock).filter((call) => call.startsWith("GET /invitations"))).toHaveLength(2),
    );
    subscription.unsubscribe();
  });
});
