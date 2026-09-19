import { useEffect, useState } from "react";
import { MessageSquare, Plus, Trash2, LogOut, ShieldAlert } from "lucide-react";
import { api, type ThreadOut } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";

interface ThreadSidebarProps {
  activeThreadId?: string;
  onSelectThread: (threadId: string) => void;
  onCreateThread: () => Promise<void>;
  isCreating?: boolean;
}

export function ThreadSidebar({
  activeThreadId,
  onSelectThread,
  onCreateThread,
  isCreating = false,
}: ThreadSidebarProps) {
  const { user, signOut } = useAuth();
  const [threads, setThreads] = useState<ThreadOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const fetchThreads = async () => {
    try {
      setLoading(true);
      const data = await api.chat.threads();
      setThreads(data);
    } catch (err) {
      console.error("Failed to fetch chat threads:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchThreads();
  }, [activeThreadId]);

  const handleDelete = async (e: React.MouseEvent, threadId: string) => {
    e.stopPropagation();
    if (!confirm("Are you sure you want to delete this screening session?")) {
      return;
    }

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
    }
  };

  return (
    <aside className="w-72 md:w-80 bg-slate-950 border-r border-slate-800 flex flex-col h-full shrink-0 select-none">
      {/* Header */}
      <div className="p-4 border-b border-slate-800/80">
        <div className="flex items-center gap-2.5 mb-4">
          <div className="w-8 h-8 rounded-xl bg-sky-600/20 border border-sky-500/30 flex items-center justify-center text-sky-400">
            <svg
              className="w-4 h-4"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M9.75 3.104v5.714a2.25 2.25 0 0 1-.659 1.591L5 14.5M9.75 3.104c-.251.023-.501.05-.75.082m.75-.082a24.301 24.301 0 0 1 4.5 0m0 0v5.714c0 .597.237 1.17.659 1.591L19.8 15.3M14.25 3.104c.251.023.501.05.75.082M19.8 15.3l-1.57.393A9.065 9.065 0 0 1 12 15a9.065 9.065 0 0 0-6.23-.693L5 14.5m14.8.8 1.402 1.402c1 1 .03 2.798-1.442 2.798H4.24c-1.47 0-2.44-1.798-1.442-2.798L4.2 15.3"
              />
            </svg>
          </div>
          <div>
            <h1 className="font-semibold text-white text-sm tracking-tight leading-none">
              SCRI Copilot
            </h1>
            <p className="text-[11px] text-slate-400 mt-1">
              Oncology Protocol Assistant
            </p>
          </div>
        </div>

        <button
          onClick={onCreateThread}
          disabled={isCreating}
          className="w-full flex items-center justify-center gap-2 bg-sky-600 hover:bg-sky-500 disabled:opacity-50 text-white font-medium text-xs px-3.5 py-2.5 rounded-xl transition-all shadow-sm cursor-pointer disabled:cursor-not-allowed"
        >
          <Plus className="w-4 h-4" />
          <span>New Screening Session</span>
        </button>
      </div>

      {/* Thread list */}
      <div className="flex-1 overflow-y-auto px-2 py-3 space-y-1 scrollbar-thin scrollbar-thumb-slate-800">
        <div className="px-2 pb-1 text-[11px] font-medium text-slate-500 uppercase tracking-wider">
          Screening History
        </div>

        {loading && threads.length === 0 ? (
          <div className="p-4 text-center text-xs text-slate-500">
            Loading sessions...
          </div>
        ) : threads.length === 0 ? (
          <div className="p-4 text-center text-xs text-slate-500">
            No past sessions. Click "New Screening Session" to start.
          </div>
        ) : (
          threads.map((thread) => {
            const isActive = thread.id === activeThreadId;
            return (
              <div
                key={thread.id}
                onClick={() => onSelectThread(thread.id)}
                className={`group relative flex items-center justify-between gap-2 px-3 py-2.5 rounded-xl cursor-pointer transition-colors text-xs ${
                  isActive
                    ? "bg-slate-800/90 text-white font-medium border border-sky-500/30 shadow-xs"
                    : "text-slate-400 hover:bg-slate-900 hover:text-slate-200 border border-transparent"
                }`}
              >
                <div className="flex items-center gap-2.5 min-w-0 flex-1">
                  <MessageSquare
                    className={`w-4 h-4 shrink-0 ${
                      isActive ? "text-sky-400" : "text-slate-500"
                    }`}
                  />
                  <div className="truncate flex-1">
                    <div className="truncate">{thread.title}</div>
                    <div className="text-[10px] text-slate-500 font-normal mt-0.5">
                      {new Date(thread.created_at).toLocaleDateString([], {
                        month: "short",
                        day: "numeric",
                      })}
                    </div>
                  </div>
                </div>

                <button
                  type="button"
                  onClick={(e) => handleDelete(e, thread.id)}
                  disabled={deletingId === thread.id}
                  className="opacity-0 group-hover:opacity-100 p-1 rounded-md text-slate-500 hover:text-red-400 hover:bg-slate-800/60 transition-all shrink-0"
                  title="Delete session"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            );
          })
        )}
      </div>

      {/* Footer / User Profile */}
      <div className="p-3 border-t border-slate-800/80 bg-slate-950/80 flex items-center justify-between">
        <div className="flex items-center gap-2.5 min-w-0 pr-2">
          <div className="w-7 h-7 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center text-sky-400 text-xs font-semibold shrink-0">
            {user?.email?.charAt(0).toUpperCase() ?? "C"}
          </div>
          <div className="min-w-0">
            <div className="text-xs font-medium text-slate-200 truncate">
              {user?.email ?? "Coordinator"}
            </div>
            <div className="flex items-center gap-1 text-[10px] text-sky-400 font-medium">
              <ShieldAlert className="w-3 h-3" />
              <span>Verified CRC</span>
            </div>
          </div>
        </div>

        <button
          onClick={() => signOut()}
          className="p-1.5 rounded-lg text-slate-400 hover:text-red-400 hover:bg-slate-900 transition-colors shrink-0"
          title="Sign out"
        >
          <LogOut className="w-4 h-4" />
        </button>
      </div>
    </aside>
  );
}
