import { FieldArray, useFormikContext } from "formik";
import { useEffect, useRef, type ChangeEvent } from "react";
import type { CategoryCode, Taxonomy } from "../../api/types";
import { taxonomyLabel } from "../../i18n/taxonomy";
import { uk } from "../../i18n/uk";
import SelectField from "../SelectField/SelectField";
import styles from "./ProfileForm.module.css";
import {
  emptyCapabilityRow,
  equipmentFor,
  useFieldError,
  type ProfileFormValues,
} from "./profileValues";

interface CapabilitiesFieldsetProps {
  taxonomy: Taxonomy;
}

interface CapabilityRowFieldsProps {
  taxonomy: Taxonomy;
  index: number;
  onRemove: () => void;
}

const text = uk.profile.functional;

const CapabilityRowFields = ({ taxonomy, index, onRemove }: CapabilityRowFieldsProps) => {
  const { values, getFieldProps, setFieldValue } = useFormikContext<ProfileFormValues>();
  const categoryError = useFieldError(`capabilities.${index}.category`);
  const levelError = useFieldError(`capabilities.${index}.level`);
  const equipmentError = useFieldError(`capabilities.${index}.equipment`);
  const row = values.capabilities[index];
  const taken = new Set(values.capabilities.map((item) => item.category));

  const categoryOptions = taxonomy.categories
    .filter((code) => code === row?.category || !taken.has(code))
    .map((code) => ({ value: code, label: taxonomyLabel(taxonomy.version, "categories", code) }));
  const levelOptions = taxonomy.capability_levels.map((level) => ({
    value: String(level),
    label: `${level}: ${taxonomyLabel(taxonomy.version, "capabilityLevels", String(level))}`,
  }));
  // Equipment is offered only if it can be attached to the chosen category
  const equipmentOptions = equipmentFor(taxonomy, row?.category ?? "").map((code) => ({
    value: code,
    label: taxonomyLabel(taxonomy.version, "equipment", code),
  }));
  const categoryHint = row?.category
    ? taxonomyLabel(taxonomy.version, "categoryHints", row.category)
    : undefined;

  const categoryProps = getFieldProps(`capabilities.${index}.category`);
  const onCategoryChange = (event: ChangeEvent<HTMLSelectElement>) => {
    categoryProps.onChange(event);
    const next = event.target.value as CategoryCode | "";
    const current = row?.equipment;
    if (current && !equipmentFor(taxonomy, next).includes(current)) {
      void setFieldValue(`capabilities.${index}.equipment`, "");
    }
  };

  return (
    <fieldset className={styles.row}>
      <legend className={styles.rowLegend}>{text.row(index + 1)}</legend>
      <SelectField
        {...categoryProps}
        onChange={onCategoryChange}
        label={text.category}
        options={categoryOptions}
        placeholder={uk.profile.choose}
        hint={categoryHint}
        required
        error={categoryError}
      />
      <SelectField
        {...getFieldProps(`capabilities.${index}.level`)}
        label={text.level}
        options={levelOptions}
        placeholder={uk.profile.choose}
        required
        error={levelError}
      />
      {equipmentOptions.length > 0 && (
        <SelectField
          {...getFieldProps(`capabilities.${index}.equipment`)}
          label={text.equipment}
          options={equipmentOptions}
          placeholder={text.equipmentNone}
          error={equipmentError}
        />
      )}
      <button className="button button-secondary" type="button" onClick={onRemove}>
        {text.remove(index + 1)}
      </button>
    </fieldset>
  );
};

/**
 * Editor of the declared capabilities: category, level and equipment per row.
 * It is rendered only while the consent for functional data is given.
 */
const CapabilitiesFieldset = ({ taxonomy }: CapabilitiesFieldsetProps) => {
  const { values } = useFormikContext<ProfileFormValues>();
  const addRef = useRef<HTMLButtonElement>(null);
  const groupRef = useRef<HTMLFieldSetElement>(null);
  const focusAfter = useRef<"new-row" | "add-button" | null>(null);
  const count = values.capabilities.length;
  const allAdded = count >= taxonomy.categories.length;

  useEffect(() => {
    if (focusAfter.current === "new-row") {
      groupRef.current
        ?.querySelector<HTMLElement>(`select[name="capabilities.${count - 1}.category"]`)
        ?.focus();
    } else if (focusAfter.current === "add-button") {
      addRef.current?.focus();
    }
    focusAfter.current = null;
  }, [count]);

  return (
    <fieldset className={styles.group} ref={groupRef}>
      <legend className={styles.legend}>{text.capabilitiesLegend}</legend>
      <p className={styles.note}>{text.capabilitiesHint}</p>
      <FieldArray name="capabilities">
        {(helpers) => (
          <>
            {values.capabilities.map((_row, index) => (
              <CapabilityRowFields
                key={index}
                taxonomy={taxonomy}
                index={index}
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
              aria-disabled={allAdded ? true : undefined}
              onClick={() => {
                if (allAdded) return;
                focusAfter.current = "new-row";
                helpers.push({ ...emptyCapabilityRow });
              }}
            >
              {text.add}
            </button>
            {allAdded && <p className={styles.note}>{text.allCategoriesAdded}</p>}
          </>
        )}
      </FieldArray>
    </fieldset>
  );
};

export default CapabilitiesFieldset;
