import { waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { axe } from "vitest-axe";
import { calls, jsonResponse, routeFetch } from "../../test/api";
import { loggedIn, renderWithProviders } from "../../test/utils";
import Avatar from "./Avatar";
import { MOTIFS } from "./placeholder";

const ID = "6f1c1c0e-0000-4000-8000-0000000000a1";

describe("Avatar", () => {
  const fetchMock = vi.fn<typeof fetch>();

  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    fetchMock.mockReset();
    vi.unstubAllGlobals();
  });

  const renderAvatar = (hasPhoto: boolean, name = "Андрій") =>
    renderWithProviders(<Avatar profileId={ID} name={name} hasPhoto={hasPhoto} />, {
      preloadedState: loggedIn,
    });

  it("draws a placeholder with the initial and asks the server for nothing", () => {
    const { container } = renderAvatar(false);

    const picture = container.querySelector("svg");
    expect(picture).toHaveAttribute("aria-hidden", "true");
    expect(MOTIFS).toContain(picture?.getAttribute("data-avatar"));
    expect(picture).toHaveTextContent("А");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("draws the same placeholder for the same profile whatever the name", () => {
    const first = renderAvatar(false, "Андрій").container.querySelector("svg");
    const second = renderAvatar(false, "Богдан").container.querySelector("svg");

    expect(second?.getAttribute("data-avatar")).toBe(first?.getAttribute("data-avatar"));
    expect(second?.getAttribute("style")).toBe(first?.getAttribute("style"));
  });

  it("loads the photograph with the token and shows it as a decorative image", async () => {
    routeFetch(fetchMock, {
      [`GET /profiles/${ID}/photo`]: (request) => {
        expect(request.headers.get("Authorization")).toBe("Bearer test-token");
        return new Response(new Blob(["jpeg"]), {
          status: 200,
          headers: { "Content-Type": "image/jpeg" },
        });
      },
    });
    const { container } = renderAvatar(true);

    // The placeholder holds the place until the picture arrives
    expect(container.querySelector("svg")).not.toBeNull();
    await waitFor(() => expect(container.querySelector("img")).not.toBeNull());
    const image = container.querySelector("img");
    // A data URL, the only kind besides the site itself that the content security policy allows
    expect(image?.getAttribute("src")).toMatch(/^data:image\/jpeg;base64,/);
    expect(image).toHaveAttribute("alt", "");
    expect(calls(fetchMock)).toEqual([`GET /profiles/${ID}/photo`]);
  });

  it("keeps the placeholder when the photograph cannot be loaded", async () => {
    routeFetch(fetchMock, {
      [`GET /profiles/${ID}/photo`]: () => jsonResponse(404, { detail: "Photo not found" }),
    });
    const { container } = renderAvatar(true);

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    expect(container.querySelector("img")).toBeNull();
    expect(container.querySelector("svg")).not.toBeNull();
  });

  it("has no axe violations", async () => {
    const { container } = renderAvatar(false);

    expect(await axe(container)).toHaveNoViolations();
  });
});
