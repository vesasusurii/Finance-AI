/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL: string;
  /** Set to "false" to hide seed credentials on the login page */
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
