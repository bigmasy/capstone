import { useFormikContext } from "formik";
import { uk } from "../../i18n/uk";
import CheckboxField from "../CheckboxField/CheckboxField";
import type { ProfileFormValues } from "./profileValues";
import styles from "./ProfileForm.module.css";

const text = uk.profile.visibility;

/** The switch that hides the profile from the feed of other users. */
const VisibilityFieldset = () => {
  const { getFieldProps } = useFormikContext<ProfileFormValues>();

  return (
    <fieldset className={styles.group}>
      <legend className={styles.legend}>{text.legend}</legend>
      <CheckboxField
        {...getFieldProps({ name: "is_visible", type: "checkbox" })}
        variant="switch"
        label={text.isVisible}
        description={text.isVisibleHint}
      />
    </fieldset>
  );
};

export default VisibilityFieldset;
