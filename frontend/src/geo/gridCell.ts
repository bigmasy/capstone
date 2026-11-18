/**
 * The privacy grid of the location, mirrored from the server (`app/domain/privacy.py`).
 *
 * The server stores only the centre of the grid cell that contains the point it receives, so
 * the form sends that centre and never the point the user clicked. These functions repeat the
 * server's arithmetic step by step (same steps, same floor, same clamping to the outermost
 * cells, same rounding of the centre to six decimals), so the rectangle drawn on the map is the
 * area that is really stored. The golden values in the tests were produced by the server code.
 */
import type { AreaPrecision } from "../api/types";

/** Height of a cell of the default grid in degrees of latitude: about 4.4 km. */
export const LAT_STEP = 0.04;
/** Width of a cell of the default grid in degrees of longitude: about 4.3 km at 50 degrees north. */
export const LON_STEP = 0.06;

/** The grid of a profile that has not chosen one; the server uses the same default. */
export const DEFAULT_PRECISION: AreaPrecision = "4km";

/**
 * Steps of every grid in degrees: [latitude, longitude]. Each grid is twice as coarse as the
 * one before, so the grids are nested and an area can be made coarser without the original point.
 */
export const GRID_STEPS: Record<AreaPrecision, readonly [number, number]> = {
  "1km": [0.01, 0.015],
  "2km": [0.02, 0.03],
  "4km": [LAT_STEP, LON_STEP],
  place: [0.08, 0.12],
};

/** The grids from the finest to the coarsest. */
export const PRECISION_ORDER: readonly AreaPrecision[] = ["1km", "2km", "4km", "place"];

/** True when the cells of `a` are larger than the cells of `b`. */
export function isCoarser(a: AreaPrecision, b: AreaPrecision): boolean {
  return PRECISION_ORDER.indexOf(a) > PRECISION_ORDER.indexOf(b);
}

const MAX_LATITUDE = 90;
const MAX_LONGITUDE = 180;

/** A grid cell: its centre (what is stored and sent) and its edges (what is drawn). */
export interface GridCell {
  /** Latitude of the centre, rounded to six decimals. */
  latitude: number;
  /** Longitude of the centre, rounded to six decimals. */
  longitude: number;
  south: number;
  north: number;
  west: number;
  east: number;
}

/** Same rounding as the server's `round(value, 6)` for the values that occur here. */
function round6(value: number): number {
  // + 0 turns a negative zero into 0
  return Math.round(value * 1e6) / 1e6 + 0;
}

/**
 * Index of the cell of a value on one axis. The index is clamped to the outermost cells of the
 * range, so a point on the upper bound (90 or 180) or beyond it belongs to the last cell inside.
 */
function cellIndex(value: number, step: number, limit: number): number {
  const cells = Math.round(limit / step);
  return Math.max(-cells, Math.min(cells - 1, Math.floor(value / step)));
}

function cellAt(latIndex: number, lonIndex: number, latStep: number, lonStep: number): GridCell {
  return {
    latitude: round6((latIndex + 0.5) * latStep),
    longitude: round6((lonIndex + 0.5) * lonStep),
    south: round6(latIndex * latStep),
    north: round6((latIndex + 1) * latStep),
    west: round6(lonIndex * lonStep),
    east: round6((lonIndex + 1) * lonStep),
  };
}

/**
 * The grid cell that contains a point, exactly as the server computes it.
 *
 * Values outside the globe are clamped to the outermost cells, as on the server.
 *
 * @param latitude Latitude in degrees.
 * @param longitude Longitude in degrees.
 * @param precision Grid to use; the default grid has cells of about 4 km.
 * @throws RangeError If a value is not a finite number (the message never contains the value).
 */
export function snapToCell(
  latitude: number,
  longitude: number,
  precision: AreaPrecision = DEFAULT_PRECISION,
): GridCell {
  if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) {
    throw new RangeError("coordinates must be finite numbers");
  }
  const [latStep, lonStep] = GRID_STEPS[precision];
  return cellAt(
    cellIndex(latitude, latStep, MAX_LATITUDE),
    cellIndex(longitude, lonStep, MAX_LONGITUDE),
    latStep,
    lonStep,
  );
}

/** Great-circle distance in kilometres between two points, from the haversine formula. */
export function distanceKm(
  from: { latitude: number; longitude: number },
  to: { latitude: number; longitude: number },
): number {
  const earthRadiusKm = 6371;
  const rad = (degrees: number) => (degrees * Math.PI) / 180;
  const dPhi = rad(to.latitude - from.latitude);
  const dLambda = rad(to.longitude - from.longitude);
  const h =
    Math.sin(dPhi / 2) ** 2 +
    Math.cos(rad(from.latitude)) * Math.cos(rad(to.latitude)) * Math.sin(dLambda / 2) ** 2;
  return 2 * earthRadiusKm * Math.asin(Math.sqrt(Math.min(1, h)));
}
