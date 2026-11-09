import { lazy, Suspense, useId, useState, type KeyboardEvent } from "react";
import { nearestCity, placesInOrder, findPlace } from "../../content/gazetteer";
import { neighbourCell, snapToCell, type Direction, type GridCell } from "../../geo/gridCell";
import { uk } from "../../i18n/uk";
import Loader from "../Loader/Loader";
import type { LocationValue } from "../ProfileForm/profileValues";
import SelectField from "../SelectField/SelectField";
import styles from "./LocationPicker.module.css";
import MapBoundary from "./MapBoundary";

// A separate chunk: neither the map library nor any tile is requested before it is needed
const LocationMap = lazy(() => import("./LocationMap"));

const text = uk.profile.location;
const PLACE_OPTIONS = placesInOrder().map((place) => ({ value: place.id, label: place.name }));

type GeolocationState = "idle" | "pending" | "located" | "denied" | "unavailable";

const ARROW_DIRECTIONS: Record<string, Direction> = {
  ArrowUp: "north",
  ArrowDown: "south",
  ArrowRight: "east",
  ArrowLeft: "west",
};

interface LocationPickerProps {
  /** The chosen area as the centre of its grid cell, or null. */
  value: LocationValue | null;
  /** Receives the centre of the chosen cell, or null; an exact point never leaves this component. */
  onChange: (value: LocationValue | null) => void;
  /** Error text for the list of places, which is the first control of the picker. */
  error?: string;
  /** True for an existing profile: leaving the area unchosen keeps the stored one. */
  optional?: boolean;
}

function centreOf(cell: GridCell): LocationValue {
  return { latitude: cell.latitude, longitude: cell.longitude };
}

/** A latitude or longitude edge such as "50.44° пн. ш."; edges are multiples of 0.01. */
function edge(value: number, positive: string, negative: string): string {
  return `${Math.abs(value).toFixed(2)}° ${value < 0 ? negative : positive}`;
}

/**
 * Chooses the training area without typing coordinates.
 *
 * Three ways in, all ending in the same step: the point is snapped to its grid cell at once,
 * so only the cell is kept in the form and sent, and the rectangle of that cell is what the map
 * shows. The ways are the list of places (a static gazetteer, no search through a third party),
 * the browser's position, and the map; direction buttons move the cell by one step, which is the
 * way to adjust it without a pointer. The map is loaded only after the user asks for it or picks
 * a place.
 */
