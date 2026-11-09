/**
 * The privacy grid of the location, mirrored from the server (`app/domain/privacy.py`).
 *
 * The server stores only the centre of the grid cell that contains the point it receives, so
 * the form sends that centre and never the point the user clicked. These functions repeat the
 * server's arithmetic step by step (same steps, same floor, same clamping to the outermost
 * cells, same rounding of the centre to six decimals), so the rectangle drawn on the map is the
 * area that is really stored. The golden values in the tests were produced by the server code.
 */

/** Height of a cell in degrees of latitude: about 4.4 km. */
export const LAT_STEP = 0.04;
/** Width of a cell in degrees of longitude: about 4.3 km at 50 degrees north. */
export const LON_STEP = 0.06;

const MAX_LATITUDE = 90;
const MAX_LONGITUDE = 180;

export type Direction = "north" | "south" | "east" | "west";

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

function cellAt(latIndex: number, lonIndex: number): GridCell {
  return {
    latitude: round6((latIndex + 0.5) * LAT_STEP),
    longitude: round6((lonIndex + 0.5) * LON_STEP),
    south: round6(latIndex * LAT_STEP),
    north: round6((latIndex + 1) * LAT_STEP),
    west: round6(lonIndex * LON_STEP),
    east: round6((lonIndex + 1) * LON_STEP),
  };
}

/**
 * The grid cell that contains a point, exactly as the server computes it.
 *
 * Values outside the globe are clamped to the outermost cells, as on the server.
 *
 * @param latitude Latitude in degrees.
 * @param longitude Longitude in degrees.
 * @throws RangeError If a value is not a finite number (the message never contains the value).
 */
export function snapToCell(latitude: number, longitude: number): GridCell {
  if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) {
    throw new RangeError("coordinates must be finite numbers");
  }
  return cellAt(
    cellIndex(latitude, LAT_STEP, MAX_LATITUDE),
    cellIndex(longitude, LON_STEP, MAX_LONGITUDE),
  );
}

/** The neighbouring cell in a direction; at the edge of the globe the cell stays where it is. */
export function neighbourCell(cell: GridCell, direction: Direction): GridCell {
  const latIndex = cellIndex(cell.latitude, LAT_STEP, MAX_LATITUDE);
  const lonIndex = cellIndex(cell.longitude, LON_STEP, MAX_LONGITUDE);
  const latCells = Math.round(MAX_LATITUDE / LAT_STEP);
  const lonCells = Math.round(MAX_LONGITUDE / LON_STEP);
  switch (direction) {
    case "north":
      return cellAt(Math.min(latCells - 1, latIndex + 1), lonIndex);
    case "south":
      return cellAt(Math.max(-latCells, latIndex - 1), lonIndex);
    case "east":
      return cellAt(latIndex, Math.min(lonCells - 1, lonIndex + 1));
    case "west":
      return cellAt(latIndex, Math.max(-lonCells, lonIndex - 1));
  }
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
