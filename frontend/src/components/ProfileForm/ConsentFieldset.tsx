import { useFormikContext } from "formik";
import { uk } from "../../i18n/uk";
import CheckboxField from "../CheckboxField/CheckboxField";
import type { ProfileFormValues } from "./profileValues";
import styles from "./ProfileForm.module.css";

const text = uk.profile.functional;

/**
 * Consent for functional data with a plain statement of what is collected and who sees what.
 * The wording sits next to the checkbox, so the consent is given with the terms in view.
 */
const ConsentFieldset = () => {
  const { getFieldProps } = useFormikContext<ProfileFormValues>();

  return (
    <fieldset className={styles.group}>
      <legend className={styles.legend}>{text.legend}</legend>
      <p className={styles.note}>{text.consentIntro}</p>
      <ul className={styles.list}>
        <li>{text.collected}</li>
        <li>{text.visibility}</li>
        <li>{text.withdraw}</li>
        <li>{text.without}</li>
      </ul>
      <CheckboxField
        {...getFieldProps({ name: "functional_data_consent", type: "checkbox" })}
        label={text.consent}
      />
    </fieldset>
  );
};

export default ConsentFieldset;
