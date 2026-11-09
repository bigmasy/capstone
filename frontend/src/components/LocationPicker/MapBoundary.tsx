import { Component, type ReactNode } from "react";
import { uk } from "../../i18n/uk";

interface MapBoundaryProps {
  children: ReactNode;
}

interface MapBoundaryState {
  failed: boolean;
}

/**
 * Keeps a failure of the lazily loaded map (a chunk that cannot be fetched, a browser without
 * the features the library needs) away from the rest of the form: the list of places and the
 * direction buttons still work, so the message points to them.
 */
class MapBoundary extends Component<MapBoundaryProps, MapBoundaryState> {
  state: MapBoundaryState = { failed: false };

  static getDerivedStateFromError(): MapBoundaryState {
    return { failed: true };
  }

  render() {
    if (!this.state.failed) return this.props.children;
    return (
      <p role="alert">
        <strong>{uk.form.errorPrefix}</strong> {uk.profile.location.mapFailed}
      </p>
    );
  }
}

export default MapBoundary;
