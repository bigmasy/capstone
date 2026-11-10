import { selectIsLoggedIn } from "../auth/selectors";
import { useAppSelector } from "../hooks";
import { useMeQuery } from "./authApi";

export interface EmailStatus {
  /** True once the account has been read from the server. */
  known: boolean;
  /**
   * False only when the server said the address is not confirmed. While the answer is
   * pending, and when nobody is signed in, it is true, so nothing flashes or gets blocked.
   */
  verified: boolean;
}

/** Whether the signed-in user has confirmed the e-mail address. */
export function useEmailStatus(): EmailStatus {
  const loggedIn = useAppSelector(selectIsLoggedIn);
  const { data } = useMeQuery(undefined, { skip: !loggedIn });
  // Only an explicit "false" blocks: a missing or unreadable answer must not lock anybody out
  return { known: data !== undefined, verified: data?.email_verified !== false };
}
