import { Form, Formik } from "formik";
import { useEffect, useRef, useState } from "react";
import { Link, useLocation } from "react-router";
import * as Yup from "yup";
import authStyles from "../../components/AuthForm/AuthForm.module.css";
import { recoveryErrorMessage } from "../../components/AuthForm/recoveryErrors";
import FocusFirstError from "../../components/FormField/FocusFirstError";
import FormField from "../../components/FormField/FormField";
import Loader from "../../components/Loader/Loader";
import { uk } from "../../i18n/uk";
import { useResetPasswordMutation } from "../../redux/api/authApi";

const text = uk.passwordReset.reset;
const messages = uk.form.validation;

const schema = Yup.object({
  password: Yup.string()
    .required(messages.required)
    .min(10, messages.passwordMin)
    .max(128, messages.passwordMax),
  confirmPassword: Yup.string()
    .required(messages.confirmRequired)
    .oneOf([Yup.ref("password")], messages.passwordMismatch),
});

/** Reads the token from the fragment of the link; the fragment never reaches a server. */
function readToken(hash: string): string | null {
  const token = new URLSearchParams(hash.replace(/^#/, "")).get("token");
  return token && token.length > 0 ? token : null;
}

/**
 * The page the e-mailed reset link opens. The token is read from the URL fragment and removed
 * from the address bar and the history entry at once, then sent in the body of one POST with
 * the new password. A link that the server refuses (unknown, used or expired) is explained
 * and followed by a way to ask for a new one.
 */
const ResetPasswordPage = () => {
  const { hash } = useLocation();
  const [reset] = useResetPasswordMutation();
  const formRef = useRef<HTMLFormElement>(null);
  // Read once: the effect below clears the fragment, and a re-render must not lose the token
  const [token] = useState(() => readToken(hash));
  const [saved, setSaved] = useState(false);
  const [linkRefused, setLinkRefused] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);

  useEffect(() => {
    if (token !== null) {
      window.history.replaceState(
        window.history.state,
        "",
        window.location.pathname,
      );
    }
  }, [token]);

  const askForNew = (
    <Link className="button" to="/forgot-password">
      {text.requestNew}
    </Link>
  );

  let body;
  if (token === null) {
    body = (
      <div role="status">
        <p>{text.missingToken}</p>
        {askForNew}
      </div>
    );
  } else if (saved) {
    body = (
      <div role="status">
        <p>{text.saved}</p>
        <Link className="button" to="/login">
          {text.toLogin}
        </Link>
      </div>
    );
  } else if (linkRefused) {
    body = (
      <div role="alert">
        <p>{text.invalidLink}</p>
        {askForNew}
      </div>
    );
  } else {
    body = (
      <>
        <p>{text.lead}</p>
        <Formik
          initialValues={{ password: "", confirmPassword: "" }}
          validationSchema={schema}
          onSubmit={async (values, helpers) => {
            setFailure(null);
            try {
              const result = await reset({ token, password: values.password });
              if (!("error" in result)) {
                setSaved(true);
              } else if (
                typeof result.error === "object" &&
                (result.error as { status?: unknown }).status === 400
              ) {
                setLinkRefused(true);
              } else if (
                (result.error as { status?: unknown }).status === 422
              ) {
                setFailure(uk.auth.serverRejectedPassword);
              } else {
                setFailure(recoveryErrorMessage(result.error, text.failed));
              }
            } finally {
              helpers.setSubmitting(false);
            }
          }}
        >
          {({ getFieldProps, errors, touched, isSubmitting, handleSubmit }) => (
            <Form
              className={authStyles.form}
              noValidate
              ref={formRef}
              onSubmit={(event) => {
                if (isSubmitting) {
                  event.preventDefault();
                  return;
                }
                handleSubmit(event);
              }}
            >
              <FocusFirstError formRef={formRef} />
              <FormField
                {...getFieldProps("password")}
                type="password"
                label={text.newPassword}
                autoComplete="new-password"
                hint={uk.auth.passwordHint}
                required
                error={touched.password ? errors.password : undefined}
              />
              <FormField
                {...getFieldProps("confirmPassword")}
                type="password"
                label={text.confirmPassword}
                autoComplete="new-password"
                required
                error={
                  touched.confirmPassword ? errors.confirmPassword : undefined
                }
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
      </>
    );
  }

  return (
    <>
      <h1>{text.title}</h1>
      {body}
    </>
  );
};

export default ResetPasswordPage;
