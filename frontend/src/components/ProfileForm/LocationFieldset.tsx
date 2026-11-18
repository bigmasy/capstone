import { useFormikContext } from "formik";
import { uk } from "../../i18n/uk";
import LocationPicker from "../LocationPicker/LocationPicker";
import styles from "./ProfileForm.module.css";
import type { AreaPrecision } from "../../api/types";
import { useFieldError, type LocationValue, type ProfileFormValues } from "./profileValues";

interface LocationFieldsetProps {
  /** Sentence about the stored area of an existing profile; absent for a new one. */
  storedArea?: string;
  /** True for an existing profile: no new area needs to be chosen and the stored one is kept. */
  optional?: boolean;
}

const text = uk.profile.location;

/**
 * The area the user trains around and how coarse it is. Both are chosen with the location
 * picker; the page says plainly that only the rounded area is stored, and the picker draws it.
 */
const LocationFieldset = ({ storedArea, optional = false }: LocationFieldsetProps) => {
  const { values, setFieldValue, setFieldTouched } = useFormikContext<ProfileFormValues>();
  const locationError = useFieldError("location");

  const change = (next: LocationValue | null) => {
    void setFieldValue("location", next);
    void setFieldTouched("location", true, false);
  };

  const changePrecision = (next: AreaPrecision) => {
    void setFieldValue("area_precision", next);
    void setFieldTouched("location", true, false);
  };

  return (
    <fieldset className={styles.group}>
      <legend className={styles.legend}>{text.legend}</legend>
      <p className={styles.note}>{text.explanation}</p>
      {storedArea && (
        <p className={styles.note}>
          <strong>{storedArea}</strong> {text.keepStored}
        </p>
      )}
      <LocationPicker
        value={values.location}
        onChange={change}
        precision={values.area_precision}
        onPrecisionChange={changePrecision}
        error={locationError}
        optional={optional}
      />
    </fieldset>
  );
};

export default LocationFieldset;
