/**
 * Trials page — full-page trial catalog accessible from /trials.
 *
 * Shares the sidebar layout with ChatPage. Renders the TrialList
 * component in the main content area.
 */

import { useNavigate } from "react-router-dom";
import { ThreadSidebar } from "@/components/chat/ThreadSidebar";
import { TrialList } from "@/components/trials/TrialList";

export function TrialsPage() {
  const navigate = useNavigate();

  return (
    <div className="h-screen w-screen flex overflow-hidden bg-void font-sans">
      <ThreadSidebar
        onSelectThread={(id) => navigate(`/chat/${id}`)}
        onCreateThread={async () => {
          navigate("/chat");
        }}
      />
      <main className="flex-1 flex flex-col h-full min-w-0 overflow-hidden bg-void">
        <TrialList />
      </main>
    </div>
  );
}
