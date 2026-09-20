/**
 * Supabase browser client — singleton instance shared across the entire SPA.
 *
 * Why a singleton matters:
 * createClient() maintains in-memory session state and sets up a real-time
 * auth state listener. Creating multiple instances causes desynchronized
 * session state and duplicate network subscriptions — one instance per app.
 */

import { createClient, SupabaseClient } from "@supabase/supabase-js";
import { env } from "@/lib/env";

export const supabase: SupabaseClient = createClient(
  env.supabaseUrl,
  env.supabaseAnonKey,
  {
    auth: {
      // Persist the session in localStorage so coordinators stay logged in
      // across page refreshes without re-entering credentials.
      persistSession: true,
      // Let the client auto-refresh the JWT before it expires — the backend
      // never refreshes tokens (auto_refresh_token=False on the server).
      autoRefreshToken: true,
      detectSessionInUrl: true,
    },
  }
);
