import { lazy, Suspense, useId, useState } from "react";
import type { AreaPrecision } from "../../api/types";
import { placesInOrder, findPlace } from "../../content/gazetteer";
import { isCoarser, snapToCell } from "../../geo/gridCell";
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
/** The choices in the order they are offered: from the coarsest area to the finest. */
const PRECISION_CHOICES: readonly AreaPrecision[] = ["place", "4km", "2km", "1km"];

type GeolocationState = "idle" | "pending" | "located" | "denied" | "unavailable";

interface LocationPickerProps {
  /** The chosen area as the centre of its grid cell, or null. */
  value: LocationValue | null;
  /** Receives the centre of the chosen cell, or null; an exact point never leaves this component. */
  onChange: (value: LocationValue | null) => void;
  /** How coarse the stored area is; the owner's choice. */
  precision: AreaPrecision;
  /** Receives the new choice of area size. */
  onPrecisionChange: (precision: AreaPrecision) => void;
  /** Error text for the list of places, which is the first control of the picker. */
  error?: string;
  /** True for an existing profile: leaving the area unchosen keeps the stored one. */
  optional?: boolean;
}

function centreOf(latitude: number, longitude: number, precision: AreaPrecision): LocationValue {
  const cell = snapToCell(latitude, longitude, precision);
  return { latitude: cell.latitude, longitude: cell.longitude };
}

/**
 * Chooses the training area without typing coordinates.
 *
 * First the size of the area: only a city or a district, or a square of about 4, 2 or 1 km.
 * With "city or district" the list of places is the whole control. With a square the area can
 * also come from the browser's position or from the map. Whatever the way in, the point is
 * snapped to its grid cell at once, so only the cell is kept in the form and sent, and the
 * rectangle of that cell is what the map shows. The map is loaded only after the user asks for
 * it or picks a place.
 */
const LocationPicker = ({
  value,
  onChange,
  precision,
  onPrecisionChange,
  error,
  optional = false,
}: LocationPickerProps) => {
  const mapRegionId = useId();
  const precisionName = useId();
  const [mapShown, setMapShown] = useState(false);
  const [recenterKey, setRecenterKey] = useState(0);
  const [picked, setPicked] = useState<({ id: string } & LocationValue) | null>(null);
  const [geolocation, setGeolocation] = useState<GeolocationState>("idle");
  const canLocate = "geolocation" in navigator;
  const placeOnly = precision === "place";

  // The list shows a place only while the chosen cell is the one that place produced
  const selectedId =
    picked && value && picked.latitude === value.latitude && picked.longitude === value.longitude
      ? picked.id
      : "";

  /** Takes a point from the map or the browser; the exact value is dropped right here. */
  const chooseFromPoint = (latitude: number, longitude: number, recenter: boolean) => {
    onChange(centreOf(latitude, longitude, precision));
    setPicked(null);
    if (recenter) setRecenterKey((key) => key + 1);
  };

  const choosePlace = (id: string) => {
    const place = findPlace(id);
    if (!place) {
      onChange(null);
      return;
    }
    const centre = centreOf(place.latitude, place.longitude, precision);
    onChange(centre);
    setPicked({ id, ...centre });
    if (!placeOnly) {
      // Picking a place is a request to see it
      setMapShown(true);
      setRecenterKey((key) => key + 1);
    }
  };

  const choosePrecision = (next: AreaPrecision) => {
    if (next === precision) return;
    onPrecisionChange(next);
    const place = picked ? findPlace(picked.id) : undefined;
    if (place) {
      // A place from the list is a known point: it is simply snapped again
      const centre = centreOf(place.latitude, place.longitude, next);
      onChange(centre);
      setPicked({ id: place.id, ...centre });
    } else if (value && isCoarser(next, precision)) {
      // The grids are nested, so the chosen cell lies inside exactly one larger cell
      onChange(centreOf(value.latitude, value.longitude, next));
    } else if (value) {
      // A smaller cell cannot be derived from a larger one: the place has to be chosen again
      onChange(null);
    }
    setRecenterKey((key) => key + 1);
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

  return (
    <div className={styles.picker}>
      <fieldset className={styles.sizes}>
        <legend>{text.precisionLegend}</legend>
        <p className={styles.note}>{text.precisionHint}</p>
        <div className={styles.sizeList}>
          {PRECISION_CHOICES.map((choice) => (
            <label key={choice} className={styles.size} htmlFor={`${precisionName}-${choice}`}>
              <input
                id={`${precisionName}-${choice}`}
                type="radio"
                name={precisionName}
                value={choice}
                checked={precision === choice}
                onChange={() => choosePrecision(choice)}
              />
              <span className={styles.sizeName}>{text.precision[choice].name}</span>
              <span className={styles.sizeNote}>{text.precision[choice].note}</span>
            </label>
          ))}
        </div>
      </fieldset>

      <SelectField
        name="place"
        label={text.place}
        hint={
          optional
            ? `${placeOnly ? text.placeOnlyHint : text.placeHint} ${text.optionalHint}`
            : placeOnly
              ? text.placeOnlyHint
              : text.placeHint
        }
        options={PLACE_OPTIONS}
        placeholder={text.placePlaceholder}
        value={selectedId}
        onChange={(event) => choosePlace(event.target.value)}
        required={!optional}
        error={error}
      />

      {!placeOnly && canLocate && (
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

      {!placeOnly && (
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
            <p className={styles.note}>{text.mapNote}</p>
          </div>
          <div id={mapRegionId}>
            {mapShown && (
              <>
                <p className={styles.note}>{text.mapPointerHint}</p>
                <MapBoundary>
                  <Suspense fallback={<Loader label={text.mapLoading} />}>
                    <LocationMap
                      value={value}
                      precision={precision}
                      onPick={(latitude, longitude) => chooseFromPoint(latitude, longitude, false)}
                      recenterKey={recenterKey}
                    />
                  </Suspense>
                </MapBoundary>
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
      )}

      {/* Always in the DOM so that the choice is announced when it changes */}
      <p role="status" className={styles.chosen}>
        {value ? text.chosen[precision] : ""}
      </p>

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
