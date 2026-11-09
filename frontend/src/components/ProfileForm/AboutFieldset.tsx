import { useFormikContext } from "formik";
import type { Taxonomy } from "../../api/types";
import { taxonomyLabel } from "../../i18n/taxonomy";
import { uk } from "../../i18n/uk";
import FormField from "../FormField/FormField";
import SelectField from "../SelectField/SelectField";
import { useFieldError, type ProfileFormValues } from "./profileValues";
import styles from "./ProfileForm.module.css";

interface AboutFieldsetProps {
  taxonomy: Taxonomy;
}

const text = uk.profile.about;

/** Display name, district and usual intensity. */
const AboutFieldset = ({ taxonomy }: AboutFieldsetProps) => {
  const { getFieldProps } = useFormikContext<ProfileFormValues>();
  const displayNameError = useFieldError("display_name");
  const districtError = useFieldError("district_code");
  const intensityError = useFieldError("intensity");

  return (
    <fieldset className={styles.group}>
      <legend className={styles.legend}>{text.legend}</legend>
      <FormField
        {...getFieldProps("display_name")}
        label={text.displayName}
        hint={text.displayNameHint}
        autoComplete="nickname"
        required
        error={displayNameError}
      />
      <SelectField
        {...getFieldProps("district_code")}
        label={text.district}
        hint={text.districtHint}
        options={taxonomy.districts.map((code) => ({
          value: code,
          label: taxonomyLabel(taxonomy.version, "districts", code),
        }))}
        placeholder={text.districtNone}
        error={districtError}
      />
      <SelectField
        {...getFieldProps("intensity")}
        label={text.intensity}
        hint={text.intensityHint}
        options={taxonomy.intensities.map((level) => ({
          value: String(level),
          label: `${level}: ${taxonomyLabel(taxonomy.version, "intensities", String(level))}`,
        }))}
        placeholder={uk.profile.choose}
        required
        error={intensityError}
      />
    </fieldset>
  );
};

export default AboutFieldset;
