import { uk } from "../../i18n/uk";
import styles from "./VerificationBanner.module.css";

interface UnverifiedNoticeProps {
  /** Which action is blocked: sending an invitation or accepting one. */
  action: "invite" | "accept";
}

/**
 * Takes the place of a button that an unconfirmed account cannot use. It is plain text, not a
 * disabled button, so nobody has to guess why nothing happens; the banner above the page says
 * how to confirm the address.
 */
const UnverifiedNotice = ({ action }: UnverifiedNoticeProps) => (
  <p className={styles.notice}>
    {action === "invite" ? uk.verification.inviteNotice : uk.verification.acceptNotice}
  </p>
);

export default UnverifiedNotice;
