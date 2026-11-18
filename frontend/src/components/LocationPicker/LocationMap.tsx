import {
  control,
  icon,
  map as createMap,
  marker as createMarker,
  rectangle as createRectangle,
  tileLayer,
  type LatLngBoundsLiteral,
  type LeafletMouseEvent,
  type Map as LeafletMap,
  type Marker,
  type Rectangle,
} from "leaflet";
import "leaflet/dist/leaflet.css";
import markerRetinaUrl from "leaflet/dist/images/marker-icon-2x.png";
import markerUrl from "leaflet/dist/images/marker-icon.png";
import markerShadowUrl from "leaflet/dist/images/marker-shadow.png";
import { useEffect, useRef } from "react";
import type { AreaPrecision } from "../../api/types";
import { snapToCell } from "../../geo/gridCell";
import { uk } from "../../i18n/uk";
import type { LocationValue } from "../ProfileForm/profileValues";
import styles from "./LocationPicker.module.css";

const text = uk.profile.location;

/** Raster tiles of OpenStreetMap; the one host named in the content security policy. */
const TILE_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
const TILE_MAX_ZOOM = 19;
/** Roughly the middle of Ukraine, shown before an area is chosen. */
const START_CENTRE: [number, number] = [48.6, 31.2];
const START_ZOOM = 6;
/** The zoom at which a cell of each grid fills a useful part of the map. */
const AREA_ZOOM: Record<AreaPrecision, number> = { "1km": 13, "2km": 12, "4km": 11, place: 10 };

interface LocationMapProps {
  /** The chosen area (cell centre), or null before one is chosen. */
  value: LocationValue | null;
  /** The grid of the area: it sets the size of the rectangle that is drawn. */
  precision: AreaPrecision;
  /** The user clicked the map or dropped the marker; the exact point is for the caller to snap. */
  onPick: (latitude: number, longitude: number) => void;
  /** Changes whenever the map should move to the chosen area (list, geolocation, direction). */
  recenterKey: number;
}

function boundsOf(value: LocationValue, precision: AreaPrecision): LatLngBoundsLiteral {
  const cell = snapToCell(value.latitude, value.longitude, precision);
  return [
    [cell.south, cell.west],
    [cell.north, cell.east],
  ];
}

function prefersReducedMotion(): boolean {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/**
 * An OpenStreetMap map with the privacy preview: a draggable marker at the centre of the chosen
 * grid cell and the rectangle of the cell, which is the area that is really stored.
 *
 * This is the only module that imports Leaflet, and it is loaded lazily, so neither the library
 * nor a single tile request exists until the user asks for the map.
 *
 * Keyboard: Leaflet makes the map container focusable (tabindex 0); with the focus on it the
 * arrow keys pan and "+" / "-" zoom. Leaflet handles no Tab key, so the map is not a keyboard
 * trap: Tab and Shift+Tab move on to the zoom buttons and the following controls. Setting the
 * point is not possible with a key press on the map; the list of places above the map does
 * that. The marker is therefore left out of the tab order.
 */
const LocationMap = ({ value, precision, onPick, recenterKey }: LocationMapProps) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<LeafletMap | null>(null);
  const markerRef = useRef<Marker | null>(null);
  const areaRef = useRef<Rectangle | null>(null);
  // Always the latest props, so the map handlers need not be re-registered on every render
  const latest = useRef({ value, onPick, precision });
  const shownKey = useRef(recenterKey);

  useEffect(() => {
    latest.current = { value, onPick, precision };
  });

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const reduced = prefersReducedMotion();
    const initial = latest.current.value;
    const map = createMap(container, {
      center: initial ? [initial.latitude, initial.longitude] : START_CENTRE,
      zoom: initial ? AREA_ZOOM[latest.current.precision] : START_ZOOM,
      keyboard: true,
      // Both controls are added below with Ukrainian texts: Leaflet's own are English, which a
      // screen reader would read out with the wrong pronunciation (WCAG 3.1.2)
      zoomControl: false,
      attributionControl: false,
      // Without animation under the reduced-motion preference
      zoomAnimation: !reduced,
      fadeAnimation: !reduced,
      markerZoomAnimation: !reduced,
    });
    control.zoom({ zoomInTitle: text.zoomIn, zoomOutTitle: text.zoomOut }).addTo(map);
    // Without the "Leaflet" prefix link, whose title is English; the credit of the map data stays
    control.attribution({ prefix: false }).addTo(map);
    tileLayer(TILE_URL, {
      maxZoom: TILE_MAX_ZOOM,
      attribution:
        '<span lang="en">&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap</a> contributors</span>',
    }).addTo(map);
    mapRef.current = map;

    map.on("click", (event: LeafletMouseEvent) => {
      const point = event.latlng.wrap();
      latest.current.onPick(point.lat, point.lng);
    });

    return () => {
      map.remove();
      mapRef.current = null;
      markerRef.current = null;
      areaRef.current = null;
    };
  }, []);

  // The privacy preview follows the chosen value
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    if (!value) {
      markerRef.current?.remove();
      areaRef.current?.remove();
      markerRef.current = null;
      areaRef.current = null;
      return;
    }

    const centre: [number, number] = [value.latitude, value.longitude];
    if (areaRef.current) {
      areaRef.current.setBounds(boundsOf(value, precision));
    } else {
      // The class sets stroke and fill from the colour tokens; it cannot be an SVG attribute
      areaRef.current = createRectangle(boundsOf(value, precision), {
        className: styles.area,
        interactive: false,
      }).addTo(map);
    }

    if (markerRef.current) {
      markerRef.current.setLatLng(centre);
    } else {
      const pin = createMarker(centre, {
        draggable: true,
        keyboard: false,
        alt: text.markerLabel,
        icon: icon({
          iconUrl: markerUrl,
          iconRetinaUrl: markerRetinaUrl,
          shadowUrl: markerShadowUrl,
          iconSize: [25, 41],
          iconAnchor: [12, 41],
          shadowSize: [41, 41],
        }),
      }).addTo(map);
      // While dragging, the rectangle shows the cell under the pointer
      pin.on("drag", () => {
        const point = pin.getLatLng().wrap();
        areaRef.current?.setBounds(
          boundsOf({ latitude: point.lat, longitude: point.lng }, latest.current.precision),
        );
      });
      pin.on("dragend", () => {
        const point = pin.getLatLng().wrap();
        latest.current.onPick(point.lat, point.lng);
      });
      markerRef.current = pin;
    }
  }, [value, precision]);

  // Move to the chosen area when the caller asks; the first render is handled at creation
  useEffect(() => {
    if (shownKey.current === recenterKey) return;
    shownKey.current = recenterKey;
    const map = mapRef.current;
    const current = latest.current.value;
    if (!map || !current) return;
    const zoom = AREA_ZOOM[latest.current.precision];
    map.setView([current.latitude, current.longitude], Math.max(map.getZoom(), zoom), {
      animate: !prefersReducedMotion(),
    });
  }, [recenterKey]);

  return (
    <div
      className={styles.map}
      ref={containerRef}
      role="group"
      aria-label={text.mapLabel}
    />
  );
};

export default LocationMap;
