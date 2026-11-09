import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { uk } from "../../i18n/uk";
import LocationMap from "./LocationMap";

/*
 * Leaflet needs layout, which jsdom does not have, so the library is replaced by a recorder.
 * The tests check what the component asks Leaflet to do: which tiles, which rectangle, which
 * marker, which handlers, and what it reports back.
 */
interface FakeLatLng {
  lat: number;
  lng: number;
  wrap: () => FakeLatLng;
}

type Handler = (event?: unknown) => void;

interface FakeLayer {
  handlers: Record<string, Handler[]>;
  options: Record<string, unknown>;
  removed: boolean;
  on: (name: string, handler: Handler) => FakeLayer;
  addTo: (map: unknown) => FakeLayer;
  remove: () => FakeLayer;
}

interface FakeMap extends FakeLayer {
  container: HTMLElement;
  zoom: number;
  setView: ReturnType<typeof vi.fn>;
  getZoom: () => number;
}

interface FakeMarker extends FakeLayer {
  latlng: [number, number];
  setLatLng: ReturnType<typeof vi.fn>;
  getLatLng: () => FakeLatLng;
  drag: (to: [number, number]) => void;
}

interface FakeRectangle extends FakeLayer {
  bounds: [[number, number], [number, number]];
  setBounds: ReturnType<typeof vi.fn>;
}

interface FakeTileLayer extends FakeLayer {
  url: string;
}

const recorded = vi.hoisted(() => ({
  maps: [] as unknown[],
  markers: [] as unknown[],
  rectangles: [] as unknown[],
  tiles: [] as unknown[],
  icons: [] as Record<string, unknown>[],
  controls: [] as { kind: "zoom" | "attribution"; options: Record<string, unknown>; added: boolean }[],
}));

vi.mock("leaflet", () => {
  const latLng = (lat: number, lng: number): FakeLatLng => ({
    lat,
    lng,
    // Longitudes outside -180..180 are wrapped back, as Leaflet's LatLng.wrap does
    wrap: () => latLng(lat, lng > 180 ? lng - 360 : lng < -180 ? lng + 360 : lng),
  });
  const layer = (options: Record<string, unknown>): FakeLayer => {
    const self: FakeLayer = {
      handlers: {},
      options,
      removed: false,
      on(name, handler) {
        (self.handlers[name] ??= []).push(handler);
        return self;
      },
      addTo() {
        return self;
      },
      remove() {
        self.removed = true;
        return self;
      },
    };
    return self;
  };
  return {
    map: (container: HTMLElement, options: Record<string, unknown>) => {
      const self = Object.assign(layer(options), {
        container,
        zoom: options.zoom as number,
        setView: vi.fn(),
        getZoom: () => self.zoom,
      }) as FakeMap;
      recorded.maps.push(self);
      return self;
    },
    tileLayer: (url: string, options: Record<string, unknown>) => {
      const self: FakeTileLayer = Object.assign(layer(options), { url });
      recorded.tiles.push(self);
      return self;
    },
    rectangle: (bounds: FakeRectangle["bounds"], options: Record<string, unknown>) => {
      const self = Object.assign(layer(options), { bounds, setBounds: vi.fn() }) as FakeRectangle;
      self.setBounds.mockImplementation((next: FakeRectangle["bounds"]) => {
        self.bounds = next;
      });
      recorded.rectangles.push(self);
      return self;
    },
    marker: (position: [number, number], options: Record<string, unknown>) => {
      const self = Object.assign(layer(options), {
        latlng: position,
        setLatLng: vi.fn(),
        getLatLng: () => latLng(self.latlng[0], self.latlng[1]),
        drag: (to: [number, number]) => {
          self.latlng = to;
          for (const handler of self.handlers.drag ?? []) handler();
        },
      }) as FakeMarker;
      self.setLatLng.mockImplementation((next: [number, number]) => {
        self.latlng = next;
      });
      recorded.markers.push(self);
      return self;
    },
    icon: (options: Record<string, unknown>) => {
      recorded.icons.push(options);
      return options;
    },
    control: {
      zoom: (options: Record<string, unknown>) => {
        const entry = { kind: "zoom" as const, options, added: false };
        recorded.controls.push(entry);
        return { addTo: () => ((entry.added = true), entry) };
      },
      attribution: (options: Record<string, unknown>) => {
        const entry = { kind: "attribution" as const, options, added: false };
        recorded.controls.push(entry);
        return { addTo: () => ((entry.added = true), entry) };
      },
    },
    __latLng: latLng,
  };
});

