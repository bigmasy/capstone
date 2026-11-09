import { useId, type ComponentProps } from "react";
import { uk } from "../../i18n/uk";
import styles from "./CheckboxField.module.css";

interface CheckboxFieldProps
  extends Omit<
    ComponentProps<"input">,
    "id" | "type" | "role" | "aria-invalid" | "aria-describedby"
  > {
  label: string;
  name: string;
  /** Explanation linked to the control with aria-describedby. */
  description?: string;
  error?: string;
  /** A switch is announced as "on/off"; the markup is still a native checkbox. */
  variant?: "checkbox" | "switch";
}

/** Native checkbox (optionally announced as a switch) with a label, a description and an error. */
const CheckboxField = ({
  label,
  name,
  description,
  error,
  variant = "checkbox",
  ...inputProps
}: CheckboxFieldProps) => {
  const id = useId();
  const descriptionId = `${id}-description`;
  const errorId = `${id}-error`;
  const describedBy = [description ? descriptionId : null, error ? errorId : null]
    .filter(Boolean)
    .join(" ");

  return (
    <div className={styles.field}>
      <div className={styles.row}>
        <input
          {...inputProps}
          className={styles.control}
          type="checkbox"
          role={variant === "switch" ? "switch" : undefined}
          id={id}
          name={name}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy || undefined}
        />
        <label className={styles.label} htmlFor={id}>
          {label}
        </label>
      </div>
      {description && (
        <p className={styles.description} id={descriptionId}>
          {description}
        </p>
      )}
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

export default CheckboxField;
