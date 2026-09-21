/**
 * Login page — institutional email + password authentication.
 *
 * Uses Supabase signInWithPassword. No third-party OAuth or magic links —
 * coordinators authenticate with their SCRI / HCA Healthcare credentials
 * provisioned by an admin directly in the Supabase dashboard.
 *
 * Clinical Dusk theme with teal accents.
 */

import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { supabase } from "@/lib/supabase";
import { useAuth } from "@/context/AuthContext";
import { useTheme } from "@/context/ThemeContext";
import { Beaker, Sun, Moon } from "lucide-react";

export function Login() {
  const { session } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const navigate = useNavigate();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // Already authenticated → skip login screen.
  useEffect(() => {
    if (session) navigate("/", { replace: true });
  }, [session, navigate]);

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    const { error: authError } = await supabase.auth.signInWithPassword({
      email,
      password,
    });

    if (authError) {
      // Supabase returns "Invalid login credentials" for wrong email/password —
      // surface it directly so coordinators understand the failure reason.
      setError(authError.message);
      setLoading(false);
      return;
    }

    // onAuthStateChange in AuthContext will pick up the new session;
    // the useEffect above will then redirect to /.
  };

  return (
    <div className="min-h-screen bg-void flex items-center justify-center p-4 relative">
      {/* Theme toggle in top right */}
      <div className="absolute top-4 right-4 z-10">
        <button
          type="button"
          onClick={toggleTheme}
          className="p-2 rounded-lg bg-graphite border border-ash text-fog hover:text-cloud hover:bg-ash/40 transition-colors cursor-pointer"
          title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
        >
          {theme === "dark" ? (
            <Sun className="w-4 h-4" />
          ) : (
            <Moon className="w-4 h-4" />
          )}
        </button>
      </div>
      {/* Subtle grid background */}
      <div
        className="absolute inset-0 opacity-[0.02]"
        style={{
          backgroundImage:
            "linear-gradient(var(--fog) 1px, transparent 1px), linear-gradient(90deg, var(--fog) 1px, transparent 1px)",
          backgroundSize: "48px 48px",
        }}
      />

      <div className="relative w-full max-w-sm">
        {/* Header */}
        <div className="text-center mb-7">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-xl bg-teal-dim border border-teal-border mb-4">
            <Beaker className="w-6 h-6 text-teal" />
          </div>
          <h1 className="text-[20px] font-semibold text-cloud tracking-tight">
            SCRI Copilot
          </h1>
          <p className="text-fog text-[12px] mt-1">
            Sarah Cannon Research Institute
          </p>
        </div>

        {/* Card */}
        <div className="bg-graphite border border-ash rounded-xl p-6">
          <h2 className="text-cloud text-[14px] font-medium mb-5">
            Sign in to your account
          </h2>

          {/* Error banner */}
          {error && (
            <div className="flex items-start gap-2.5 bg-danger-dim border border-danger/30 rounded-lg px-3.5 py-2.5 mb-4">
              <svg
                className="w-3.5 h-3.5 text-danger mt-0.5 shrink-0"
                fill="currentColor"
                viewBox="0 0 20 20"
              >
                <path
                  fillRule="evenodd"
                  d="M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0zm-8-5a.75.75 0 0 1 .75.75v4.5a.75.75 0 0 1-1.5 0v-4.5A.75.75 0 0 1 10 5zm0 10a1 1 0 1 0 0-2 1 1 0 0 0 0 2z"
                  clipRule="evenodd"
                />
              </svg>
              <p className="text-danger text-[12px]">{error}</p>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-3.5">
            <div>
              <label
                htmlFor="email"
                className="block text-[12px] font-medium text-fog mb-1.5"
              >
                Institutional email
              </label>
              <input
                id="email"
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@scri.com"
                className="w-full bg-slate-surface border border-ash rounded-lg px-3 py-2 text-cloud placeholder-fog/40 text-[13px] focus:outline-none focus:ring-1 focus:ring-teal-border focus:border-teal-border transition"
              />
            </div>

            <div>
              <label
                htmlFor="password"
                className="block text-[12px] font-medium text-fog mb-1.5"
              >
                Password
              </label>
              <input
                id="password"
                type="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full bg-slate-surface border border-ash rounded-lg px-3 py-2 text-cloud placeholder-fog/40 text-[13px] focus:outline-none focus:ring-1 focus:ring-teal-border focus:border-teal-border transition"
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-teal hover:bg-teal/85 disabled:opacity-40 disabled:cursor-not-allowed text-void font-medium rounded-lg py-2.5 text-[13px] transition-colors flex items-center justify-center gap-2 mt-1 cursor-pointer"
            >
              {loading ? (
                <>
                  <div className="w-3.5 h-3.5 border-2 border-void/30 border-t-void rounded-full animate-spin" />
                  Signing in…
                </>
              ) : (
                "Sign in"
              )}
            </button>
          </form>
        </div>

        {/* Footer */}
        <p className="text-center text-fog/40 text-[10px] mt-5 leading-relaxed">
          For authorized SCRI clinical research staff only.
          <br />
          Contact your administrator to request access.
        </p>
      </div>
    </div>
  );
}
