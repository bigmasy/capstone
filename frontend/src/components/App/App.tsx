import { Route, Routes } from "react-router";
import { Toaster } from "react-hot-toast";
import AboutPage from "../../pages/AboutPage/AboutPage";
import HomePage from "../../pages/HomePage/HomePage";
import InvitationsPage from "../../pages/InvitationsPage/InvitationsPage";
import LoginPage from "../../pages/LoginPage/LoginPage";
import MatchesPage from "../../pages/MatchesPage/MatchesPage";
import NotFoundPage from "../../pages/NotFoundPage/NotFoundPage";
import ProfilePage from "../../pages/ProfilePage/ProfilePage";
import RegisterPage from "../../pages/RegisterPage/RegisterPage";
import Layout from "../Layout/Layout";
import PostLoginRedirect from "../PostLoginRedirect/PostLoginRedirect";
import PrivateRoute from "../PrivateRoute/PrivateRoute";
import RestrictedRoute from "../RestrictedRoute/RestrictedRoute";
import SessionGuard from "../SessionGuard/SessionGuard";

const App = () => (
  <>
    {/* Each toast is a role="status" element; 6 s gives time to read a status message (WCAG 2.2.1) */}
    <Toaster position="top-center" toastOptions={{ duration: 6000 }} />
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<HomePage />} />
        <Route path="about" element={<AboutPage />} />
        {/* A logged-in visitor of these pages is sent to /start, which picks onboarding or home */}
        <Route
          path="login"
          element={<RestrictedRoute component={<LoginPage />} redirectTo="/start" />}
        />
        <Route
          path="register"
          element={<RestrictedRoute component={<RegisterPage />} redirectTo="/start" />}
        />
        <Route path="start" element={<PrivateRoute component={<PostLoginRedirect />} />} />
        <Route path="profile" element={<PrivateRoute component={<ProfilePage />} />} />
        <Route path="matches" element={<PrivateRoute component={<MatchesPage />} />} />
        <Route path="invitations" element={<PrivateRoute component={<InvitationsPage />} />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
    {/* After the routes: its effects must run after PrivateRoute's own redirect so that the router state wins */}
    <SessionGuard />
  </>
);

export default App;
