import { useEffect, useRef, useState } from "react";
import { Link, useLocation } from "react-router";
import Loader from "../../components/Loader/Loader";
import { uk } from "../../i18n/uk";
import { useVerifyEmailMutation } from "../../redux/api/authApi";
import { selectIsLoggedIn } from "../../redux/auth/selectors";
import { useAppSelector } from "../../redux/hooks";
import styles from "./VerifyEmailPage.module.css";

const text = uk.verification.page;

/** Reads the token from the fragment of the link; the fragment never reaches a server. */
function readToken(hash: string): string | null {
  const token = new URLSearchParams(hash.replace(/^#/, "")).get("token");
  return token && token.length > 0 ? token : null;
}

/**
 * The page the e-mailed link opens. The token is read from the URL fragment, removed from the
 * address bar and the history entry at once (so it is not left in the browser history or a
 * shared screenshot), and sent in the body of one POST. No session is needed: the link may be
 * opened on another device. The result is announced in a status region.
 */
const VerifyEmailPage = () => {
  const { hash } = useLocation();
  const loggedIn = useAppSelector(selectIsLoggedIn);
  const [verify, { isSuccess, isError }] = useVerifyEmailMutation();
  // Read once: the effect below clears the fragment, and a re-render must not lose the token
  const [token] = useState(() => readToken(hash));
  const started = useRef(false);

  useEffect(() => {
    if (token === null || started.current) return;
    started.current = true;
    window.history.replaceState(window.history.state, "", window.location.pathname);
    void verify(token);
  }, [token, verify]);

  let body;
  if (token === null) {
    body = <p>{text.missingToken}</p>;
  } else if (isSuccess) {
    body = (
      <>
        <p>{text.success}</p>
        <Link className="button" to={loggedIn ? "/matches" : "/login"}>
          {loggedIn ? text.toPartners : text.toLogin}
        </Link>
      </>
    );
  } else if (isError) {
    body = (
      <>
        <p>{text.failure}</p>
        <p>{text.failureHelp}</p>
        {!loggedIn && (
          <Link className="button" to="/login">
            {text.toLogin}
          </Link>
        )}
      </>
    );
  } else {
    body = <Loader label={text.checking} />;
  }

  return (
    <>
      <h1>{text.title}</h1>
      <div className={`card status-panel ${styles.result}`} role="status">
        {body}
      </div>
    </>
  );
};

export default VerifyEmailPage;
