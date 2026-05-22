/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL: string;
  /** Set to "false" to hide seed credentials on the login page */
  readonly VITE_SHOW_DEV_LOGIN_HINT?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
