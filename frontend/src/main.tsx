import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { Provider } from "react-redux";
import { BrowserRouter } from "react-router";
import App from "./components/App/App";
import ErrorBoundary from "./components/ErrorBoundary/ErrorBoundary";
import { setupStore } from "./redux/store";
import "./styles/tokens.css";
import "./styles/global.css";

const container = document.getElementById("root");
if (!container) {
  throw new Error("Root element #root not found");
}

createRoot(container).render(
  <StrictMode>
    {/* Last line of defence: the page-level boundary in Layout cannot catch AppBar or Navigation errors */}
    <ErrorBoundary standalone>
      <Provider store={setupStore()}>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </Provider>
    </ErrorBoundary>
  </StrictMode>,
);
