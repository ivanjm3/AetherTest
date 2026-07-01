/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE: string
  readonly VITE_DEFAULT_PIPELINE_ARN?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
