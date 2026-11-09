import { Link } from "react-router";
import AuthForm from "../../components/AuthForm/AuthForm";
import { uk } from "../../i18n/uk";

const RegisterPage = () => (
  <>
    <h1>{uk.pages.register.title}</h1>
    <p>{uk.pages.register.lead}</p>
    <AuthForm mode="register" />
    <p>
      {uk.pages.register.haveAccount} <Link to="/login">{uk.nav.login}</Link>
    </p>
  </>
);

export default RegisterPage;
