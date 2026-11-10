import { Form, Formik } from "formik";
import { useRef, useState } from "react";
import { Link } from "react-router";
import * as Yup from "yup";
import authStyles from "../../components/AuthForm/AuthForm.module.css";
import { recoveryErrorMessage } from "../../components/AuthForm/recoveryErrors";
import FocusFirstError from "../../components/FormField/FocusFirstError";
import FormField from "../../components/FormField/FormField";
import Loader from "../../components/Loader/Loader";
import { uk } from "../../i18n/uk";
import { useForgotPasswordMutation } from "../../redux/api/authApi";

const text = uk.passwordReset.forgot;
const messages = uk.form.validation;

const schema = Yup.object({
  email: Yup.string()
    .trim()
    .required(messages.required)
    .email(messages.email)
    .max(254, messages.emailMax),
});

/**
 * Asks for a reset link. The page says the same thing whether or not the address has an
 * account, exactly like the server, so it cannot be used to find out who is registered.
 */
const ForgotPasswordPage = () => {
  const [forgot] = useForgotPasswordMutation();
  const formRef = useRef<HTMLFormElement>(null);
  const [sent, setSent] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);

  return (
    <>
      <h1>{text.title}</h1>
      {sent ? (
        <div role="status">
          <p>{text.sent}</p>
          <p>
            <button
              type="button"
              className="button button-secondary"
              onClick={() => setSent(false)}
            >
              {text.another}
            </button>
          </p>
          <p>
            <Link to="/login">{text.backToLogin}</Link>
          </p>
        </div>
      ) : (
        <>
          <p>{text.lead}</p>
          <Formik
            initialValues={{ email: "" }}
            validationSchema={schema}
            onSubmit={async (values, helpers) => {
              setFailure(null);
              try {
                const result = await forgot(values.email.trim());
                if ("error" in result)
                  setFailure(recoveryErrorMessage(result.error));
                else setSent(true);
              } finally {
                helpers.setSubmitting(false);
              }
            }}
          >
            {({
              getFieldProps,
              errors,
              touched,
              isSubmitting,
              handleSubmit,
            }) => (
              <Form
                className={authStyles.form}
                noValidate
                ref={formRef}
                onSubmit={(event) => {
                  // aria-disabled does not stop Enter, so a submit while pending is ignored here
                  if (isSubmitting) {
                    event.preventDefault();
                    return;
                  }
                  handleSubmit(event);
                }}
              >
                <FocusFirstError formRef={formRef} />
                <FormField
                  {...getFieldProps("email")}
                  type="email"
                  label={uk.auth.email}
                  autoComplete="email"
                  autoCapitalize="none"
                  spellCheck={false}
                  required
                  error={touched.email ? errors.email : undefined}
                />
                {failure && (
                  <p className={authStyles.submitError} role="alert">
                    <strong>{uk.form.errorPrefix}</strong> {failure}
                  </p>
                )}
                <div className={authStyles.actions}>
                  <button
                    className="button"
                    type="submit"
                    aria-disabled={isSubmitting ? true : undefined}
                  >
                    {text.submit}
                  </button>
                  {isSubmitting && <Loader label={uk.auth.submitting} />}
                </div>
              </Form>
            )}
          </Formik>
          <p>
            <Link to="/login">{text.backToLogin}</Link>
          </p>
        </>
      )}
    </>
  );
};

export default ForgotPasswordPage;
