import { describe, expect, it } from "vitest";
import {
  LAT_STEP,
  LON_STEP,
  distanceKm,
  neighbourCell,
  snapToCell,
  type Direction,
} from "./gridCell";

/*
 * Golden rows produced by the server function `coarsen` (backend/app/domain/privacy.py):
 * [latitude, longitude, expected centre latitude, expected centre longitude].
 * They include negative coordinates, exact multiples of the steps (where the floating point
 * quotient decides the cell), values a hair below a boundary, and the edges of the globe.
 */
const SERVER_GOLDEN: [number, number, number, number][] = [
  [50.45, 30.5236, 50.46, 30.51],
  [0, 0, 0.02, 0.03],
  [-0.0001, -0.0001, -0.02, -0.03],
  [0.0399999, 0.0599999, 0.02, 0.03],
  [0.04, 0.06, 0.06, 0.09],
  [-0.04, -0.06, -0.02, -0.03],
  [-0.0400001, -0.0600001, -0.06, -0.09],
  [50.44, 30.48, 50.46, 30.51],
  [50.4399999, 30.4799999, 50.42, 30.45],
  [50.48, 30.54, 50.5, 30.57],
  [-33.8688, 151.2093, -33.86, 151.23],
  [-12.0464, -77.0428, -12.06, -77.07],
  [48.0, 24.0, 48.02, 24.03],
  [90, 180, 89.98, 179.97],
  [-90, -180, -89.98, -179.97],
  [89.99, 179.99, 89.98, 179.97],
  [-89.99, -179.99, -89.98, -179.97],
  [46.484167, 30.7325, 46.5, 30.75],
  [49.8419, 24.0316, 49.86, 24.03],
  [44.605, 33.5225, 44.62, 33.51],
  [52.9, 40.9, 52.9, 40.89],
  [100, 200, 89.98, 179.97],
  [-100, -200, -89.98, -179.97],
  [22.295, 22.295, 22.3, 22.29],
];

describe("snapToCell", () => {
  it.each(SERVER_GOLDEN)("mirrors the server for %s, %s", (lat, lon, centreLat, centreLon) => {
    const cell = snapToCell(lat, lon);

    expect(cell.latitude).toBe(centreLat);
    expect(cell.longitude).toBe(centreLon);
  });

  it("has the steps of the server grid", () => {
    expect(LAT_STEP).toBe(0.04);
    expect(LON_STEP).toBe(0.06);
  });

  it("returns a cell whose edges are one step apart and which contains the centre", () => {
    const cell = snapToCell(50.45, 30.5236);

    expect(cell.north - cell.south).toBeCloseTo(LAT_STEP, 9);
    expect(cell.east - cell.west).toBeCloseTo(LON_STEP, 9);
    expect(cell.latitude).toBeCloseTo((cell.south + cell.north) / 2, 9);
    expect(cell.longitude).toBeCloseTo((cell.west + cell.east) / 2, 9);
    expect(cell).toEqual({
      latitude: 50.46,
      longitude: 30.51,
      south: 50.44,
      north: 50.48,
      west: 30.48,
      east: 30.54,
    });
  });

  it("gives a cell with the lower edge included and the upper edge excluded", () => {
    const onEdge = snapToCell(50.44, 30.48);
    const justBelow = snapToCell(50.4399999, 30.4799999);

    expect(onEdge.south).toBe(50.44);
    expect(onEdge.west).toBe(30.48);
    expect(justBelow.north).toBe(50.44);
    expect(justBelow.east).toBe(30.48);
  });

  it("puts negative coordinates in the cell that contains them, not the one towards zero", () => {
    const cell = snapToCell(-0.0001, -0.0001);

    expect(cell.south).toBe(-0.04);
    expect(cell.north).toBe(0);
    expect(cell.west).toBe(-0.06);
    expect(cell.east).toBe(0);
    expect(Object.is(cell.north, -0)).toBe(false);
    expect(Object.is(cell.east, -0)).toBe(false);
  });

  it("is idempotent: the centre of a cell snaps to the same cell", () => {
    for (const [lat, lon] of SERVER_GOLDEN) {
      const cell = snapToCell(lat, lon);

      expect(snapToCell(cell.latitude, cell.longitude)).toEqual(cell);
    }
  });

  it("maps every point of a cell to the same cell (grid sweep, both signs)", () => {
    for (const [baseLat, baseLon] of [
      [50.44, 30.48],
      [-0.04, -0.06],
      [-33.88, 151.2],
      [0, 0],
    ] as const) {
      const expected = snapToCell(baseLat + 0.01, baseLon + 0.01);
      for (const fractionLat of [0.1, 0.5, 0.9]) {
        for (const fractionLon of [0.1, 0.5, 0.9]) {
          const cell = snapToCell(baseLat + fractionLat * LAT_STEP, baseLon + fractionLon * LON_STEP);

          expect(cell).toEqual(expected);
        }
      }
    }
  });

  it("places the centre within half a step of the point, for a deterministic spread of points", () => {
    // A small linear congruential generator keeps the sweep reproducible
    let seed = 12345;
    const next = () => {
      seed = (seed * 1664525 + 1013904223) % 4294967296;
      return seed / 4294967296;
    };
    for (let i = 0; i < 2000; i += 1) {
      const lat = next() * 178 - 89;
      const lon = next() * 358 - 179;
      const cell = snapToCell(lat, lon);

      expect(Math.abs(cell.latitude - lat)).toBeLessThanOrEqual(LAT_STEP / 2 + 1e-9);
      expect(Math.abs(cell.longitude - lon)).toBeLessThanOrEqual(LON_STEP / 2 + 1e-9);
      expect(cell.south).toBeLessThanOrEqual(lat + 1e-9);
      expect(cell.north).toBeGreaterThanOrEqual(lat - 1e-9);
      expect(snapToCell(cell.latitude, cell.longitude)).toEqual(cell);
    }
  });

  it("keeps every centre inside its range, also for points on and beyond the bounds", () => {
    for (const [lat, lon] of [
      [90, 180],
      [-90, -180],
      [1e9, 1e9],
      [-1e9, -1e9],
    ] as const) {
      const cell = snapToCell(lat, lon);

      expect(Math.abs(cell.latitude)).toBeLessThan(90);
      expect(Math.abs(cell.longitude)).toBeLessThan(180);
    }
  });

  it.each([
    [Number.NaN, 0],
    [0, Number.POSITIVE_INFINITY],
    [Number.NEGATIVE_INFINITY, 0],
  ])("rejects a value that is not finite without echoing it", (lat, lon) => {
    expect(() => snapToCell(lat, lon)).toThrow(RangeError);
    expect(() => snapToCell(lat, lon)).toThrow(/^coordinates must be finite numbers$/);
  });
});

