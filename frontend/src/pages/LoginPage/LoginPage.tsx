import { Link, useLocation } from "react-router";
import AuthForm from "../../components/AuthForm/AuthForm";
import type { SessionEndState } from "../../components/SessionGuard/SessionGuard";
import { uk } from "../../i18n/uk";

const LoginPage = () => {
  const state = useLocation().state as Partial<SessionEndState> | null;
  const sessionEnded = state?.reason === "expired";

  return (
    <>
      <h1>{uk.pages.login.title}</h1>
      {sessionEnded && (
        <p className="alert alert-warning" role="status">
          {uk.auth.sessionEnded}
        </p>
      )}
      <p>{uk.pages.login.lead}</p>
      <AuthForm mode="login" />
      <p>
        {uk.pages.login.noAccount} <Link to="/register">{uk.nav.register}</Link>
      </p>
    </>
  );
};

export default LoginPage;
