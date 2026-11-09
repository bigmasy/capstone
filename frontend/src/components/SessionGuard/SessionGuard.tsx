import { useEffect } from "react";
import { useNavigate } from "react-router";
import { authApi } from "../../redux/api/authApi";
import { selectSessionEndedBy } from "../../redux/auth/selectors";
import { sessionEndAcknowledged } from "../../redux/auth/slice";
import { useAppDispatch, useAppSelector, useAppStore } from "../../redux/hooks";

/** Router state that tells the login page why the user has arrived there. */
export interface SessionEndState {
  reason: "expired";
}

/**
 * Keeps the session honest; renders nothing.
 *
 * On start it asks the server once whether a token restored from sessionStorage is still
 * valid (a 401 clears the session in the base query). When the server ends the session,
 * it sends the user to the login page with `{ reason: "expired" }` in the router state. After
 * the user deleted the account or signed out, it sends them to the landing page instead.
 * There is deliberately no refresh-token flow and no countdown.
 */
const SessionGuard = () => {
  const dispatch = useAppDispatch();
  const store = useAppStore();
  const navigate = useNavigate();
  const endedBy = useAppSelector(selectSessionEndedBy);

  useEffect(() => {
    if (store.getState().auth.token !== null) {
      // Concurrent identical requests are shared, so the StrictMode double effect sends one
      void dispatch(authApi.endpoints.me.initiate());
    }
  }, [dispatch, store]);

  useEffect(() => {
    if (endedBy === "deleted" || endedBy === "signedOut") {
      // Not an error: the user asked for this, so the landing page is the natural next screen
      void navigate("/", { replace: true });
      dispatch(sessionEndAcknowledged());
      return;
    }
    if (endedBy !== "expired") return;
    const state: SessionEndState = { reason: "expired" };
    void navigate("/login", { replace: true, state });
    dispatch(sessionEndAcknowledged());
  }, [endedBy, dispatch, navigate]);

  return null;
};

export default SessionGuard;