const text = uk.profile.location;
const centre = { latitude: 50.46, longitude: 30.51 };

const lastOf = <T,>(list: unknown[]): T => list.at(-1) as T;
const click = (map: FakeMap, lat: number, lng: number) => {
  const wrapped = (n: number) => (n > 180 ? n - 360 : n < -180 ? n + 360 : n);
  const point: FakeLatLng = {
    lat,
    lng,
    wrap: () => ({ lat, lng: wrapped(lng), wrap: () => point }),
  };
  for (const handler of map.handlers.click ?? []) handler({ latlng: point });
};

function setReducedMotion(reduced: boolean) {
  window.matchMedia = (query: string) => ({
    matches: reduced && query.includes("prefers-reduced-motion"),
    media: query,
    onchange: null,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
    addListener: () => undefined,
    removeListener: () => undefined,
    dispatchEvent: () => false,
  });
}

describe("LocationMap", () => {
  const originalMatchMedia = window.matchMedia.bind(window);

  beforeEach(() => {
    for (const list of Object.values(recorded)) list.length = 0;
    setReducedMotion(false);
  });

  afterEach(() => {
    window.matchMedia = originalMatchMedia;
  });

  it("renders a labelled group that holds the map and can be described by the area text", () => {
    render(<LocationMap value={null} onPick={vi.fn()} recenterKey={0} describedBy="area" />);

    const group = screen.getByRole("group", { name: text.mapLabel });
    expect(group).toHaveAttribute("aria-describedby", "area");
    expect(lastOf<FakeMap>(recorded.maps).container).toBe(group);
  });

  it("starts on Ukraine with keyboard control and no animation under reduced motion", () => {
    setReducedMotion(true);
    render(<LocationMap value={null} onPick={vi.fn()} recenterKey={0} />);

    const { options } = lastOf<FakeMap>(recorded.maps);
    expect(options).toMatchObject({
      center: [48.6, 31.2],
      zoom: 6,
      keyboard: true,
      zoomAnimation: false,
      fadeAnimation: false,
      markerZoomAnimation: false,
    });
  });

  it("labels the zoom buttons in Ukrainian instead of Leaflet's English defaults", () => {
    render(<LocationMap value={null} onPick={vi.fn()} recenterKey={0} />);

    expect(lastOf<FakeMap>(recorded.maps).options).toMatchObject({ zoomControl: false });
    const zoom = recorded.controls.find((control) => control.kind === "zoom");
    expect(zoom).toMatchObject({
      added: true,
      options: { zoomInTitle: text.zoomIn, zoomOutTitle: text.zoomOut },
    });
  });

  it("drops the English Leaflet prefix from the attribution and keeps the map credit", () => {
    render(<LocationMap value={null} onPick={vi.fn()} recenterKey={0} />);

    expect(lastOf<FakeMap>(recorded.maps).options).toMatchObject({ attributionControl: false });
    const attribution = recorded.controls.find((control) => control.kind === "attribution");
    expect(attribution).toMatchObject({ added: true, options: { prefix: false } });
    expect(String(lastOf<FakeTileLayer>(recorded.tiles).options.attribution)).toContain("OpenStreetMap");
  });

  it("animates when the user has no motion preference", () => {
    render(<LocationMap value={null} onPick={vi.fn()} recenterKey={0} />);

    expect(lastOf<FakeMap>(recorded.maps).options).toMatchObject({ zoomAnimation: true, fadeAnimation: true });
  });

  it("starts on the chosen area when there is one", () => {
    render(<LocationMap value={centre} onPick={vi.fn()} recenterKey={0} />);

    expect(lastOf<FakeMap>(recorded.maps).options).toMatchObject({ center: [50.46, 30.51], zoom: 11 });
  });

  it("loads OpenStreetMap tiles from the single allowed host with a linked attribution", () => {
    render(<LocationMap value={null} onPick={vi.fn()} recenterKey={0} />);

    const tile = lastOf<FakeTileLayer>(recorded.tiles);
    expect(tile.url).toBe("https://tile.openstreetmap.org/{z}/{x}/{y}.png");
    expect(tile.options.attribution).toContain('href="https://www.openstreetmap.org/copyright"');
    expect(tile.options.attribution).toContain("OpenStreetMap");
    expect(tile.options.attribution).toContain("contributors");
    expect(tile.options.maxZoom).toBe(19);
  });

  it("draws nothing before an area is chosen", () => {
    render(<LocationMap value={null} onPick={vi.fn()} recenterKey={0} />);

    expect(recorded.rectangles).toHaveLength(0);
    expect(recorded.markers).toHaveLength(0);
  });

  describe("the privacy preview", () => {
    it("draws the exact cell that is stored, not interactive, with the class from the stylesheet", () => {
      render(<LocationMap value={centre} onPick={vi.fn()} recenterKey={0} />);

      const area = lastOf<FakeRectangle>(recorded.rectangles);
      expect(area.bounds).toEqual([
        [50.44, 30.48],
        [50.48, 30.54],
      ]);
      expect(area.options).toMatchObject({ interactive: false });
      expect(area.options.className).toEqual(expect.any(String));
      expect(area.options.className).not.toBe("");
    });

    it("draws the cell of a value even when it is not exactly a centre", () => {
      render(<LocationMap value={{ latitude: 50.4501, longitude: 30.5236 }} onPick={vi.fn()} recenterKey={0} />);

      expect(lastOf<FakeRectangle>(recorded.rectangles).bounds).toEqual([
        [50.44, 30.48],
        [50.48, 30.54],
      ]);
    });

    it("puts a draggable marker with bundled icons at the centre of the cell", () => {
      render(<LocationMap value={centre} onPick={vi.fn()} recenterKey={0} />);

      const pin = lastOf<FakeMarker>(recorded.markers);
      expect(pin.latlng).toEqual([50.46, 30.51]);
      expect(pin.options).toMatchObject({ draggable: true, keyboard: false, alt: text.markerLabel });
      const urls = Object.values(lastOf<Record<string, unknown>>(recorded.icons)).filter(
        (value): value is string => typeof value === "string",
      );
      expect(urls.length).toBeGreaterThan(0);
      for (const url of urls) expect(url).not.toMatch(/^https?:\/\//);
    });

    it("moves the rectangle and the marker when the value changes and removes both when it is cleared", () => {
      const { rerender } = render(<LocationMap value={centre} onPick={vi.fn()} recenterKey={0} />);
      const area = lastOf<FakeRectangle>(recorded.rectangles);
      const pin = lastOf<FakeMarker>(recorded.markers);

      rerender(<LocationMap value={{ latitude: 50.5, longitude: 30.51 }} onPick={vi.fn()} recenterKey={0} />);

      expect(area.bounds).toEqual([
        [50.48, 30.48],
        [50.52, 30.54],
      ]);
      expect(pin.latlng).toEqual([50.5, 30.51]);
      expect(recorded.rectangles).toHaveLength(1);
      expect(recorded.markers).toHaveLength(1);

      rerender(<LocationMap value={null} onPick={vi.fn()} recenterKey={0} />);

      expect(area.removed).toBe(true);
      expect(pin.removed).toBe(true);
    });

    it("draws the layers when a value arrives after the first render", () => {
      const { rerender } = render(<LocationMap value={null} onPick={vi.fn()} recenterKey={0} />);

      rerender(<LocationMap value={centre} onPick={vi.fn()} recenterKey={0} />);

      expect(recorded.rectangles).toHaveLength(1);
      expect(recorded.markers).toHaveLength(1);
    });
  });

  describe("picking a point", () => {
    it("reports a click, wrapped into the valid longitude range", () => {
      const onPick = vi.fn();
      render(<LocationMap value={null} onPick={onPick} recenterKey={0} />);

      click(lastOf<FakeMap>(recorded.maps), 50.4517, 30.5249);
      click(lastOf<FakeMap>(recorded.maps), 10, 190);

      expect(onPick).toHaveBeenNthCalledWith(1, 50.4517, 30.5249);
      expect(onPick).toHaveBeenNthCalledWith(2, 10, -170);
    });

    it("always calls the latest onPick, also after a re-render", () => {
      const first = vi.fn();
      const second = vi.fn();
      const { rerender } = render(<LocationMap value={null} onPick={first} recenterKey={0} />);

      rerender(<LocationMap value={null} onPick={second} recenterKey={0} />);
      click(lastOf<FakeMap>(recorded.maps), 49, 24);

      expect(first).not.toHaveBeenCalled();
      expect(second).toHaveBeenCalledWith(49, 24);
    });

    it("shows the cell under the marker while dragging and reports the drop", () => {
      const onPick = vi.fn();
      render(<LocationMap value={centre} onPick={onPick} recenterKey={0} />);
      const pin = lastOf<FakeMarker>(recorded.markers);
      const area = lastOf<FakeRectangle>(recorded.rectangles);

      pin.drag([-33.8688, 151.2093]);

      expect(area.bounds).toEqual([
        [-33.88, 151.2],
        [-33.84, 151.26],
      ]);
      expect(onPick).not.toHaveBeenCalled();

      for (const handler of pin.handlers.dragend ?? []) handler();

      expect(onPick).toHaveBeenCalledWith(-33.8688, 151.2093);
    });
  });

  describe("recentring", () => {
    it("does nothing on the first render and moves the view when the key changes", () => {
      const { rerender } = render(<LocationMap value={centre} onPick={vi.fn()} recenterKey={0} />);
      const map = lastOf<FakeMap>(recorded.maps);
      expect(map.setView).not.toHaveBeenCalled();

      rerender(<LocationMap value={{ latitude: 49.86, longitude: 24.03 }} onPick={vi.fn()} recenterKey={1} />);

      expect(map.setView).toHaveBeenCalledTimes(1);
      expect(map.setView).toHaveBeenCalledWith([49.86, 24.03], 11, { animate: true });
    });

    it("keeps a zoom that is already closer and skips the animation under reduced motion", () => {
      setReducedMotion(true);
      const { rerender } = render(<LocationMap value={centre} onPick={vi.fn()} recenterKey={0} />);
      const map = lastOf<FakeMap>(recorded.maps);
      map.zoom = 15;

      rerender(<LocationMap value={centre} onPick={vi.fn()} recenterKey={2} />);

      expect(map.setView).toHaveBeenCalledWith([50.46, 30.51], 15, { animate: false });
    });

    it("does not move when there is no value to move to", () => {
      const { rerender } = render(<LocationMap value={null} onPick={vi.fn()} recenterKey={0} />);

      rerender(<LocationMap value={null} onPick={vi.fn()} recenterKey={1} />);

      expect(lastOf<FakeMap>(recorded.maps).setView).not.toHaveBeenCalled();
    });
  });

  it("destroys the map when it is unmounted, so no handler or tile request remains", () => {
    const { unmount } = render(<LocationMap value={centre} onPick={vi.fn()} recenterKey={0} />);
    const map = lastOf<FakeMap>(recorded.maps);

    unmount();

    expect(map.removed).toBe(true);
  });
});
