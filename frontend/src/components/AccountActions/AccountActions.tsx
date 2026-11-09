import { useId } from "react";
import toast from "react-hot-toast";
import { uk } from "../../i18n/uk";
import { useDeleteAccountMutation } from "../../redux/api/profileApi";
import { accountDeleted } from "../../redux/auth/slice";
import { useAppDispatch } from "../../redux/hooks";
import ConfirmAction from "../ConfirmAction/ConfirmAction";
import styles from "./AccountActions.module.css";

const text = uk.profile.manage;

/**
 * The one destructive action of the profile page: deleting the profile together with the
 * account behind an explicit confirmation step. The server removes everything that belongs to
 * the account in one transaction, so there is no separate "delete only the profile" action.
 */
const AccountActions = () => {
  const headingId = useId();
  const dispatch = useAppDispatch();
  const [deleteAccount] = useDeleteAccountMutation();

  const removeAll = async (): Promise<boolean> => {
    const result = await deleteAccount();
    if ("error" in result) return false;
    toast.success(text.deleteAll.done);
    // Ends the session and clears every cached answer of the deleted account; the session
    // watcher then sends the user to the landing page
    dispatch(accountDeleted());
    return true;
  };

  return (
    <section className={styles.section} aria-labelledby={headingId}>
      <h2 id={headingId}>{text.legend}</h2>
      <div className={styles.item}>
        <ConfirmAction
          triggerLabel={text.deleteAll.trigger}
          title={text.deleteAll.title}
          description={text.deleteAll.description}
          confirmLabel={text.deleteAll.confirm}
          failureMessage={text.deleteAll.failed}
          onConfirm={removeAll}
        />
      </div>
    </section>
  );
};

export default AccountActions;
