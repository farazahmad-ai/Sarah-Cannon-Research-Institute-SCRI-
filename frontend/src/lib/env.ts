/**
 * Single source of truth for all frontend environment variables.
 *
 * Rules:
 * - Never read `import.meta.env` directly in components or other modules.
 * - If a required variable is missing, throw immediately at module load time
 *   so the blank-screen failure is obvious during development — not a silent
 *   runtime error inside a coordinator's active screening session.
 */

function requireEnv(key: string): string {
  const value = import.meta.env[key];
  if (!value) {
    throw new Error(
      `[env] Required environment variable "${key}" is missing. ` +
        `Add it to frontend/.env and restart the dev server.`
    );
  }
  return value as string;
}

export const env = {
  /** Base URL of the FastAPI backend, e.g. http://localhost:8000 */
  apiBaseUrl: requireEnv("VITE_API_BASE_URL"),

  /** Supabase project URL — safe to expose in the browser */
  supabaseUrl: requireEnv("VITE_SUPABASE_URL"),

  /** Supabase anon/publishable key — safe to expose in the browser */
  supabaseAnonKey: requireEnv("VITE_SUPABASE_ANON_KEY"),
} as const;
