import type { FetchBaseQueryError } from "@reduxjs/toolkit/query/react";
import { useState } from "react";
import type { InvitationOut } from "../../api/types";
import { uk } from "../../i18n/uk";
import {
  useAcceptInvitationMutation,
  useCancelInvitationMutation,
  useDeclineInvitationMutation,
} from "../../redux/api/invitationsApi";
import { isContactRequired } from "../../redux/api/contactRequired";
import ConfirmAction from "../ConfirmAction/ConfirmAction";
import ContactRequiredNotice from "../ContactRequiredNotice/ContactRequiredNotice";
import styles from "./InvitationCard.module.css";

/** What the page tells the user after an answer; it outlives the card that was answered. */
export interface ActionFeedback {
  kind: "success" | "error";
  text: string;
}

const text = uk.invitations;

/** Fixed message for a failed answer; the server's own wording is never shown. */
function describeAnswerError(error: unknown): { message: string; refreshed: boolean } {
  const status = (error as Partial<FetchBaseQueryError> | undefined)?.status;
  // 404 and 409 mean that the invitation changed or went away: the list is refreshed
  if (status === 409) return { message: text.errors.conflict, refreshed: true };
  if (status === 404) return { message: text.errors.notFound, refreshed: true };
  if (status === 403) return { message: text.errors.forbidden, refreshed: false };
  return { message: text.errors.generic, refreshed: false };
}

interface InvitationActionsProps {
  invitation: InvitationOut;
  /** Name that tells the buttons of different cards apart for assistive technology. */
  partnerName: string;
  onFeedback: (feedback: ActionFeedback) => void;
}

/**
 * The actions that apply to a pending invitation: the recipient accepts or declines, the
 * sender cancels. Each one is an inline confirmation. A conflict ends in a message on the
 * page, because the refreshed list no longer shows the buttons of the answered card. Accepting
 * without a contact on the own profile keeps the invitation pending and shows a notice that
 * links to the profile instead of the accept confirmation; declining stays available.
 */
const InvitationActions = ({ invitation, partnerName, onFeedback }: InvitationActionsProps) => {
  const [accept] = useAcceptInvitationMutation();
  const [decline] = useDeclineInvitationMutation();
  const [cancel] = useCancelInvitationMutation();
  const [failure, setFailure] = useState<string>(text.errors.generic);
  const [needsContact, setNeedsContact] = useState(false);

  if (invitation.status !== "pending") return null;

  const answer =
    (run: typeof accept, done: string, contactAware = false) =>
    async (): Promise<boolean> => {
      const result = await run(invitation.id);
      if (!("error" in result)) {
        // The focused message above the list confirms the result, so no toast is added
        onFeedback({ kind: "success", text: done });
        return true;
      }
      if (contactAware && isContactRequired(result.error)) {
        // The invitation stays pending; the confirmation gives way to a notice with a link
        setNeedsContact(true);
        return true;
      }
      const { message, refreshed } = describeAnswerError(result.error);
      if (refreshed) {
        // Nothing is left to confirm: the refreshed list shows the real state of the invitation
        onFeedback({ kind: "error", text: message });
        return true;
      }
      setFailure(message);
      return false;
    };

  const actions = text.actions;
  return (
    <div className={styles.actions}>
      {invitation.direction === "incoming" ? (
        <>
          {needsContact ? (
            <ContactRequiredNotice />
          ) : (
            <ConfirmAction
              tone="neutral"
              triggerLabel={actions.accept.trigger}
              triggerAriaLabel={actions.accept.triggerFor(partnerName)}
              title={actions.accept.title}
              description={actions.accept.description}
              confirmLabel={actions.accept.confirm}
              failureMessage={failure}
              onConfirm={answer(accept, actions.accept.done, true)}
            />
          )}
          <ConfirmAction
            triggerLabel={actions.decline.trigger}
            triggerAriaLabel={actions.decline.triggerFor(partnerName)}
            title={actions.decline.title}
            description={actions.decline.description}
            confirmLabel={actions.decline.confirm}
            failureMessage={failure}
            onConfirm={answer(decline, actions.decline.done)}
          />
        </>
      ) : (
        <ConfirmAction
          triggerLabel={actions.cancel.trigger}
          triggerAriaLabel={actions.cancel.triggerFor(partnerName)}
          title={actions.cancel.title}
          description={actions.cancel.description}
          confirmLabel={actions.cancel.confirm}
          failureMessage={failure}
          onConfirm={answer(cancel, actions.cancel.done)}
        />
      )}
    </div>
  );
};

export default InvitationActions;
