/**
 * Main chat conversation view — messages area + input.
 *
 * No top header bar (redundant with sidebar context).
 * Clean empty state with centered welcome and 3 suggested prompts.
 * Passes citation data through to ChatMessage for interactive pills.
 * Prevents navigation race conditions when starting a new session.
 */

import { useEffect, useRef, useState, useCallback } from "react";
import { AlertCircle } from "lucide-react";
import { api } from "@/lib/api";
import { useChatStream } from "@/lib/useChatStream";
import { ChatMessage } from "./ChatMessage";
import { ChatInput } from "./ChatInput";
import type { CitationOut } from "@/lib/api";

interface ChatContainerProps {
  threadId?: string;
  onThreadCreated?: (threadId: string) => void;
  onStreamComplete?: (threadId: string) => void;
}

const QUICK_PROMPTS = [
  {
    title: "Prior therapy washout",
    prompt: "What is the prior therapy washout period for study treatment?",
  },
  {
    title: "Brain metastases",
    prompt: "What are the exclusion criteria regarding treated or active brain metastases?",
  },
  {
    title: "Lab thresholds",
    prompt: "What are the acceptable baseline lab thresholds for ANC and platelets?",
  },
];

export function ChatContainer({
  threadId,
  onThreadCreated,
  onStreamComplete,
}: ChatContainerProps) {
  const [historyLoading, setHistoryLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  /** Citation data keyed by message ID for interactive pills. */
  const [citationsByMessage, setCitationsByMessage] = useState<
    Map<string, CitationOut[]>
  >(new Map());
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Track thread ID created by the current streaming interaction to prevent wiping messages
  const justCreatedThreadIdRef = useRef<string | null>(null);

  // Map citations by assistant turn index as a resilient fallback for client/server ID mismatch (H2)
  const [citationsByIndex, setCitationsByIndex] = useState<Map<number, CitationOut[]>>(new Map());
  const setMessagesRef = useRef<((messages: any[]) => void) | null>(null);

  const handleStreamComplete = useCallback(async (completedThreadId: string) => {
    try {
      // Reload history to retrieve verified citations and DB message IDs saved by backend
      const history = await api.chat.messages(completedThreadId);
      const cMap = new Map<string, CitationOut[]>();
      const cIndexMap = new Map<number, CitationOut[]>();
      let aIdx = 0;

      for (const m of history) {
        if (m.citations && m.citations.length > 0) {
          cMap.set(m.id, m.citations);
        }
        if (m.role === "assistant") {
          if (m.citations && m.citations.length > 0) {
            cIndexMap.set(aIdx, m.citations);
          }
          aIdx++;
        }
      }
      setCitationsByMessage(cMap);
      setCitationsByIndex(cIndexMap);

      // Reconcile client-generated temporary IDs with authoritative DB messages
      if (setMessagesRef.current) {
        setMessagesRef.current(
          history.map((m) => ({
            id: m.id,
            role: m.role as "user" | "assistant",
            content: m.content,
            createdAt: new Date(m.created_at),
          }))
        );
      }
      onStreamComplete?.(completedThreadId);
    } catch (e) {
      console.error("Failed to load citations on stream complete:", e);
    }
  }, [onStreamComplete]);

  const handleThreadCreated = useCallback(
    (newId: string) => {
      justCreatedThreadIdRef.current = newId;
      onThreadCreated?.(newId);
    },
    [onThreadCreated]
  );

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
    onThreadCreated: handleThreadCreated,
    onStreamComplete: handleStreamComplete,
    onError: (err) => {
      setErrorMsg(err.message || "An error occurred while streaming.");
    },
  });

  setMessagesRef.current = setMessages;

  // Load message history + citations when threadId changes
  useEffect(() => {
    if (!threadId) {
      setMessages([]);
      setCitationsByMessage(new Map());
      setCitationsByIndex(new Map());
      justCreatedThreadIdRef.current = null;
      return;
    }

    // If this threadId was just created by the current active stream,
    // do not wipe out the in-flight conversation!
    if (justCreatedThreadIdRef.current === threadId) {
      justCreatedThreadIdRef.current = null;
      return;
    }

    let isMounted = true;

    async function loadHistory() {
      try {
        setHistoryLoading(true);
        setErrorMsg(null);
        const history = await api.chat.messages(threadId!);

        if (isMounted) {
          // Build citation lookup
          const cMap = new Map<string, CitationOut[]>();
          const cIndexMap = new Map<number, CitationOut[]>();
          let aIdx = 0;

          for (const m of history) {
            if (m.citations && m.citations.length > 0) {
              cMap.set(m.id, m.citations);
            }
            if (m.role === "assistant") {
              if (m.citations && m.citations.length > 0) {
                cIndexMap.set(aIdx, m.citations);
              }
              aIdx++;
            }
          }
          setCitationsByMessage(cMap);
          setCitationsByIndex(cIndexMap);

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
        if (isMounted) setErrorMsg("Could not load previous messages.");
      } finally {
        if (isMounted) setHistoryLoading(false);
      }
    }

    loadHistory();
    return () => {
      isMounted = false;
    };
  }, [threadId, setMessages]);

  // Auto-scroll as tokens stream in
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  const handlePromptClick = (promptText: string) => {
    if (isLoading) return;
    sendMessage(promptText);
  };

  return (
    <div className="flex-1 flex flex-col h-full bg-void overflow-hidden">
      {/* Messages scroll area */}
      <div className="flex-1 overflow-y-auto scrollbar-clinical">
        {historyLoading ? (
          <div className="h-full flex items-center justify-center text-[12px] text-fog">
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 border-2 border-ash border-t-teal rounded-full animate-spin" />
              Loading messages...
            </div>
          </div>
        ) : messages.length === 0 ? (
          /* ── Empty State ── */
          <div className="h-full flex flex-col items-center justify-center max-w-xl mx-auto text-center px-6">
            <h2 className="text-[18px] font-semibold text-cloud tracking-tight">
              Clinical protocol assistant
            </h2>
            <p className="text-[13px] text-fog mt-2 max-w-sm leading-relaxed">
              Ask plain-English questions about clinical trial eligibility criteria, washout periods, and biomarker thresholds.
            </p>

            {errorMsg && (
              <div className="flex items-center gap-2 p-3 mt-4 bg-danger-dim border border-danger/30 rounded-lg text-danger text-[12px] max-w-md text-left">
                <AlertCircle className="w-3.5 h-3.5 shrink-0" />
                <span>{errorMsg}</span>
              </div>
            )}

            {/* Suggested prompts */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5 w-full mt-7">
              {QUICK_PROMPTS.map((item, idx) => (
                <button
                  key={idx}
                  onClick={() => handlePromptClick(item.prompt)}
                  className="flex flex-col items-start p-3 rounded-lg bg-slate-surface border border-ash hover:border-teal-border text-left transition-all group cursor-pointer"
                >
                  <span className="text-[11px] font-medium text-teal group-hover:text-teal/80">
                    {item.title}
                  </span>
                  <span className="text-[11px] text-fog mt-1 line-clamp-2">
                    {item.prompt}
                  </span>
                </button>
              ))}
            </div>
          </div>
        ) : (
          /* ── Message Thread ── */
          <div className="max-w-3xl mx-auto w-full px-4 md:px-6 py-4">
            {(() => {
              let assistantTurn = 0;
              return messages.map((m, idx) => {
                const isLastAssistant =
                  idx === messages.length - 1 && m.role === "assistant";
                const currentAssistantIdx = m.role === "assistant" ? assistantTurn++ : -1;
                const messageCitations =
                  citationsByMessage.get(m.id) ||
                  (currentAssistantIdx >= 0 ? citationsByIndex.get(currentAssistantIdx) : undefined);

                return (
                  <div key={m.id || idx}>
                    {idx > 0 && (
                      <div className="border-t border-ash/40 my-1" />
                    )}
                    <ChatMessage
                      role={m.role as "user" | "assistant"}
                      content={m.content}
                      createdAt={m.createdAt ? m.createdAt.toISOString() : undefined}
                      isStreaming={isLastAssistant && isLoading}
                      citations={messageCitations}
                    />
                  </div>
                );
              });
            })()}

            {errorMsg && (
              <div className="flex items-center gap-2 p-3 my-3 bg-danger-dim border border-danger/30 rounded-lg text-danger text-[12px]">
                <AlertCircle className="w-3.5 h-3.5 shrink-0" />
                <span>{errorMsg}</span>
              </div>
            )}

            <div ref={messagesEndRef} className="h-4" />
          </div>
        )}
      </div>

      {/* Input area */}
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
