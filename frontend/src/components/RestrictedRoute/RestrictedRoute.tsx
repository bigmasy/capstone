import type { ReactElement } from "react";
import { Navigate } from "react-router";
import { useAppSelector } from "../../redux/hooks";
import { selectIsLoggedIn } from "../../redux/auth/selectors";

interface RestrictedRouteProps {
  component: ReactElement;
  redirectTo?: string;
}

/** Renders the page for anonymous users only (login, registration); logged-in users are redirected. */
const RestrictedRoute = ({ component, redirectTo = "/profile" }: RestrictedRouteProps) => {
  const isLoggedIn = useAppSelector(selectIsLoggedIn);
  return isLoggedIn ? <Navigate to={redirectTo} replace /> : component;
};

export default RestrictedRoute;