describe("neighbourCell", () => {
  const start = snapToCell(50.45, 30.5236);

  it.each<[Direction, Partial<typeof start>]>([
    ["north", { latitude: 50.5, longitude: 30.51 }],
    ["south", { latitude: 50.42, longitude: 30.51 }],
    ["east", { latitude: 50.46, longitude: 30.57 }],
    ["west", { latitude: 50.46, longitude: 30.45 }],
  ])("moves one cell to the %s", (direction, centre) => {
    const next = neighbourCell(start, direction);

    expect(next).toMatchObject(centre);
    expect(snapToCell(next.latitude, next.longitude)).toEqual(next);
  });

  it("touches the old cell along one edge", () => {
    expect(neighbourCell(start, "north").south).toBe(start.north);
    expect(neighbourCell(start, "south").north).toBe(start.south);
    expect(neighbourCell(start, "east").west).toBe(start.east);
    expect(neighbourCell(start, "west").east).toBe(start.west);
  });

  it("returns to the start after a step and the opposite step, across the equator and the meridian", () => {
    const opposite: Record<Direction, Direction> = {
      north: "south",
      south: "north",
      east: "west",
      west: "east",
    };
    for (const cell of [start, snapToCell(-0.001, -0.001), snapToCell(0.001, 0.001)]) {
      for (const direction of ["north", "south", "east", "west"] as const) {
        expect(neighbourCell(neighbourCell(cell, direction), opposite[direction])).toEqual(cell);
      }
    }
  });

  it("stays in the last cell at the edge of the globe", () => {
    const corner = snapToCell(90, 180);
    const opposite = snapToCell(-90, -180);

    expect(neighbourCell(corner, "north")).toEqual(corner);
    expect(neighbourCell(corner, "east")).toEqual(corner);
    expect(neighbourCell(opposite, "south")).toEqual(opposite);
    expect(neighbourCell(opposite, "west")).toEqual(opposite);
  });
});

describe("distanceKm", () => {
  it("is zero for the same point and symmetric", () => {
    const a = { latitude: 50.45, longitude: 30.52 };
    const b = { latitude: 49.84, longitude: 24.03 };

    expect(distanceKm(a, a)).toBe(0);
    expect(distanceKm(a, b)).toBe(distanceKm(b, a));
  });

  it("gives about 470 km between Kyiv and Lviv", () => {
    const km = distanceKm(
      { latitude: 50.45, longitude: 30.524 },
      { latitude: 49.842, longitude: 24.032 },
    );

    expect(km).toBeGreaterThan(460);
    expect(km).toBeLessThan(480);
  });
});
