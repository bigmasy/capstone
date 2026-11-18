import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { axe } from "vitest-axe";
import { uk } from "../../i18n/uk";
import { calls, jsonResponse, noContent, routeFetch } from "../../test/api";
import { loggedIn, renderWithProviders } from "../../test/utils";
import PhotoSection from "./PhotoSection";

const text = uk.profile.photo;
const ID = "6f1c1c0e-0000-4000-8000-000000000001";

function file(bytes: number, type = "image/png", name = "me.png"): File {
  return new File([new Uint8Array(bytes)], name, { type });
}

describe("PhotoSection", () => {
  const fetchMock = vi.fn<typeof fetch>();

  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    fetchMock.mockReset();
    vi.unstubAllGlobals();
  });

  const renderSection = (hasPhoto = false) =>
    renderWithProviders(<PhotoSection profileId={ID} name="Олена" hasPhoto={hasPhoto} />, {
      preloadedState: loggedIn,
    });
  const input = (container: HTMLElement) =>
    container.querySelector('input[type="file"]') as HTMLInputElement;

  it("explains what happens to the file and offers to add a photograph", () => {
    const { container } = renderSection();

    expect(screen.getByRole("heading", { name: text.heading })).toBeInTheDocument();
    expect(screen.getByText(new RegExp(text.noteWithoutPhoto))).toBeInTheDocument();
    expect(text.rules).toMatch(/дані про місце й час зйомки з файлу видаляються/);
    expect(screen.getByRole("button", { name: text.choose })).toHaveAccessibleDescription(
      new RegExp(text.rules),
    );
    expect(screen.queryByRole("button", { name: text.remove })).toBeNull();
    expect(input(container)).toHaveAttribute("accept", "image/jpeg,image/png,image/webp");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("uploads the chosen picture as the request body and confirms it", async () => {
    routeFetch(fetchMock, {
      "PUT /profiles/me/photo": async (request) => {
        expect(request.headers.get("Content-Type")).toBe("image/png");
        expect((await request.arrayBuffer()).byteLength).toBe(1200);
        return noContent();
      },
      "GET /profiles/me": () => jsonResponse(404, {}),
    });
    const user = userEvent.setup();
    const { container } = renderSection();

    await user.upload(input(container), file(1200));

    expect(await screen.findByText(text.saved)).toHaveAttribute("role", "status");
    expect(calls(fetchMock)).toContain("PUT /profiles/me/photo");
  });

  it("refuses a file over the limit before anything is sent", async () => {
    const user = userEvent.setup();
    const { container } = renderSection();

    await user.upload(input(container), file(2 * 1024 * 1024 + 1));

    expect(await screen.findByRole("alert")).toHaveTextContent(text.tooLarge);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it.each([
    { code: "photo_invalid", message: text.invalid },
    { code: "photo_too_large", message: text.tooLarge },
  ])("explains a $code answer in its own words", async ({ code, message }) => {
    routeFetch(fetchMock, {
      "PUT /profiles/me/photo": () => jsonResponse(422, { detail: "server wording", code }),
    });
    const user = userEvent.setup();
    const { container } = renderSection();

    await user.upload(input(container), file(900));

    expect(await screen.findByRole("alert")).toHaveTextContent(message);
    expect(document.body).not.toHaveTextContent("server wording");
  });

  it("reports any other failure and lets the same file be chosen again", async () => {
    routeFetch(fetchMock, { "PUT /profiles/me/photo": () => jsonResponse(500, {}) });
    const user = userEvent.setup();
    const { container } = renderSection();

    await user.upload(input(container), file(900));

    expect(await screen.findByRole("alert")).toHaveTextContent(text.failed);
    expect(input(container).value).toBe("");
  });

  it("offers to replace or remove an existing photograph and removes it", async () => {
    routeFetch(fetchMock, {
      [`GET /profiles/${ID}/photo`]: () =>
        new Response(new Blob(["jpeg"], { type: "image/jpeg" }), { status: 200 }),
      "DELETE /profiles/me/photo": () => noContent(),
      "GET /profiles/me": () => jsonResponse(404, {}),
    });
    const user = userEvent.setup();
    renderSection(true);

    expect(screen.getByRole("button", { name: text.replace })).toBeInTheDocument();
    expect(screen.getByText(new RegExp(text.noteWithPhoto))).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: text.remove }));

    expect(await screen.findByText(text.removed)).toBeInTheDocument();
    await waitFor(() => expect(calls(fetchMock)).toContain("DELETE /profiles/me/photo"));
  });

  it("has no axe violations", async () => {
    const { container } = renderSection();

    expect(await axe(container)).toHaveNoViolations();
  });
});