const LocationPicker = ({ value, onChange, error, optional = false }: LocationPickerProps) => {
  const mapRegionId = useId();
  const descriptionId = useId();
  const [mapShown, setMapShown] = useState(false);
  const [recenterKey, setRecenterKey] = useState(0);
  const [picked, setPicked] = useState<{ id: string } & LocationValue | null>(null);
  const [geolocation, setGeolocation] = useState<GeolocationState>("idle");
  const canLocate = "geolocation" in navigator;

  const cell = value ? snapToCell(value.latitude, value.longitude) : null;
  // The list shows a place only while the chosen cell is the one that place produced
  const selectedId =
    picked && value && picked.latitude === value.latitude && picked.longitude === value.longitude
      ? picked.id
      : "";

  /** Takes a point from the map or the browser; the exact value is dropped right here. */
  const chooseFromPoint = (latitude: number, longitude: number, recenter: boolean) => {
    onChange(centreOf(snapToCell(latitude, longitude)));
    setPicked(null);
    if (recenter) setRecenterKey((key) => key + 1);
  };

  const choosePlace = (id: string) => {
    const place = findPlace(id);
    if (!place) {
      onChange(null);
      return;
    }
    const centre = centreOf(snapToCell(place.latitude, place.longitude));
    onChange(centre);
    setPicked({ id, ...centre });
    // Picking a place is a request to see it
    setMapShown(true);
    setRecenterKey((key) => key + 1);
  };

  const nudge = (direction: Direction) => {
    if (!cell) return;
    onChange(centreOf(neighbourCell(cell, direction)));
    setPicked(null);
    setRecenterKey((key) => key + 1);
  };

  const onNudgeKey = (event: KeyboardEvent<HTMLButtonElement>) => {
    const direction = ARROW_DIRECTIONS[event.key];
    if (direction === undefined) return;
    event.preventDefault();
    nudge(direction);
  };

  const locate = () => {
    if (geolocation === "pending") return;
    setGeolocation("pending");
    navigator.geolocation.getCurrentPosition(
      ({ coords }) => {
        chooseFromPoint(coords.latitude, coords.longitude, true);
        setGeolocation("located");
      },
      (failure) => {
        setGeolocation(failure.code === failure.PERMISSION_DENIED ? "denied" : "unavailable");
      },
      { enableHighAccuracy: false, maximumAge: 0, timeout: 10000 },
    );
  };

  const geolocationStatus =
    geolocation === "pending"
      ? text.locating
      : geolocation === "located"
        ? text.located
        : geolocation === "denied"
          ? text.denied
          : geolocation === "unavailable"
            ? text.unavailable
            : "";

  const nearest = cell ? nearestCity(cell) : null;
  const description = cell
    ? `${text.area(
        edge(cell.south, text.northLatitude, text.southLatitude),
        edge(cell.north, text.northLatitude, text.southLatitude),
        edge(cell.west, text.eastLongitude, text.westLongitude),
        edge(cell.east, text.eastLongitude, text.westLongitude),
      )} ${nearest ? text.nearest(nearest.place.name, Math.round(nearest.distanceKm)) : ""}`.trim()
    : text.areaNone;

  const directions: { direction: Direction; label: string; className: string }[] = [
    { direction: "north", label: text.north, className: styles.north ?? "" },
    { direction: "west", label: text.west, className: styles.west ?? "" },
    { direction: "east", label: text.east, className: styles.east ?? "" },
    { direction: "south", label: text.south, className: styles.south ?? "" },
  ];

  return (
    <div className={styles.picker}>
      <SelectField
        name="place"
        label={text.place}
        hint={optional ? `${text.placeHint} ${text.optionalHint}` : text.placeHint}
        options={PLACE_OPTIONS}
        placeholder={text.placePlaceholder}
        value={selectedId}
        onChange={(event) => choosePlace(event.target.value)}
        required={!optional}
        error={error}
      />

      {canLocate && (
        <div className={styles.row}>
          <button
            className="button button-secondary"
            type="button"
            aria-disabled={geolocation === "pending" ? true : undefined}
            onClick={locate}
          >
            {text.useMyLocation}
          </button>
          <p className={styles.note}>{text.geolocationNote}</p>
          {/* Always in the DOM so that a result added later is announced */}
          <p role="status" className={styles.note}>
            {geolocationStatus}
          </p>
        </div>
      )}

      <div className={styles.mapFrame}>
        <div className={styles.row}>
          <button
            className="button button-secondary"
            type="button"
            aria-expanded={mapShown}
            aria-controls={mapRegionId}
            onClick={() => setMapShown((shown) => !shown)}
          >
            {mapShown ? text.hideMap : text.showMap}
          </button>
          <p className={styles.note}>{text.mapOptional}</p>
        </div>
        <p className={styles.note}>{text.mapNote}</p>
        <div id={mapRegionId}>
          {mapShown && (
            <>
              <p className={styles.note}>{text.mapPointerHint}</p>
              <MapBoundary>
                <Suspense fallback={<Loader label={text.mapLoading} />}>
                  <LocationMap
                    value={value}
                    onPick={(latitude, longitude) => chooseFromPoint(latitude, longitude, false)}
                    recenterKey={recenterKey}
                    describedBy={descriptionId}
                  />
                </Suspense>
              </MapBoundary>
              <p className={styles.note}>{text.mapKeyboardHint}</p>
              <p className={styles.note}>
                <a
                  href="https://www.openstreetmap.org/copyright"
                  target="_blank"
                  rel="noopener noreferrer"
                  referrerPolicy="no-referrer"
                  // The wording of the credit is the English one the map provider asks for
                  lang="en"
                >
                  {text.attribution}
                </a>
              </p>
            </>
          )}
        </div>
      </div>

      {cell && (
        <fieldset className={styles.compass}>
          <legend>{text.nudgeLegend}</legend>
          {directions.map(({ direction, label, className }) => (
            <button
              key={direction}
              className={`button button-secondary ${className}`}
              type="button"
              onClick={() => nudge(direction)}
              onKeyDown={onNudgeKey}
            >
              {label}
            </button>
          ))}
        </fieldset>
      )}
      {cell && <p className={styles.note}>{text.nudgeHint}</p>}

      <div className={styles.preview}>
        <p id={descriptionId} role="status">
          {description}
        </p>
        <p className={styles.previewNote}>{text.previewNote}</p>
      </div>

      {value && (
        <div className={styles.row}>
          <button className="button button-secondary" type="button" onClick={() => onChange(null)}>
            {text.clear}
          </button>
        </div>
      )}
    </div>
  );
};

export default LocationPicker;
