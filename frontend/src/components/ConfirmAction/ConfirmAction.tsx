import { useEffect, useId, useRef, useState } from "react";
import { uk } from "../../i18n/uk";
import Loader from "../Loader/Loader";
import styles from "./ConfirmAction.module.css";

interface ConfirmActionProps {
  /** Text of the button that opens the confirmation. */
  triggerLabel: string;
  /** Accessible name of that button when the visible text is not unique on the page. */
  triggerAriaLabel?: string;
  title: string;
  description: string;
  confirmLabel: string;
  /** Message shown in an alert when the action fails. */
  failureMessage: string;
  /** `danger` (default) marks an irreversible action; `neutral` is for an ordinary choice. */
  tone?: "danger" | "neutral";
  /** Runs the action; returns true on success. The caller handles what follows a success. */
  onConfirm: () => Promise<boolean>;
}

/**
 * A destructive action behind an explicit confirmation step, shown in place.
 *
 * Opening it moves focus to the question, and cancelling returns focus to the button that
 * opened it. While the request is pending the confirm button uses
 * aria-disabled so that it keeps focus and a second activation is ignored.
 */
const ConfirmAction = ({
  triggerLabel,
  triggerAriaLabel,
  title,
  description,
  confirmLabel,
  failureMessage,
  tone = "danger",
  onConfirm,
}: ConfirmActionProps) => {
  const titleId = useId();
  const [open, setOpen] = useState(false);
  const [pending, setPending] = useState(false);
  const [failed, setFailed] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const headingRef = useRef<HTMLHeadingElement>(null);
  const returnFocus = useRef(false);

  useEffect(() => {
    if (open) {
      headingRef.current?.focus();
    } else if (returnFocus.current) {
      returnFocus.current = false;
      triggerRef.current?.focus();
    }
  }, [open]);

  const cancel = () => {
    if (pending) return;
    returnFocus.current = true;
    setFailed(false);
    setOpen(false);
  };

  const confirm = async () => {
    if (pending) return;
    setPending(true);
    setFailed(false);
    try {
      const done = await onConfirm();
      if (!done) setFailed(true);
    } finally {
      setPending(false);
    }
  };

  if (!open) {
    return (
      <button
        className="button button-secondary"
        type="button"
        ref={triggerRef}
        aria-label={triggerAriaLabel}
        onClick={() => setOpen(true)}
      >
        {triggerLabel}
      </button>
    );
  }

  return (
    <div
      className={`${styles.panel} ${tone === "danger" ? styles.panelDanger : styles.panelNeutral}`}
      role="group"
      aria-labelledby={titleId}
    >
      <h3 className={styles.title} id={titleId} tabIndex={-1} ref={headingRef}>
        {title}
      </h3>
      <p>{description}</p>
      {failed && (
        <p className={styles.error} role="alert">
          <strong>{uk.form.errorPrefix}</strong> {failureMessage}
        </p>
      )}
      <div className={styles.actions}>
        <button className="button button-secondary" type="button" onClick={cancel}>
          {uk.profile.manage.cancel}
        </button>
        <button
          className={tone === "danger" ? `button ${styles.danger}` : "button"}
          type="button"
          aria-disabled={pending ? true : undefined}
          onClick={() => void confirm()}
        >
          {confirmLabel}
        </button>
        {pending && <Loader label={uk.profile.manage.working} />}
      </div>
    </div>
  );
};

export default ConfirmAction;
