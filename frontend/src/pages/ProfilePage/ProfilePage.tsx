import AccountActions from "../../components/AccountActions/AccountActions";
import Loader from "../../components/Loader/Loader";
import ProfileForm from "../../components/ProfileForm/ProfileForm";
import { uk } from "../../i18n/uk";
import {
  isNoProfile,
  useGetMyProfileQuery,
  useGetTaxonomyQuery,
} from "../../redux/api/profileApi";
import styles from "./ProfilePage.module.css";

/**
 * The profile page: the form for editing, or the onboarding variant of it when the
 * account has no profile yet (GET /profiles/me answered 404).
 */
const ProfilePage = () => {
  const taxonomy = useGetTaxonomyQuery();
  const profile = useGetMyProfileQuery();
  // After a failed refetch RTK Query keeps the last data, so the 404 is checked first
  const noProfile = isNoProfile(profile.error);
  const stored = noProfile ? undefined : profile.data;

  let content;
  if (taxonomy.isLoading || profile.isLoading) {
    content = <Loader label={uk.profile.loading} />;
  } else if (!taxonomy.data) {
    content = (
      <div>
        <p className={styles.error} role="alert">
          <strong>{uk.form.errorPrefix}</strong> {uk.profile.taxonomyFailed}
        </p>
        <button className="button" type="button" onClick={() => void taxonomy.refetch()}>
          {uk.profile.retry}
        </button>
      </div>
    );
  } else if (!noProfile && !stored) {
    content = (
      <div>
        <p className={styles.error} role="alert">
          <strong>{uk.form.errorPrefix}</strong> {uk.profile.loadFailed}
        </p>
        <button className="button" type="button" onClick={() => void profile.refetch()}>
          {uk.profile.retry}
        </button>
      </div>
    );
  } else {
    content = (
      <>
        {noProfile && (
          <section className={styles.onboarding} aria-labelledby="onboarding-heading">
            <h2 id="onboarding-heading">{uk.profile.onboarding.title}</h2>
            <p>{uk.profile.onboarding.lead}</p>
          </section>
        )}
        <ProfileForm taxonomy={taxonomy.data} profile={stored} />
        <AccountActions />
      </>
    );
  }

  return (
    <>
      <h1>{uk.pages.profile.title}</h1>
      {content}
    </>
  );
};

export default ProfilePage;
