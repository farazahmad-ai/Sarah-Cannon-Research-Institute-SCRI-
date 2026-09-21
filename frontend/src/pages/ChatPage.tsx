/**
 * Chat page — top-level layout for /chat and /chat/:threadId.
 *
 * Split layout: ThreadSidebar on left, ChatContainer on right.
 * Uses the void background from Clinical Dusk palette.
 */

import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "@/lib/api";
import { ThreadSidebar } from "@/components/chat/ThreadSidebar";
import { ChatContainer } from "@/components/chat/ChatContainer";

export function ChatPage() {
  const { threadId } = useParams<{ threadId?: string }>();
  const navigate = useNavigate();
  const [sidebarRefreshKey, setSidebarRefreshKey] = useState(0);

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
    <div className="h-screen w-screen flex overflow-hidden bg-void font-sans">
      <ThreadSidebar
        activeThreadId={threadId}
        onSelectThread={handleSelectThread}
        onCreateThread={handleCreateThread}
        refreshKey={sidebarRefreshKey}
      />
      <main className="flex-1 flex flex-col h-full min-w-0 overflow-hidden">
        <ChatContainer
          threadId={threadId}
          onThreadCreated={(id) => {
            navigate(`/chat/${id}`);
            handleThreadActivity();
          }}
          onStreamComplete={handleThreadActivity}
        />
      </main>
    </div>
  );
}
