import { uk } from "../i18n/uk";

interface LocationMapStubProps {
  value: { latitude: number; longitude: number } | null;
  onPick: (latitude: number, longitude: number) => void;
  recenterKey: number;
  describedBy?: string;
}

/** The exact point that the stub reports as clicked; tests check that it is never sent. */
export const CLICKED_POINT = { latitude: 50.4517, longitude: 30.5249 } as const;

/**
 * Stands in for the Leaflet map in component tests: jsdom has no layout, so the real library is
 * covered by LocationMap.test.tsx with a stubbed Leaflet instead. The stub shows what the map
 * would be given and lets a test "click" a point.
 */
const LocationMapStub = ({ value, onPick, recenterKey, describedBy }: LocationMapStubProps) => (
  <div role="group" aria-label={uk.profile.location.mapLabel} aria-describedby={describedBy}>
    <button type="button" onClick={() => onPick(CLICKED_POINT.latitude, CLICKED_POINT.longitude)}>
      Клік по карті
    </button>
    <span data-testid="stub-recenter">{recenterKey}</span>
    <span data-testid="stub-value">{value ? `${value.latitude};${value.longitude}` : "none"}</span>
  </div>
);

export default LocationMapStub;
