import AudienceSection from "../../components/landing/AudienceSection";
import FaqSection from "../../components/landing/FaqSection";
import FinalCta from "../../components/landing/FinalCta";
import Hero from "../../components/landing/Hero";
import HowItWorks from "../../components/landing/HowItWorks";
import MemberPanel from "../../components/landing/MemberPanel";
import PrivacySection from "../../components/landing/PrivacySection";
import SourcesSection from "../../components/landing/SourcesSection";
import WhySection from "../../components/landing/WhySection";
import { selectIsLoggedIn } from "../../redux/auth/selectors";
import { useAppSelector } from "../../redux/hooks";

/**
 * Public landing page, shown to everyone. A logged-in visitor sees the same page with the
 * calls to action pointing into the app and a panel with their own profile.
 */
const HomePage = () => {
  const isLoggedIn = useAppSelector(selectIsLoggedIn);

  return (
    <>
      <Hero isLoggedIn={isLoggedIn} />
      {isLoggedIn && <MemberPanel />}
      <HowItWorks />
      <WhySection />
      <PrivacySection />
      <AudienceSection />
      <SourcesSection />
      <FaqSection />
      <FinalCta isLoggedIn={isLoggedIn} />
    </>
  );
};

export default HomePage;
