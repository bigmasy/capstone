import { Navigate } from "react-router";
import { isNoProfile, useGetMyProfileQuery } from "../../redux/api/profileApi";
import Loader from "../Loader/Loader";

/** Where a new account is sent: the profile page, which then shows the onboarding. */
export const ONBOARDING_PATH = "/profile";
/** Where an account that already has a profile is sent. */
export const HOME_PATH = "/";

/**
 * Decides where a user goes right after logging in or registering.
 *
 * GET /profiles/me answering 404 means the account has no profile yet, so the user is
 * sent to the profile page to create one; any other answer, including a failed request,
 * leads to the home page, which reports problems with its own retry button.
 */
const PostLoginRedirect = () => {
  const { error, isLoading } = useGetMyProfileQuery();

  if (isLoading) return <Loader />;
  return <Navigate to={isNoProfile(error) ? ONBOARDING_PATH : HOME_PATH} replace />;
};

export default PostLoginRedirect;
