import { useEffect, useRef } from "react";
import { Link } from "react-router";
import { uk } from "../../i18n/uk";
import styles from "./ContactRequiredNotice.module.css";

/**
 * Tells the user that sending and accepting invitations needs a contact on the profile, and
 * links to the profile. It is announced as an alert and takes focus when it appears, because
 * the confirmation that had focus is replaced by it.
 */
const ContactRequiredNotice = () => {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    ref.current?.focus();
  }, []);

  return (
    <div className={styles.notice} role="alert" tabIndex={-1} ref={ref}>
      <p className={styles.message}>
        <strong>{uk.form.errorPrefix}</strong> {uk.contactRequired.message}
      </p>
      <Link className="button" to="/profile">
        {uk.contactRequired.link}
      </Link>
    </div>
  );
};

export default ContactRequiredNotice;
