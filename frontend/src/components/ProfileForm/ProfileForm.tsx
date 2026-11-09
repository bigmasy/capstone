import { Form, Formik, setIn, type FormikErrors, type FormikHelpers } from "formik";
import { useMemo, useRef, useState, type FormEvent } from "react";
import toast from "react-hot-toast";
import type { ProfileOwner, Taxonomy } from "../../api/types";
import { taxonomyLabel } from "../../i18n/taxonomy";
import { uk } from "../../i18n/uk";
import { useSaveMyProfileMutation } from "../../redux/api/profileApi";
import FocusFirstError from "../FormField/FocusFirstError";
import Loader from "../Loader/Loader";
import AboutFieldset from "./AboutFieldset";
import CapabilitiesFieldset from "./CapabilitiesFieldset";
import ConsentFieldset from "./ConsentFieldset";
import ContactFieldset from "./ContactFieldset";
import LocationFieldset from "./LocationFieldset";
import SportsFieldset from "./SportsFieldset";
import VisibilityFieldset from "./VisibilityFieldset";
import { describeProfileError } from "./profileErrors";
import {
  buildInitialValues,
  buildProfileSchema,
  toProfilePut,
  type ProfileFormValues,
} from "./profileValues";
import styles from "./ProfileForm.module.css";

interface ProfileFormProps {
  taxonomy: Taxonomy;
  /** The stored profile; absent while the account has none (onboarding). */
  profile?: ProfileOwner;
}

/** Nests flat paths such as `sports.0.sport` into the error object that Formik expects. */
function toFormikErrors(fields: Record<string, string>): FormikErrors<ProfileFormValues> {
  let errors: object = {};
  for (const [path, message] of Object.entries(fields)) {
    errors = setIn(errors, path, message) as object;
  }
  return errors;
}

/**
 * The profile form: onboarding when there is no profile yet, editing otherwise.
 *
 * A server answer of 422 is mapped to the fields from its error types and locations only;
 * the server's own wording is never shown.
 */
const ProfileForm = ({ taxonomy, profile }: ProfileFormProps) => {
  const [save] = useSaveMyProfileMutation();
  const formRef = useRef<HTMLFormElement>(null);
  const [failure, setFailure] = useState<string | null>(null);
  const hasProfile = profile !== undefined;
  const schema = useMemo(() => buildProfileSchema(taxonomy, hasProfile), [taxonomy, hasProfile]);
  const initialValues = useMemo(() => buildInitialValues(profile), [profile]);

  // Only what the API returns about the location: the district, never a position
  const storedArea = profile
    ? profile.district_code
      ? uk.profile.location.storedDistrict(
          taxonomyLabel(taxonomy.version, "districts", profile.district_code),
        )
      : uk.profile.location.storedNoDistrict
    : undefined;

  const handleSubmit = async (
    values: ProfileFormValues,
    helpers: FormikHelpers<ProfileFormValues>,
  ) => {
    setFailure(null);
    try {
      const result = await save(toProfilePut(values));
      if ("error" in result) {
        const described = describeProfileError(result.error);
        setFailure(described.message);
        helpers.setErrors(toFormikErrors(described.fields));
      } else {
        // The coordinates are cleared with the rest: the response carries only the area
        helpers.resetForm({ values: buildInitialValues(result.data) });
        toast.success(uk.profile.saved);
      }
    } finally {
      helpers.setSubmitting(false);
    }
  };

  return (
    <Formik
      initialValues={initialValues}
      validationSchema={schema}
      enableReinitialize
      onSubmit={handleSubmit}
    >
      {({ values, isSubmitting, handleSubmit: submit }) => {
        // aria-disabled does not stop a click or Enter, so a submit while pending is ignored here
        const onSubmit = (event: FormEvent<HTMLFormElement>) => {
          if (isSubmitting) {
            event.preventDefault();
            return;
          }
          submit(event);
        };

        return (
          <Form className={styles.form} noValidate ref={formRef} onSubmit={onSubmit}>
            <FocusFirstError formRef={formRef} />
            <AboutFieldset taxonomy={taxonomy} />
            <SportsFieldset taxonomy={taxonomy} />
            <LocationFieldset storedArea={storedArea} optional={hasProfile} />
            <ContactFieldset />
            <ConsentFieldset />
            {values.functional_data_consent && <CapabilitiesFieldset taxonomy={taxonomy} />}
            <VisibilityFieldset />
            {failure && (
              <p className={styles.submitError} role="alert">
                <strong>{uk.form.errorPrefix}</strong> {failure}
              </p>
            )}
            <div className={styles.actions}>
              <button
                className="button"
                type="submit"
                aria-disabled={isSubmitting ? true : undefined}
              >
                {uk.profile.submit}
              </button>
              {isSubmitting && <Loader label={uk.profile.saving} />}
            </div>
          </Form>
        );
      }}
    </Formik>
  );
};

export default ProfileForm;
