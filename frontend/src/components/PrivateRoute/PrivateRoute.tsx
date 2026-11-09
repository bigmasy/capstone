import type { ReactElement } from "react";
import { Navigate } from "react-router";
import { useAppSelector } from "../../redux/hooks";
import { selectIsLoggedIn } from "../../redux/auth/selectors";

interface PrivateRouteProps {
  component: ReactElement;
  redirectTo?: string;
}

/** Renders the page for logged-in users only; others are redirected. */
const PrivateRoute = ({ component, redirectTo = "/login" }: PrivateRouteProps) => {
  const isLoggedIn = useAppSelector(selectIsLoggedIn);
  return isLoggedIn ? component : <Navigate to={redirectTo} replace />;
};

export default PrivateRoute;
