/**
 * Chat page — top-level layout for /chat and /chat/:threadId.
 *
 * Split layout: ThreadSidebar on left, ChatContainer on right.
 * Uses the void background from Clinical Dusk palette.
 */

import { useState, useCallback, useRef } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "@/lib/api";
import { ThreadSidebar } from "@/components/chat/ThreadSidebar";
import { ChatContainer } from "@/components/chat/ChatContainer";

const SIDEBAR_OPEN_KEY = "scri-sidebar-open";
const SIDEBAR_WIDTH_KEY = "scri-sidebar-width";

export function ChatPage() {
  const { threadId } = useParams<{ threadId?: string }>();
  const navigate = useNavigate();
  const [sidebarRefreshKey, setSidebarRefreshKey] = useState(0);

  const [isSidebarOpen, setIsSidebarOpen] = useState<boolean>(() => {
    const saved = localStorage.getItem(SIDEBAR_OPEN_KEY);
    return saved !== null ? saved === "true" : true;
  });

  const [sidebarWidth, setSidebarWidth] = useState<number>(() => {
    const saved = localStorage.getItem(SIDEBAR_WIDTH_KEY);
    return saved ? Math.max(200, Math.min(440, Number(saved))) : 260;
  });

  const isDraggingRef = useRef(false);

  const toggleSidebar = useCallback(() => {
    setIsSidebarOpen((prev) => {
      const next = !prev;
      localStorage.setItem(SIDEBAR_OPEN_KEY, String(next));
      return next;
    });
  }, []);

  const handleResizeStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    isDraggingRef.current = true;
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";

    const onMouseMove = (moveEvent: MouseEvent) => {
      if (!isDraggingRef.current) return;
      const newWidth = Math.max(200, Math.min(440, moveEvent.clientX));
      setSidebarWidth(newWidth);
    };

    const onMouseUp = (upEvent: MouseEvent) => {
      isDraggingRef.current = false;
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
      const finalWidth = Math.max(200, Math.min(440, upEvent.clientX));
      localStorage.setItem(SIDEBAR_WIDTH_KEY, String(finalWidth));
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("mouseup", onMouseUp);
    };

    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("mouseup", onMouseUp);
  }, []);

  const handleSelectThread = (id: string) => {
    if (!id) {
      navigate("/chat");
    } else {
      navigate(`/chat/${id}`);
    }
  };

  const handleCreateThread = async () => {
    try {
      const newThread = await api.chat.createThread("New session");
      navigate(`/chat/${newThread.id}`);
      handleThreadActivity();
    } catch (err) {
      console.error("Failed to create thread:", err);
    }
  };

  const handleThreadActivity = () => {
    setSidebarRefreshKey((k) => k + 1);
  };

  return (
    <div className="h-screen w-screen flex overflow-hidden bg-void font-sans select-none">
      <ThreadSidebar
        activeThreadId={threadId}
        onSelectThread={handleSelectThread}
        onCreateThread={handleCreateThread}
        refreshKey={sidebarRefreshKey}
        isOpen={isSidebarOpen}
        onToggleOpen={toggleSidebar}
        width={sidebarWidth}
        onResizeStart={handleResizeStart}
      />
      <main className="flex-1 flex flex-col h-full min-w-0 overflow-hidden">
        <ChatContainer
          threadId={threadId}
          onThreadCreated={(id) => {
            navigate(`/chat/${id}`);
            handleThreadActivity();
          }}
          onStreamComplete={handleThreadActivity}
          isSidebarOpen={isSidebarOpen}
          onToggleSidebar={toggleSidebar}
        />
      </main>
    </div>
  );
}
