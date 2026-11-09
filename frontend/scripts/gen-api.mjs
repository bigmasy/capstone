// Generates TypeScript types from the OpenAPI contract exported by the backend.
import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const input = resolve(root, "../docs/api/openapi.json");
const output = resolve(root, "src/api/schema.d.ts");

if (!existsSync(input)) {
  console.error(`gen:api: OpenAPI contract not found at ${input}`);
  console.error("Export the contract from the backend first, then run this script again.");
  process.exit(1);
}

const result = spawnSync("npx", ["--no-install", "openapi-typescript", input, "-o", output], {
  cwd: root,
  stdio: "inherit",
});

if (result.error) {
  console.error(`gen:api: could not run openapi-typescript: ${result.error.message}`);
  process.exit(1);
}
process.exit(result.status ?? 1);
