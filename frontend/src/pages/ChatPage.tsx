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
  const [isCreating, setIsCreating] = useState(false);

  const handleSelectThread = (id: string) => {
    if (!id) {
      navigate("/chat");
    } else {
      navigate(`/chat/${id}`);
    }
  };

  const handleCreateThread = async () => {
    try {
      setIsCreating(true);
      const newThread = await api.chat.createThread();
      navigate(`/chat/${newThread.id}`);
    } catch (err) {
      console.error("Failed to create thread:", err);
    } finally {
      setIsCreating(false);
    }
  };

  return (
    <div className="h-screen w-screen flex overflow-hidden bg-void font-sans">
      <ThreadSidebar
        activeThreadId={threadId}
        onSelectThread={handleSelectThread}
        onCreateThread={handleCreateThread}
        isCreating={isCreating}
      />
      <main className="flex-1 flex flex-col h-full min-w-0 overflow-hidden">
        <ChatContainer
          threadId={threadId}
          onThreadCreated={(id) => navigate(`/chat/${id}`)}
        />
      </main>
    </div>
  );
}
