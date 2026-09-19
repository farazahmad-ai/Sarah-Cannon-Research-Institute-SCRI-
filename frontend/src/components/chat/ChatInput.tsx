import React, { useEffect, useRef } from "react";
import { ArrowUp, Square } from "lucide-react";

interface ChatInputProps {
  input: string;
  handleInputChange: (e: React.ChangeEvent<HTMLTextAreaElement>) => void;
  handleSubmit: (e: React.FormEvent<HTMLFormElement>) => void;
  isLoading: boolean;
  stop?: () => void;
  placeholder?: string;
}

export function ChatInput({
  input,
  handleInputChange,
  handleSubmit,
  isLoading,
  stop,
  placeholder = "Ask a protocol eligibility question (e.g., washout periods, biomarker thresholds, ANC limits)...",
}: ChatInputProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-resize textarea height as content expands
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(
        textareaRef.current.scrollHeight,
        180
      )}px`;
    }
  }, [input]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (input.trim() && !isLoading) {
        // Trigger submit
        const form = e.currentTarget.form;
        if (form) {
          form.requestSubmit();
        }
      }
    }
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="relative flex flex-col w-full max-w-4xl mx-auto px-4 pb-4"
    >
      <div className="relative flex items-end bg-slate-900/90 border border-slate-800 rounded-2xl p-2 shadow-lg focus-within:border-sky-500/60 focus-within:ring-1 focus-within:ring-sky-500/30 transition-all">
        <textarea
          ref={textareaRef}
          value={input}
          onChange={handleInputChange}
          onKeyDown={handleKeyDown}
          rows={1}
          placeholder={placeholder}
          disabled={isLoading}
          className="w-full bg-transparent text-slate-100 placeholder:text-slate-500 text-sm resize-none px-3 py-2 focus:outline-hidden min-h-[44px] max-h-[180px] leading-relaxed"
        />

        <div className="flex items-center gap-1.5 pb-1 pr-1 shrink-0">
          {isLoading ? (
            <button
              type="button"
              onClick={stop}
              className="flex items-center justify-center w-8 h-8 rounded-xl bg-red-950/80 border border-red-800/80 text-red-300 hover:bg-red-900 transition-colors shadow-xs"
              title="Stop generating"
            >
              <Square className="w-3.5 h-3.5 fill-current" />
            </button>
          ) : (
            <button
              type="submit"
              disabled={!input.trim() || isLoading}
              className="flex items-center justify-center w-8 h-8 rounded-xl bg-sky-600 hover:bg-sky-500 disabled:opacity-40 disabled:hover:bg-sky-600 text-white transition-all shadow-xs disabled:cursor-not-allowed"
              title="Send question (Enter)"
            >
              <ArrowUp className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>

      <div className="flex items-center justify-between text-[11px] text-slate-500 px-3 mt-2">
        <span>
          Answers are strictly grounded in unclassified ClinicalTrials.gov protocols.
        </span>
        <span className="hidden sm:inline text-slate-600">
          Press <kbd className="px-1 py-0.5 bg-slate-800 rounded text-slate-400">Enter</kbd> to send, <kbd className="px-1 py-0.5 bg-slate-800 rounded text-slate-400">Shift+Enter</kbd> for newline
        </span>
      </div>
    </form>
  );
}
