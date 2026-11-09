import { uk } from "../../i18n/uk";
import styles from "./Loader.module.css";

interface LoaderProps {
  /** Accessible text announced to screen readers; defaults to a generic loading message. */
  label?: string;
}

/** Spinner with a text alternative; the animation is disabled by prefers-reduced-motion. */
const Loader = ({ label = uk.a11y.loading }: LoaderProps) => (
  <div className={styles.loader} role="status">
    <span className={styles.spinner} aria-hidden="true" />
    <span>{label}</span>
  </div>
);

export default Loader;
