import { useFormikContext } from "formik";
import { uk } from "../../i18n/uk";
import FormField from "../FormField/FormField";
import { CONTACT_MAX, useFieldError, type ProfileFormValues } from "./profileValues";
import styles from "./ProfileForm.module.css";

const text = uk.profile.contact;

/**
 * The contact that a partner sees once an invitation between the two is accepted. It has its
 * own group because invitations cannot be sent or accepted without it; the notice about an
 * empty field is shown as text on the page, not only as a colour or a tooltip.
 */
const ContactFieldset = () => {
  const { getFieldProps, values } = useFormikContext<ProfileFormValues>();
  const contactError = useFieldError("contact");

  return (
    <fieldset className={styles.group}>
      <legend className={styles.legend}>{text.legend}</legend>
      {values.contact.trim() === "" && <p className={styles.notice}>{text.missing}</p>}
      <FormField
        {...getFieldProps("contact")}
        label={text.label}
        hint={text.hint(CONTACT_MAX)}
        autoComplete="off"
        error={contactError}
      />
    </fieldset>
  );
};

export default ContactFieldset;
