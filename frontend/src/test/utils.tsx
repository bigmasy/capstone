import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import { Provider } from "react-redux";
import { MemoryRouter, type InitialEntry } from "react-router";
import { setupStore, type RootState } from "../redux/store";

interface RenderOptions {
  /** Initial location: a path, or an entry with router state. */
  route?: InitialEntry;
  preloadedState?: Partial<RootState>;
}

/** Renders a tree inside a fresh store and an in-memory router. */
export function renderWithProviders(
  ui: ReactElement,
  { route = "/", preloadedState }: RenderOptions = {},
) {
  const store = setupStore(preloadedState);
  const result = render(
    <Provider store={store}>
      <MemoryRouter initialEntries={[route]}>{ui}</MemoryRouter>
    </Provider>,
  );
  return { store, ...result };
}

export const loggedIn: Partial<RootState> = { auth: { token: "test-token" } };
