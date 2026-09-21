/**
 * Sidebar — session list, trial catalog navigation, theme toggle, and user profile.
 *
 * Clinical Dusk theme with graphite background and teal accents.
 * Active thread indicated by a left border accent.
 */

import { useEffect, useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import {
  MessageSquare,
  Plus,
  Trash2,
  X,
  LogOut,
  FlaskConical,
  Beaker,
  Sun,
  Moon,
} from "lucide-react";
import { api, type ThreadOut } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { useTheme } from "@/context/ThemeContext";

interface ThreadSidebarProps {
  activeThreadId?: string;
  onSelectThread: (threadId: string) => void;
  onCreateThread: () => Promise<void> | void;
  isCreating?: boolean;
  refreshKey?: number;
}

export function ThreadSidebar({
  activeThreadId,
  onSelectThread,
  onCreateThread,
  isCreating = false,
  refreshKey = 0,
}: ThreadSidebarProps) {
  const { user, signOut } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const navigate = useNavigate();
  const location = useLocation();
  const [threads, setThreads] = useState<ThreadOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);

  const isTrialsPage = location.pathname === "/trials";

  const fetchThreads = async () => {
    try {
      setLoading(true);
      const data = await api.chat.threads();
      setThreads(data);
    } catch (err) {
      console.error("Failed to fetch threads:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchThreads();
  }, [activeThreadId, refreshKey]);

  const handleDeleteClick = (e: React.MouseEvent, threadId: string) => {
    e.stopPropagation();
    setConfirmDeleteId(threadId);
  };

  const handleCancelDelete = (e: React.MouseEvent) => {
    e.stopPropagation();
    setConfirmDeleteId(null);
  };

  const handleConfirmDelete = async (e: React.MouseEvent, threadId: string) => {
    e.stopPropagation();
    try {
      setDeletingId(threadId);
      await api.chat.deleteThread(threadId);
      setThreads((prev) => prev.filter((t) => t.id !== threadId));
      if (activeThreadId === threadId) {
        onSelectThread("");
      }
    } catch (err) {
      console.error("Failed to delete thread:", err);
    } finally {
      setDeletingId(null);
      setConfirmDeleteId(null);
    }
  };

  function relativeTime(dateStr: string): string {
    const diff = Date.now() - new Date(dateStr).getTime();
    const minutes = Math.floor(diff / 60_000);
    if (minutes < 1) return "just now";
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    if (days < 30) return `${days}d ago`;
    return new Date(dateStr).toLocaleDateString([], {
      month: "short",
      day: "numeric",
    });
  }

  return (
    <aside className="w-64 bg-graphite border-r border-ash flex flex-col h-full shrink-0 select-none">
      {/* ── Brand + New Session ── */}
      <div className="p-3.5 pb-3">
        <div className="flex items-center gap-2 mb-3.5">
          <div className="w-7 h-7 rounded-lg bg-teal-dim border border-teal-border flex items-center justify-center text-teal">
            <Beaker className="w-3.5 h-3.5" />
          </div>
          <div>
            <h1 className="font-semibold text-cloud text-[13px] tracking-tight leading-none">
              SCRI Copilot
            </h1>
            <p className="text-[10px] text-fog mt-0.5">
              Protocol assistant
            </p>
          </div>
        </div>

        <button
          onClick={onCreateThread}
          disabled={isCreating}
          className="w-full flex items-center justify-center gap-1.5 bg-teal hover:bg-teal/85 disabled:opacity-40 text-void font-medium text-[12px] px-3 py-2 rounded-lg transition-all cursor-pointer disabled:cursor-not-allowed"
        >
          <Plus className="w-3.5 h-3.5" />
          <span>New session</span>
        </button>
      </div>

      {/* ── Thread List ── */}
      <div className="flex-1 overflow-y-auto px-1.5 pb-2 scrollbar-clinical">
        <div className="px-2 py-1.5 text-[10px] font-medium text-fog">
          Sessions
        </div>

        {loading && threads.length === 0 ? (
          <div className="px-3 py-4 text-center text-[11px] text-fog/60">
            Loading...
          </div>
        ) : threads.length === 0 ? (
          <div className="px-3 py-4 text-center text-[11px] text-fog/60">
            No sessions yet
          </div>
        ) : (
          <div className="space-y-0.5">
            {threads.map((thread) => {
              const isActive = thread.id === activeThreadId;
              return (
                <div
                  key={thread.id}
                  onClick={() => onSelectThread(thread.id)}
                  className={`group relative flex items-center justify-between gap-1.5 px-2.5 py-2 rounded-md cursor-pointer transition-colors text-[12px] ${
                    isActive
                      ? "bg-teal-dim/50 text-cloud border-l-2 border-l-teal ml-0"
                      : "text-fog hover:bg-ash/30 hover:text-cloud border-l-2 border-l-transparent"
                  }`}
                >
                  <div className="flex items-center gap-2 min-w-0 flex-1">
                    <MessageSquare
                      className={`w-3.5 h-3.5 shrink-0 ${
                        isActive ? "text-teal" : "text-fog/60"
                      }`}
                    />
                    <div className="truncate flex-1 min-w-0">
                      <div className="truncate text-[12px]">{thread.title}</div>
                      <div className="text-[10px] text-fog/50 mt-0.5">
                        {relativeTime(thread.created_at)}
                      </div>
                    </div>
                  </div>

                  {confirmDeleteId === thread.id ? (
                    <div
                      className="flex items-center gap-1 shrink-0"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <button
                        type="button"
                        onClick={(e) => handleConfirmDelete(e, thread.id)}
                        disabled={deletingId === thread.id}
                        className="px-1.5 py-0.5 rounded bg-danger hover:bg-danger/85 text-void font-semibold text-[10px] transition-colors cursor-pointer"
                        title="Confirm deletion"
                      >
                        {deletingId === thread.id ? "..." : "Delete"}
                      </button>
                      <button
                        type="button"
                        onClick={handleCancelDelete}
                        className="p-1 rounded text-fog hover:text-cloud transition-colors cursor-pointer"
                        title="Cancel"
                      >
                        <X className="w-3 h-3" />
                      </button>
                    </div>
                  ) : (
                    <button
                      type="button"
                      onClick={(e) => handleDeleteClick(e, thread.id)}
                      disabled={deletingId === thread.id}
                      className={`p-1.5 rounded transition-all shrink-0 cursor-pointer ${
                        isActive
                          ? "opacity-60 hover:opacity-100 text-fog hover:text-danger hover:bg-ash/40"
                          : "opacity-0 group-hover:opacity-100 text-fog/50 hover:text-danger hover:bg-ash/40"
                      }`}
                      title="Delete session"
                    >
                      {deletingId === thread.id ? (
                        <div className="w-3 h-3 border-2 border-ash border-t-danger rounded-full animate-spin" />
                      ) : (
                        <Trash2 className="w-3.5 h-3.5" />
                      )}
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* ── Trial Catalog Nav ── */}
      <div className="px-1.5 pb-1">
        <button
          type="button"
          onClick={() => (isTrialsPage ? navigate("/chat") : navigate("/trials"))}
          className={`w-full flex items-center justify-between px-2.5 py-2 rounded-md text-[12px] transition-colors cursor-pointer ${
            isTrialsPage
              ? "bg-teal-dim/50 text-teal font-medium"
              : "text-fog hover:text-cloud hover:bg-ash/30"
          }`}
          title={isTrialsPage ? "Return to screening chat" : "Open trial catalog"}
        >
          <div className="flex items-center gap-2">
            <FlaskConical className="w-3.5 h-3.5" />
            <span>Trial catalog</span>
          </div>
          {isTrialsPage && (
            <span className="text-[10px] text-teal/70 px-1 py-0.5 rounded bg-teal/10">
              Open
            </span>
          )}
        </button>
      </div>

      {/* ── User Footer with Theme Toggle ── */}
      <div className="p-2.5 border-t border-ash flex items-center justify-between">
        <div className="flex items-center gap-2 min-w-0">
          <div className="w-6 h-6 rounded-md bg-ash flex items-center justify-center text-fog text-[10px] font-semibold shrink-0">
            {user?.email?.charAt(0).toUpperCase() ?? "?"}
          </div>
          <span className="text-[11px] text-fog truncate">
            {user?.email ?? "—"}
          </span>
        </div>

        <div className="flex items-center gap-1 shrink-0">
          {/* Theme toggle */}
          <button
            type="button"
            onClick={toggleTheme}
            className="p-1 rounded text-fog/50 hover:text-cloud hover:bg-ash/40 transition-colors cursor-pointer"
            title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
          >
            {theme === "dark" ? (
              <Sun className="w-3.5 h-3.5" />
            ) : (
              <Moon className="w-3.5 h-3.5" />
            )}
          </button>

          {/* Sign out */}
          <button
            onClick={() => signOut()}
            className="p-1 rounded text-fog/50 hover:text-danger transition-colors cursor-pointer"
            title="Sign out"
          >
            <LogOut className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </aside>
  );
}
