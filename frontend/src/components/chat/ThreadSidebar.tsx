/**
 * Sidebar — session list, trial catalog navigation, theme toggle, and user profile.
 *
 * Clinical Dusk theme with graphite background and teal accents.
 * Active thread indicated by a left border accent.
 */

import { useEffect, useState } from "react";
import {
  MessageSquare,
  Plus,
  Trash2,
  X,
  LogOut,
  PanelLeftClose,
} from "lucide-react";
import { api, type ThreadOut } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";

interface ThreadSidebarProps {
  activeThreadId?: string;
  onSelectThread: (threadId: string) => void;
  onCreateThread: () => Promise<void> | void;
  isCreating?: boolean;
  refreshKey?: number;
  isOpen?: boolean;
  onToggleOpen?: () => void;
  width?: number;
  onResizeStart?: (e: React.MouseEvent) => void;
}

export function ThreadSidebar({
  activeThreadId,
  onSelectThread,
  onCreateThread,
  isCreating = false,
  refreshKey = 0,
  isOpen = true,
  onToggleOpen,
  width = 260,
  onResizeStart,
}: ThreadSidebarProps) {
  const { user, signOut } = useAuth();
  const [threads, setThreads] = useState<ThreadOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);

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

  if (!isOpen) return null;

  return (
    <aside
      style={{ width: `${width}px` }}
      className="relative bg-graphite border-r border-ash flex flex-col h-full shrink-0 select-none transition-[width] duration-75"
    >
      {/* Drag handle on right edge */}
      <div
        onMouseDown={onResizeStart}
        className="absolute top-0 right-0 bottom-0 w-1.5 cursor-col-resize hover:bg-teal/50 active:bg-teal transition-colors z-30"
        title="Drag to resize sidebar"
      />

      {/* ── Brand + New Session ── */}
      <div className="p-3.5 pb-3">
        <div className="flex items-center justify-between gap-2 mb-3.5">
          <div className="flex items-center gap-2.5 min-w-0">
            <div className="w-7 h-7 rounded-lg bg-slate-surface border border-ash flex items-center justify-center p-0.5 shrink-0 overflow-hidden shadow-xs">
              <img
                src="/logo-genes.png"
                alt="SCRI Logo"
                className="w-full h-full object-contain"
              />
            </div>
            <div className="min-w-0">
              <h1 className="font-semibold text-cloud text-[13px] tracking-tight leading-none truncate">
                SCRI Copilot
              </h1>
              <p className="text-[10px] text-fog mt-0.5 truncate">
                Protocol Assistant
              </p>
            </div>
          </div>

          {onToggleOpen && (
            <button
              type="button"
              onClick={onToggleOpen}
              className="p-1 rounded-md text-fog hover:text-cloud hover:bg-ash/40 transition-colors cursor-pointer shrink-0"
              title="Close sidebar"
              aria-label="Close sidebar"
            >
              <PanelLeftClose className="w-4 h-4" />
            </button>
          )}
        </div>

        <button
          onClick={onCreateThread}
          disabled={isCreating}
          className="w-full flex items-center justify-center gap-1.5 bg-teal hover:bg-teal/85 disabled:opacity-40 text-void font-semibold text-[12px] px-3 py-2 rounded-lg transition-all cursor-pointer disabled:cursor-not-allowed shadow-xs"
        >
          <Plus className="w-3.5 h-3.5 stroke-[2.5]" />
          <span>New session</span>
        </button>
      </div>

      {/* ── Thread List ── */}
      <div className="flex-1 overflow-y-auto px-2 pb-2 scrollbar-clinical">
        <div className="px-2 py-1.5 text-[11px] font-semibold text-fog/80 uppercase tracking-wider">
          Sessions
        </div>

        {loading && threads.length === 0 ? (
          <div className="px-3 py-4 text-center text-[11px] text-fog">
            Loading sessions...
          </div>
        ) : threads.length === 0 ? (
          <div className="px-3 py-4 text-center text-[11px] text-fog">
            No sessions yet
          </div>
        ) : (
          <div className="space-y-1">
            {threads.map((thread) => {
              const isActive = thread.id === activeThreadId;
              return (
                <div
                  key={thread.id}
                  onClick={() => onSelectThread(thread.id)}
                  className={`group relative flex items-center justify-between gap-1.5 px-3 py-2 rounded-lg cursor-pointer transition-all text-[12px] border ${
                    isActive
                      ? "bg-slate-surface text-cloud border-ash shadow-xs"
                      : "text-cloud/80 hover:text-cloud hover:bg-ash/30 border-transparent"
                  }`}
                >
                  <div className="flex items-center gap-2 min-w-0 flex-1">
                    <MessageSquare
                      className={`w-3.5 h-3.5 shrink-0 ${
                        isActive ? "text-teal" : "text-fog"
                      }`}
                    />
                    <div className="truncate flex-1 min-w-0">
                      <div className={`truncate text-[12px] ${isActive ? "font-semibold text-cloud" : "font-normal"}`}>
                        {thread.title}
                      </div>
                      <div className="text-[10px] text-fog mt-0.5">
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

      {/* ── User Footer ── */}
      <div className="p-2.5 border-t border-ash flex items-center justify-between">
        <div className="flex items-center gap-2 min-w-0">
          <div className="w-6 h-6 rounded-md bg-ash flex items-center justify-center text-fog text-[10px] font-semibold shrink-0">
            {user?.email?.charAt(0).toUpperCase() ?? "?"}
          </div>
          <span className="text-[11px] text-fog truncate">
            {user?.email ?? "—"}
          </span>
        </div>

        <button
          onClick={() => signOut()}
          className="p-1.5 rounded text-fog hover:text-danger hover:bg-ash/40 transition-colors cursor-pointer"
          title="Sign out"
        >
          <LogOut className="w-3.5 h-3.5" />
        </button>
      </div>
    </aside>
  );
}
