import { Link } from "react-router";
import { uk } from "../../i18n/uk";

const NotFoundPage = () => (
  <>
    <h1>{uk.pages.notFound.title}</h1>
    <p>{uk.pages.notFound.lead}</p>
    <p>
      <Link to="/">{uk.pages.notFound.backHome}</Link>
    </p>
  </>
);

export default NotFoundPage;
