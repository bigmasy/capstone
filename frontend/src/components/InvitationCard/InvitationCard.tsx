import { useId } from "react";
import type { InvitationOut } from "../../api/types";
import { formatDateTime } from "../../i18n/format";
import { uk } from "../../i18n/uk";
import Avatar from "../Avatar/Avatar";
import PartnerFacts from "../PartnerFacts/PartnerFacts";
import InvitationActions, { type ActionFeedback } from "./InvitationActions";
import styles from "./InvitationCard.module.css";

const text = uk.invitations;

/** Dates the invitation: when it was sent or received and when it expired or was answered. */
function describeDates(invitation: InvitationOut): string[] {
  const card = text.card;
  const lines = [
    invitation.direction === "incoming"
      ? card.received(formatDateTime(invitation.created_at))
      : card.sent(formatDateTime(invitation.created_at)),
  ];
  const answeredAt = invitation.responded_at ? formatDateTime(invitation.responded_at) : null;
  switch (invitation.status) {
    case "pending":
      lines.push(card.pendingUntil(formatDateTime(invitation.expires_at)));
      break;
    case "expired":
      lines.push(card.expiredOn(formatDateTime(invitation.expires_at)));
      break;
    case "cancelled":
      if (answeredAt) lines.push(card.cancelledOn(answeredAt));
      break;
    default:
      if (answeredAt) lines.push(card.answeredOn(answeredAt));
  }
  return lines;
}

interface InvitationCardProps {
  invitation: InvitationOut;
  version: string;
  onFeedback: (feedback: ActionFeedback) => void;
}

/**
 * One invitation with the public fields of the other party, its status and dates, the
 * actions that apply and, once it is accepted, the other party's contact.
 */
const InvitationCard = ({ invitation, version, onFeedback }: InvitationCardProps) => {
  const headingId = useId();
  const partner = invitation.direction === "incoming" ? invitation.sender : invitation.recipient;
  const name = partner?.display_name ?? text.card.partnerUnavailable;
  // The contact is shown only for an accepted invitation, whatever else the response holds
  const accepted = invitation.status === "accepted";

  return (
    <li>
      <article className={styles.card} aria-labelledby={headingId}>
        <div className={styles.head}>
          {partner && (
            <Avatar profileId={partner.id} name={partner.display_name} hasPhoto={partner.has_photo} />
          )}
          <div className={styles.who}>
            <p className={styles.role}>
              {invitation.direction === "incoming" ? text.card.from : text.card.to}
            </p>
            <h3 className={styles.name} id={headingId}>
              {name}
            </h3>
          </div>
        </div>
        <p className={styles.status}>
          <span className={styles.badge}>{text.status[invitation.status]}</span>
        </p>
        {describeDates(invitation).map((line) => (
          <p key={line} className={styles.date}>
            {line}
          </p>
        ))}
        {partner && <PartnerFacts partner={partner} version={version} />}
        {accepted && partner && (
          <section className={styles.contact}>
            <h4 className={styles.contactHeading}>{text.card.contactHeading}</h4>
            {partner.contact ? (
              <>
                <p className={styles.contactValue}>{partner.contact}</p>
                <p className={styles.note}>{text.card.contactNote}</p>
              </>
            ) : (
              <p>{text.card.contactNone}</p>
            )}
          </section>
        )}
        <InvitationActions invitation={invitation} partnerName={name} onFeedback={onFeedback} />
      </article>
    </li>
  );
};

export default InvitationCard;
