/**
 * Route guard — redirects unauthenticated users to /login.
 *
 * Shows a full-screen loader while the initial Supabase session is being
 * read from localStorage, preventing a false redirect flash on page refresh.
 */

import { Navigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";

interface ProtectedRouteProps {
  children: React.ReactNode;
}

export function ProtectedRoute({ children }: ProtectedRouteProps) {
  const { session, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen bg-void flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="w-6 h-6 rounded-full border-2 border-ash border-t-teal animate-spin" />
          <p className="text-fog text-[12px]">Verifying session…</p>
        </div>
      </div>
    );
  }

  if (!session) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
}
