import { useId, type ComponentProps } from "react";
import { uk } from "../../i18n/uk";
import styles from "./FormField.module.css";

interface FormFieldProps
  extends Omit<ComponentProps<"input">, "id" | "aria-invalid" | "aria-describedby"> {
  label: string;
  name: string;
  /** Help text linked to the input with aria-describedby. */
  hint?: string;
  /** Error message; when set the input is marked invalid and linked to the message. */
  error?: string;
}

/**
 * Label, input, hint and error message wired together for assistive technology.
 * The error text starts with a visible prefix, so the state never relies on colour alone.
 */
const FormField = ({ label, name, hint, error, required, ...inputProps }: FormFieldProps) => {
  const id = useId();
  const hintId = `${id}-hint`;
  const errorId = `${id}-error`;
  const describedBy = [hint ? hintId : null, error ? errorId : null].filter(Boolean).join(" ");

  return (
    <div className={styles.field}>
      <label className={styles.label} htmlFor={id}>
        {label}
        {required && <span className={styles.required}> ({uk.form.required})</span>}
      </label>
      {hint && (
        <p className={styles.hint} id={hintId}>
          {hint}
        </p>
      )}
      <input
        {...inputProps}
        className={`${styles.input} ${error ? styles.inputInvalid : ""}`}
        id={id}
        name={name}
        aria-required={required || undefined}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy || undefined}
      />
      {/* The polite live region is always in the DOM so that a message added on blur is announced */}
      <p className={styles.error} id={errorId} aria-live="polite">
        {error && (
          <>
            <strong>{uk.form.errorPrefix}</strong> {error}
          </>
        )}
      </p>
    </div>
  );
};

export default FormField;
