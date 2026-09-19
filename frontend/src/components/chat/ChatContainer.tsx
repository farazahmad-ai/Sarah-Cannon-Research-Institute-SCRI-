import { useEffect, useRef, useState } from "react";
import { Sparkles, FileText, AlertCircle } from "lucide-react";
import { api } from "@/lib/api";
import { useChatStream } from "@/lib/useChatStream";
import { ChatMessage } from "./ChatMessage";
import { ChatInput } from "./ChatInput";

interface ChatContainerProps {
  threadId?: string;
  onThreadCreated?: (threadId: string) => void;
}

const QUICK_PROMPTS = [
  {
    title: "Prior Therapy Washout",
    prompt: "What is the prior therapy washout period for study treatment?",
  },
  {
    title: "Brain Metastases",
    prompt: "What are the exclusion criteria regarding treated or active brain metastases?",
  },
  {
    title: "Lab Thresholds (ANC)",
    prompt: "What are the acceptable baseline lab thresholds for absolute neutrophil count (ANC) and platelets?",
  },
];

export function ChatContainer({ threadId, onThreadCreated }: ChatContainerProps) {
  const [historyLoading, setHistoryLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const {
    messages,
    setMessages,
    input,
    handleInputChange,
    handleSubmit,
    sendMessage,
    isLoading,
    stop,
  } = useChatStream({
    threadId,
    onThreadCreated,
    onError: (err) => {
      setErrorMsg(err.message || "An error occurred while streaming response.");
    },
  });

  // Load message history when threadId changes
  useEffect(() => {
    if (!threadId) {
      setMessages([]);
      return;
    }

    let isMounted = true;

    async function loadHistory() {
      try {
        setHistoryLoading(true);
        setErrorMsg(null);
        const history = await api.chat.messages(threadId!);
        if (isMounted) {
          setMessages(
            history.map((m) => ({
              id: m.id,
              role: m.role as "user" | "assistant",
              content: m.content,
              createdAt: new Date(m.created_at),
            }))
          );
        }
      } catch (err) {
        console.error("Failed to load message history:", err);
        if (isMounted) {
          setErrorMsg("Could not load previous message history.");
        }
      } finally {
        if (isMounted) setHistoryLoading(false);
      }
    }

    loadHistory();

    return () => {
      isMounted = false;
    };
  }, [threadId, setMessages]);

  // Auto-scroll to bottom as tokens stream in
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  const handlePromptClick = (promptText: string) => {
    if (isLoading) return;
    sendMessage(promptText);
  };

  return (
    <div className="flex-1 flex flex-col h-full bg-slate-950 text-slate-100 overflow-hidden">
      {/* Top Header */}
      <header className="h-14 border-b border-slate-800/80 px-6 flex items-center justify-between shrink-0 bg-slate-950/80 backdrop-blur">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            <span className="text-xs font-medium text-slate-300">
              Active Screening Session
            </span>
          </div>
          <span className="text-slate-600 text-xs">•</span>
          <span className="text-xs text-slate-400 font-mono">
            {threadId ? `ID: ${threadId.slice(0, 8)}...` : "New Session"}
          </span>
        </div>

        <div className="flex items-center gap-2 text-xs text-slate-400">
          <FileText className="w-3.5 h-3.5 text-sky-400" />
          <span>ClinicalTrials.gov Grounded</span>
        </div>
      </header>

      {/* Messages Scroll Area */}
      <div className="flex-1 overflow-y-auto px-4 md:px-8 py-6 space-y-2 scrollbar-thin scrollbar-thumb-slate-800">
        {historyLoading ? (
          <div className="h-full flex items-center justify-center text-xs text-slate-500">
            Loading message turns...
          </div>
        ) : messages.length === 0 ? (
          /* Empty state */
          <div className="h-full flex flex-col items-center justify-center max-w-2xl mx-auto text-center px-4">
            <div className="w-12 h-12 rounded-2xl bg-sky-600/10 border border-sky-500/20 flex items-center justify-center text-sky-400 mb-4 shadow-inner">
              <Sparkles className="w-6 h-6" />
            </div>

            <h2 className="text-xl font-semibold text-white tracking-tight">
              SCRI Clinical Protocol Assistant
            </h2>
            <p className="text-slate-400 text-sm mt-2 max-w-md leading-relaxed">
              Screen cancer patients against active clinical trial protocols. Ask plain-English questions regarding washouts, organ function, and biomarker criteria.
            </p>

            {/* Quick Prompt Chips */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 w-full mt-8">
              {QUICK_PROMPTS.map((item, idx) => (
                <button
                  key={idx}
                  onClick={() => handlePromptClick(item.prompt)}
                  className="flex flex-col items-start p-3.5 rounded-xl bg-slate-900/80 border border-slate-800 hover:border-sky-500/50 hover:bg-slate-900 text-left transition-all group shadow-xs cursor-pointer"
                >
                  <span className="text-xs font-medium text-sky-400 group-hover:text-sky-300">
                    {item.title}
                  </span>
                  <span className="text-[11px] text-slate-400 mt-1 line-clamp-2">
                    {item.prompt}
                  </span>
                </button>
              ))}
            </div>
          </div>
        ) : (
          /* Render Messages */
          <div className="max-w-4xl mx-auto w-full">
            {messages.map((m, idx) => {
              const isLastAssistant =
                idx === messages.length - 1 && m.role === "assistant";
              return (
                <ChatMessage
                  key={m.id || idx}
                  role={m.role as "user" | "assistant"}
                  content={m.content}
                  createdAt={m.createdAt ? m.createdAt.toISOString() : undefined}
                  isStreaming={isLastAssistant && isLoading}
                />
              );
            })}

            {errorMsg && (
              <div className="flex items-center gap-2 p-3 my-3 bg-red-950/60 border border-red-800/60 rounded-xl text-red-300 text-xs">
                <AlertCircle className="w-4 h-4 shrink-0 text-red-400" />
                <span>{errorMsg}</span>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Bottom Chat Input */}
      <ChatInput
        input={input}
        handleInputChange={handleInputChange}
        handleSubmit={handleSubmit}
        isLoading={isLoading}
        stop={stop}
      />
    </div>
  );
}
