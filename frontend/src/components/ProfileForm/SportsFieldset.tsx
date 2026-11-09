import { FieldArray, useFormikContext } from "formik";
import { useEffect, useId, useRef } from "react";
import type { Taxonomy } from "../../api/types";
import { taxonomyLabel } from "../../i18n/taxonomy";
import { uk } from "../../i18n/uk";
import SelectField from "../SelectField/SelectField";
import styles from "./ProfileForm.module.css";
import { emptySportRow, MAX_SPORTS, useFieldError, type ProfileFormValues } from "./profileValues";

interface SportsFieldsetProps {
  taxonomy: Taxonomy;
}

interface SportRowFieldsProps {
  taxonomy: Taxonomy;
  index: number;
  canRemove: boolean;
  onRemove: () => void;
}

const text = uk.profile.sports;

const SportRowFields = ({ taxonomy, index, canRemove, onRemove }: SportRowFieldsProps) => {
  const { values, getFieldProps } = useFormikContext<ProfileFormValues>();
  const sportError = useFieldError(`sports.${index}.sport`);
  const skillError = useFieldError(`sports.${index}.skill`);
  const lastRowId = useId();
  const own = values.sports[index]?.sport;
  const taken = new Set(values.sports.map((row) => row.sport));

  // A sport chosen in another row is not offered again; the row's own choice stays
  const sportOptions = taxonomy.sports
    .filter((code) => code === own || !taken.has(code))
    .map((code) => ({ value: code, label: taxonomyLabel(taxonomy.version, "sports", code) }));
  const skillOptions = taxonomy.skills.map((code) => ({
    value: code,
    label: taxonomyLabel(taxonomy.version, "skills", code),
  }));

  return (
    <fieldset className={styles.row}>
      <legend className={styles.rowLegend}>{text.row(index + 1)}</legend>
      <SelectField
        {...getFieldProps(`sports.${index}.sport`)}
        label={text.sport}
        options={sportOptions}
        placeholder={uk.profile.choose}
        required
        error={sportError}
      />
      <SelectField
        {...getFieldProps(`sports.${index}.skill`)}
        label={text.skill}
        options={skillOptions}
        required
        error={skillError}
      />
      <button
        className="button button-secondary"
        type="button"
        aria-disabled={canRemove ? undefined : true}
        aria-describedby={canRemove ? undefined : lastRowId}
        onClick={() => {
          if (canRemove) onRemove();
        }}
      >
        {text.remove(index + 1)}
      </button>
      {!canRemove && (
        <span className="visually-hidden" id={lastRowId}>
          {text.lastRow}
        </span>
      )}
    </fieldset>
  );
};

/** Editable list of sports with a skill level each: 1 to 10 rows, added and removed by button. */
const SportsFieldset = ({ taxonomy }: SportsFieldsetProps) => {
  const { values } = useFormikContext<ProfileFormValues>();
  const addRef = useRef<HTMLButtonElement>(null);
  const groupRef = useRef<HTMLFieldSetElement>(null);
  // What the next render has to do with focus: a new row gets it, a removed row hands it to "add"
  const focusAfter = useRef<"new-row" | "add-button" | null>(null);
  const count = values.sports.length;
  const atLimit = count >= MAX_SPORTS;

  useEffect(() => {
    if (focusAfter.current === "new-row") {
      groupRef.current
        ?.querySelector<HTMLElement>(`select[name="sports.${count - 1}.sport"]`)
        ?.focus();
    } else if (focusAfter.current === "add-button") {
      addRef.current?.focus();
    }
    focusAfter.current = null;
  }, [count]);

  return (
    <fieldset className={styles.group} ref={groupRef}>
      <legend className={styles.legend}>{text.legend}</legend>
      <p className={styles.note}>{text.hint}</p>
      <FieldArray name="sports">
        {(helpers) => (
          <>
            {values.sports.map((_row, index) => (
              <SportRowFields
                // Rows have no identity of their own; the position is the key
                key={index}
                taxonomy={taxonomy}
                index={index}
                canRemove={count > 1}
                onRemove={() => {
                  focusAfter.current = "add-button";
                  helpers.remove(index);
                }}
              />
            ))}
            <button
              className="button button-secondary"
              type="button"
              ref={addRef}
              aria-disabled={atLimit ? true : undefined}
              onClick={() => {
                if (atLimit) return;
                focusAfter.current = "new-row";
                helpers.push({ ...emptySportRow });
              }}
            >
              {text.add}
            </button>
            {atLimit && <p className={styles.note}>{text.limitReached}</p>}
          </>
        )}
      </FieldArray>
    </fieldset>
  );
};

export default SportsFieldset;
