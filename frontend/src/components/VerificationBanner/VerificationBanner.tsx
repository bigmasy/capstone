import { useState } from "react";
import { useLocation } from "react-router";
import { uk } from "../../i18n/uk";
import { useResendVerificationMutation } from "../../redux/api/authApi";
import { useEmailStatus } from "../../redux/api/useEmailStatus";
import { selectIsLoggedIn } from "../../redux/auth/selectors";
import { useAppSelector } from "../../redux/hooks";
import Loader from "../Loader/Loader";
import styles from "./VerificationBanner.module.css";

const text = uk.verification;
const VERIFY_PATH = "/verify-email";

/**
 * Asks a signed-in user whose address is not confirmed to confirm it, and offers to send the
 * message again. It is a labelled region above the page content, shown on every page except
 * the confirmation page itself, and disappears when the account is confirmed. The result of
 * asking for a new message is announced through a status line; the server answers the same
 * way whether or not a message was sent, so the text says "if".
 */
const VerificationBanner = () => {
  const loggedIn = useAppSelector(selectIsLoggedIn);
  const { verified } = useEmailStatus();
  const { pathname } = useLocation();
  const [resend, { isLoading }] = useResendVerificationMutation();
  const [message, setMessage] = useState<string>("");

  if (!loggedIn || verified || pathname === VERIFY_PATH) return null;

  const onResend = async () => {
    setMessage("");
    const result = await resend();
    setMessage("error" in result ? text.resendFailed : text.resent);
  };

  return (
    <section className={styles.banner} aria-label={text.bannerLabel}>
      <div className={`container ${styles.inner}`}>
        <div className={styles.copy}>
          <p className={styles.title}>{text.bannerTitle}</p>
          <p className={styles.text}>{text.bannerText}</p>
          <p className={styles.status} role="status">
            {message}
          </p>
        </div>
        <div className={styles.actions}>
          <button
            className="button button-secondary"
            type="button"
            aria-disabled={isLoading ? true : undefined}
            onClick={() => {
              if (!isLoading) void onResend();
            }}
          >
            {text.resend}
          </button>
          {isLoading && <Loader label={text.resending} />}
        </div>
      </div>
    </section>
  );
};

export default VerificationBanner;
