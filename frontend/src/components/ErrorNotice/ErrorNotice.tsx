import { uk } from "../../i18n/uk";
import styles from "./ErrorNotice.module.css";

interface ErrorNoticeProps {
  message: string;
  /** When given, a button that asks for the data again is shown below the message. */
  onRetry?: () => void;
  retryLabel?: string;
}

/** A failure announced as an alert with a text prefix, so it is not told by colour alone. */
const ErrorNotice = ({ message, onRetry, retryLabel }: ErrorNoticeProps) => (
  <div>
    <p className={styles.error} role="alert">
      <strong>{uk.form.errorPrefix}</strong> {message}
    </p>
    {onRetry && (
      <button className="button" type="button" onClick={onRetry}>
        {retryLabel ?? uk.profile.retry}
      </button>
    )}
  </div>
);

export default ErrorNotice;
