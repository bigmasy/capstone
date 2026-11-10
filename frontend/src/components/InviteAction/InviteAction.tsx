import type { FetchBaseQueryError } from "@reduxjs/toolkit/query/react";
import { useEffect, useRef, useState } from "react";
import toast from "react-hot-toast";
import { uk } from "../../i18n/uk";
import { useSendInvitationMutation } from "../../redux/api/invitationsApi";
import { isContactRequired } from "../../redux/api/contactRequired";
import { isEmailNotVerified } from "../../redux/api/emailNotVerified";
import { useEmailStatus } from "../../redux/api/useEmailStatus";
import ConfirmAction from "../ConfirmAction/ConfirmAction";
import ContactRequiredNotice from "../ContactRequiredNotice/ContactRequiredNotice";
import UnverifiedNotice from "../VerificationBanner/UnverifiedNotice";

const text = uk.feed.invite;

/** Fixed message for a failed send; the server's own wording is never shown. */
function describeInviteError(error: unknown): string {
  const status = (error as Partial<FetchBaseQueryError> | undefined)?.status;
  if (status === 404) return text.errorNotFound;
  if (status === 409) return text.errorConflict;
  return text.errorGeneric;
}

interface InviteActionProps {
  profileId: string;
  /** Name used to tell the buttons of different cards apart for assistive technology. */
  name: string;
  /** True once an invitation to this profile has been sent in this session. */
  sent: boolean;
  onSent: (profileId: string) => void;
}

/**
 * The "Invite" button of a feed card: an inline confirmation, then the request. After
 * success the button is replaced by a disabled "sent" button that takes focus, because the
 * button that had it is gone. A profile without a contact cannot invite: the server says so
 * with a coded 409, and the confirmation gives way to a notice that links to the profile.
 */
const InviteAction = ({ profileId, name, sent, onSent }: InviteActionProps) => {
  const [send] = useSendInvitationMutation();
  const [failure, setFailure] = useState<string>(text.errorGeneric);
  const [needsContact, setNeedsContact] = useState(false);
  // The account list may be stale (confirmed in another tab, or not yet read): the server decides
  const [refusedUnverified, setRefusedUnverified] = useState(false);
  const { verified } = useEmailStatus();
  const sentRef = useRef<HTMLButtonElement>(null);
  const sentNow = useRef(false);

  useEffect(() => {
    if (sent && sentNow.current) {
      sentNow.current = false;
      sentRef.current?.focus();
    }
  }, [sent]);

  const invite = async (): Promise<boolean> => {
    const result = await send({ recipient_profile_id: profileId });
    if ("error" in result) {
      if (isEmailNotVerified(result.error)) {
        setRefusedUnverified(true);
        return true;
      }
      if (isContactRequired(result.error)) {
        // The confirmation is replaced by the notice, so there is nothing left to retry here
        setNeedsContact(true);
        return true;
      }
      setFailure(describeInviteError(result.error));
      return false;
    }
    toast.success(text.sentToast);
    sentNow.current = true;
    onSent(profileId);
    return true;
  };

  if (!sent && (!verified || refusedUnverified)) return <UnverifiedNotice action="invite" />;

  if (needsContact) return <ContactRequiredNotice />;

  if (sent) {
    // aria-disabled keeps the button in the tab order, so the new state can be found and read
    return (
      <button
        className="button button-secondary button-done"
        type="button"
        ref={sentRef}
        aria-disabled="true"
      >
        {text.sent}
      </button>
    );
  }

  return (
    <ConfirmAction
      tone="neutral"
      triggerLabel={text.trigger}
      triggerAriaLabel={text.triggerFor(name)}
      title={text.title}
      description={text.description}
      confirmLabel={text.confirm}
      failureMessage={failure}
      onConfirm={invite}
    />
  );
};

export default InviteAction;
