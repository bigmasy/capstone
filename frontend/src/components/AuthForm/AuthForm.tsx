import { Form, Formik, type FormikHelpers } from "formik";
import { useRef, useState, type FormEvent } from "react";
import toast from "react-hot-toast";
import { Link, useNavigate } from "react-router";
import * as Yup from "yup";
import type { Credentials } from "../../api/types";
import { uk } from "../../i18n/uk";
import { useLoginMutation, useRegisterMutation } from "../../redux/api/authApi";
import FocusFirstError from "../FormField/FocusFirstError";
import FormField from "../FormField/FormField";
import Loader from "../Loader/Loader";
import { describeAuthError, type AuthFailure, type AuthMode } from "./authErrors";
import styles from "./AuthForm.module.css";

interface AuthFormProps {
  mode: AuthMode;
}

const messages = uk.form.validation;

// Limits follow the backend contract: e-mail up to 254 characters, password 10 to 128
const credentialsSchema = Yup.object({
  email: Yup.string()
    .trim()
    .required(messages.required)
    .email(messages.email)
    .max(254, messages.emailMax),
  password: Yup.string()
    .required(messages.required)
    .min(10, messages.passwordMin)
    .max(128, messages.passwordMax),
});

const initialValues: Credentials = { email: "", password: "" };

/** Email and password form shared by the login and registration pages. */
const AuthForm = ({ mode }: AuthFormProps) => {
  const [login] = useLoginMutation();
  const [register] = useRegisterMutation();
  const navigate = useNavigate();
  const formRef = useRef<HTMLFormElement>(null);
  const [failure, setFailure] = useState<AuthFailure | null>(null);
  const isRegister = mode === "register";

  const handleSubmit = async (values: Credentials, helpers: FormikHelpers<Credentials>) => {
    setFailure(null);
    const credentials = { email: values.email.trim(), password: values.password };
    try {
      const result = await (isRegister ? register(credentials) : login(credentials));
      if ("error" in result) {
        const described = describeAuthError(result.error, mode);
        setFailure(described);
        helpers.setErrors(described.fields);
      } else if (result.data.loggedIn) {
        toast.success(isRegister ? uk.auth.registered : uk.auth.loggedIn);
      } else {
        // The account exists but the automatic login failed: continue on the login page
        toast.success(uk.auth.registeredLoginRequired);
        void navigate("/login");
      }
    } finally {
      helpers.setSubmitting(false);
    }
  };

  return (
    <Formik
      initialValues={initialValues}
      validationSchema={credentialsSchema}
      onSubmit={handleSubmit}
    >
      {({ getFieldProps, errors, touched, isSubmitting, handleSubmit: submit }) => {
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
            <FormField
              {...getFieldProps("password")}
              type="password"
              label={uk.auth.password}
              autoComplete={isRegister ? "new-password" : "current-password"}
              hint={isRegister ? uk.auth.passwordHint : undefined}
              required
              error={touched.password ? errors.password : undefined}
            />
            {failure && (
              <p className={styles.submitError} role="alert">
                <strong>{uk.form.errorPrefix}</strong> {failure.message}
                {failure.linkToLogin && (
                  <>
                    {" "}
                    <Link to="/login">{uk.auth.accountExistsLink}</Link>
                  </>
                )}
              </p>
            )}
            <div className={styles.actions}>
              <button
                className="button"
                type="submit"
                aria-disabled={isSubmitting ? true : undefined}
              >
                {isRegister ? uk.auth.submitRegister : uk.auth.submitLogin}
              </button>
              {isSubmitting && <Loader label={uk.auth.submitting} />}
            </div>
          </Form>
        );
      }}
    </Formik>
  );
};

export default AuthForm;
