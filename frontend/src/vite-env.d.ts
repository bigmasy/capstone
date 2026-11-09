/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Base URL of the REST API; defaults to the dev proxy path. */
  readonly VITE_API_BASE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
