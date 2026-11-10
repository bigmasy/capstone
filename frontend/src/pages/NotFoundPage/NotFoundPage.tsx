import { Link } from "react-router";
import { uk } from "../../i18n/uk";

const NotFoundPage = () => (
  <>
    <h1>{uk.pages.notFound.title}</h1>
    <div className="card status-panel">
      <p>{uk.pages.notFound.lead}</p>
      <Link className="button" to="/">
        {uk.pages.notFound.backHome}
      </Link>
    </div>
  </>
);

export default NotFoundPage;
