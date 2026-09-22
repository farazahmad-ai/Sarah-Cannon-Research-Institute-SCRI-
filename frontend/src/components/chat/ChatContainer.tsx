/**
 * Main chat conversation view — messages area + input.
 *
 * No top header bar (redundant with sidebar context).
 * Clean empty state with centered welcome and 3 suggested prompts.
 * Passes citation data through to ChatMessage for interactive pills.
 * Prevents navigation race conditions when starting a new session.
 */

import { useEffect, useRef, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { AlertCircle, PanelLeft, Sun, Moon } from "lucide-react";
import { api } from "@/lib/api";
import { useChatStream } from "@/lib/useChatStream";
import { useTheme } from "@/context/ThemeContext";
import { ChatMessage } from "./ChatMessage";
import { ChatInput } from "./ChatInput";
import { CitationDrawer } from "@/components/citations/CitationDrawer";
import type { CitationData } from "@/components/citations/CitationPill";
import type { CitationOut } from "@/lib/api";

interface ChatContainerProps {
  threadId?: string;
  onThreadCreated?: (threadId: string) => void;
  onStreamComplete?: (threadId: string) => void;
  isSidebarOpen?: boolean;
  onToggleSidebar?: () => void;
}

const EXEMPLARY_QUERIES = [
  {
    category: "Thoracic (NSCLC)",
    title: "Prior Immunotherapy Washouts",
    description: "Checkpoint inhibitor washout intervals (28-day vs 14-day / 5 half-lives)",
    prompt:
      "Across our active lymphoma and lung cancer trials, which protocols require a 28-day washout for prior checkpoint inhibitor therapy versus a 14-day or 5 half-life washout?",
  },
  {
    category: "Colorectal (mCRC)",
    title: "Brain Metastases Stability",
    description: "Eligibility for pre-treated asymptomatic CNS lesions & MRI intervals",
    prompt:
      "Which active Phase 2/3 colorectal cancer protocols permit patients with pre-treated, asymptomatic brain metastases, and what is the required MRI stability interval prior to Cycle 1 Day 1?",
  },
  {
    category: "Hematologic (CAR-T)",
    title: "Baseline Hematologic Limits",
    description: "Acceptable ANC and platelet count thresholds across CAR-T studies",
    prompt:
      "Compare the baseline hematologic thresholds across our active Phase 1 CAR-T studies. Which protocol allows an absolute neutrophil count (ANC) below 1,000/µL or platelets below 75,000/µL?",
  },
  {
    category: "Breast (TNBC & HER2-Low)",
    title: "Prior Systemic Therapy Lines",
    description: "Lines of therapy and first-line refractory acceptance for metastatic patients",
    prompt:
      "Which breast cancer trials require patients to have received at least 2 prior lines of systemic therapy in the metastatic setting, and which accept first-line refractory patients?",
  },
];

export function ChatContainer({
  threadId,
  onThreadCreated,
  onStreamComplete,
  isSidebarOpen = true,
  onToggleSidebar,
}: ChatContainerProps) {
  const navigate = useNavigate();
  const { theme, toggleTheme } = useTheme();
  const [activeCitation, setActiveCitation] = useState<CitationData | null>(null);
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
      {/* ── Persistent Top Header ── */}
      <header className="h-12 border-b border-ash bg-graphite/40 backdrop-blur-sm px-4 flex items-center justify-between shrink-0 select-none z-10">
        <div className="flex items-center gap-2.5">
          {!isSidebarOpen && onToggleSidebar && (
            <button
              type="button"
              onClick={onToggleSidebar}
              className="p-1.5 rounded-md text-fog hover:text-cloud hover:bg-ash/50 transition-colors cursor-pointer mr-1"
              title="Open sidebar"
              aria-label="Open sidebar"
            >
              <PanelLeft className="w-4 h-4" />
            </button>
          )}
          <div className="w-6 h-6 rounded-md bg-slate-surface border border-ash flex items-center justify-center p-0.5 overflow-hidden shadow-xs">
            <img src="/logo-genes.png" alt="SCRI Logo" className="w-full h-full object-contain" />
          </div>
          <div className="flex items-baseline gap-2">
            <span className="font-semibold text-cloud text-[13px] tracking-tight">
              SCRI Copilot
            </span>
            <span className="text-[11px] text-fog hidden sm:inline">
              Clinical Protocol Assistant
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => navigate("/trials")}
            className="px-3 py-1 rounded-full text-[11px] font-medium text-cloud bg-slate-surface border border-ash/90 hover:border-teal/50 hover:text-teal hover:bg-teal-dim/20 transition-all cursor-pointer shadow-xs"
            title="Open Trial Catalog"
          >
            Trial Catalog
          </button>
          <button
            type="button"
            onClick={toggleTheme}
            className="p-1.5 rounded-md text-fog hover:text-cloud hover:bg-ash/40 transition-colors cursor-pointer"
            title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
            aria-label="Toggle theme"
          >
            {theme === "dark" ? <Sun className="w-3.5 h-3.5" /> : <Moon className="w-3.5 h-3.5" />}
          </button>
        </div>
      </header>

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
          /* ── Empty State with 4 Exemplary Query Cards ── */
          <div className="min-h-full flex flex-col items-center justify-center max-w-2xl mx-auto text-center px-4 py-8">
            <div className="w-12 h-12 rounded-xl bg-slate-surface border border-ash flex items-center justify-center p-1.5 mb-3 shadow-xs">
              <img src="/logo-genes.png" alt="SCRI" className="w-full h-full object-contain" />
            </div>
            <h2 className="text-[19px] font-semibold text-cloud tracking-tight">
              Clinical Protocol Assistant
            </h2>
            <p className="text-[13px] text-fog mt-1.5 max-w-md leading-relaxed">
              Ask plain-English questions about clinical trial eligibility criteria, washout periods, and biomarker thresholds.
            </p>

            {errorMsg && (
              <div className="flex items-center gap-2 p-3 mt-4 bg-danger-dim border border-danger/30 rounded-lg text-danger text-[12px] max-w-md text-left">
                <AlertCircle className="w-3.5 h-3.5 shrink-0" />
                <span>{errorMsg}</span>
              </div>
            )}

            {/* 4 Exemplary Queries */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 w-full mt-7 text-left">
              {EXEMPLARY_QUERIES.map((item, idx) => (
                <button
                  key={idx}
                  onClick={() => handlePromptClick(item.prompt)}
                  className="flex flex-col p-3.5 rounded-xl bg-slate-surface border border-ash hover:border-teal/60 hover:shadow-md transition-all group cursor-pointer text-left"
                >
                  <div className="flex items-center justify-between w-full mb-1">
                    <span className="text-[10px] font-semibold uppercase tracking-wider text-teal bg-teal-dim px-2 py-0.5 rounded border border-teal-border/40">
                      {item.category}
                    </span>
                  </div>
                  <span className="text-[13px] font-semibold text-cloud group-hover:text-teal transition-colors mt-0.5">
                    {item.title}
                  </span>
                  <span className="text-[11px] text-fog mt-1 leading-relaxed line-clamp-2">
                    {item.description}
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
                      onSelectCitation={(citation) => setActiveCitation(citation)}
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

      {/* Slide-over Citation Drawer */}
      <CitationDrawer
        citation={activeCitation}
        onClose={() => setActiveCitation(null)}
      />
    </div>
  );
}
