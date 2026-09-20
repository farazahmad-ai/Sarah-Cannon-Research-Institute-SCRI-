/**
 * Auth smoke-test dashboard — confirms the full JWT auth chain is working.
 *
 * STATUS: Temporary verification screen (D-8.8).
 * - Not wired to any React Router route — import it manually to use it.
 * - Kept because it's a fast way to verify GET /api/me during development.
 * - TODO(Phase 6.6): Replace with the real clinical trial browser dashboard.
 *   When Phase 6.6 ships, delete this file and the import below.
 */

import { useEffect, useState } from "react";
import { useAuth } from "@/context/AuthContext";
import { api } from "@/lib/api";
import type { AuthenticatedUser } from "@/lib/api";

export function Dashboard() {
  const { user, signOut } = useAuth();
  const [meData, setMeData] = useState<AuthenticatedUser | null>(null);
  const [meError, setMeError] = useState<string | null>(null);
  const [meLoading, setMeLoading] = useState(true);

  useEffect(() => {
    api.me()
      .then(setMeData)
      .catch((e: Error) => setMeError(e.message))
      .finally(() => setMeLoading(false));
  }, []);

  return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center p-4">
      <div className="w-full max-w-lg space-y-4">
        {/* Auth confirmed banner */}
        <div className="bg-emerald-950/60 border border-emerald-700/50 rounded-xl p-5">
          <div className="flex items-center gap-2 mb-3">
            <div className="w-2 h-2 bg-emerald-400 rounded-full animate-pulse" />
            <span className="text-emerald-400 text-sm font-medium">
              Session active
            </span>
          </div>
          <p className="text-slate-300 text-sm">
            Signed in as{" "}
            <span className="text-white font-medium">{user?.email}</span>
          </p>
        </div>

        {/* /api/me result */}
        <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5">
          <p className="text-slate-400 text-xs font-mono mb-3">
            GET /api/me — backend JWT validation
          </p>

          {meLoading && (
            <div className="flex items-center gap-2 text-slate-500 text-sm">
              <div className="w-4 h-4 border-2 border-slate-600 border-t-sky-500 rounded-full animate-spin" />
              Calling backend…
            </div>
          )}

          {meError && (
            <div className="text-red-400 text-sm">
              <span className="font-medium">Error:</span> {meError}
            </div>
          )}

          {meData && (
            <pre className="text-emerald-400 text-xs font-mono bg-slate-950 rounded-lg p-4 overflow-auto">
              {JSON.stringify(meData, null, 2)}
            </pre>
          )}
        </div>

        {/* Sign out */}
        <button
          onClick={signOut}
          className="w-full border border-slate-700 hover:border-slate-600 text-slate-400 hover:text-slate-200 rounded-xl py-2.5 text-sm transition-colors"
        >
          Sign out
        </button>
      </div>
    </div>
  );
}
