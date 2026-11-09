import { test as base } from "@playwright/test";
import { buildWorld, disposeWorld, type World } from "./world";

/**
 * `test` with a worker-scoped `world` fixture: the shared accounts are created the first time a
 * test asks for them and deleted when the worker ends. The registration flow does not use it, so
 * it keeps the sign-in budget of the proxy to itself when it runs first (files run in
 * alphabetical order and the flow file sorts before the others).
 */
export const test = base.extend<object, { world: World }>({
  world: [
    // Playwright reads the fixture dependencies from the destructuring pattern, so it must stay
    // eslint-disable-next-line no-empty-pattern
    async ({}, use, workerInfo) => {
      const baseURL = workerInfo.project.use.baseURL ?? "https://localhost:8443";
      const world = await buildWorld(baseURL);
      await use(world);
      await disposeWorld(baseURL, world);
    },
    { scope: "worker", timeout: 300_000 },
  ],
});

export { expect } from "@playwright/test";
