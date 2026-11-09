import { uk } from "../../i18n/uk";
import styles from "./Pagination.module.css";

interface PaginationProps {
  /** Where the user is, such as "Сторінка 2 з 5". */
  position: string;
  hasPrevious: boolean;
  hasNext: boolean;
  onPrevious: () => void;
  onNext: () => void;
}

/**
 * Previous and next buttons with the current position between them.
 *
 * A button that cannot be used is marked with aria-disabled instead of the disabled
 * attribute, so that it keeps keyboard focus when the user reaches the first or last page.
 */
const Pagination = ({ position, hasPrevious, hasNext, onPrevious, onNext }: PaginationProps) => (
  <nav className={styles.pagination} aria-label={uk.pagination.label}>
    <button
      className="button button-secondary"
      type="button"
      aria-disabled={hasPrevious ? undefined : true}
      onClick={() => {
        if (hasPrevious) onPrevious();
      }}
    >
      {uk.pagination.previous}
    </button>
    <span className={styles.position}>{position}</span>
    <button
      className="button button-secondary"
      type="button"
      aria-disabled={hasNext ? undefined : true}
      onClick={() => {
        if (hasNext) onNext();
      }}
    >
      {uk.pagination.next}
    </button>
  </nav>
);

export default Pagination;
