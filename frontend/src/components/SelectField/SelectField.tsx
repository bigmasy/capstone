import { useId, type ComponentProps } from "react";
import { uk } from "../../i18n/uk";
import styles from "../FormField/FormField.module.css";

export interface SelectOption {
  value: string;
  label: string;
}

interface SelectFieldProps
  extends Omit<ComponentProps<"select">, "id" | "children" | "aria-invalid" | "aria-describedby"> {
  label: string;
  name: string;
  options: readonly SelectOption[];
  /** Text of the empty first option; without it the field has no empty choice. */
  placeholder?: string;
  /** Help text linked to the select with aria-describedby. */
  hint?: string;
  /** Error message; when set the select is marked invalid and linked to the message. */
  error?: string;
}

/**
 * Label, native select, hint and error wired together for assistive technology.
 * It shares the look and the error pattern of FormField.
 */
const SelectField = ({
  label,
  name,
  options,
  placeholder,
  hint,
  error,
  required,
  ...selectProps
}: SelectFieldProps) => {
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
      <select
        {...selectProps}
        className={`${styles.input} ${error ? styles.inputInvalid : ""}`}
        id={id}
        name={name}
        aria-required={required || undefined}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy || undefined}
      >
        {placeholder !== undefined && <option value="">{placeholder}</option>}
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
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

export default SelectField;
