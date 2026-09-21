/**
 * Chat input — auto-growing textarea with send/stop controls.
 *
 * Minimal design: dark field blending with the void background,
 * teal focus ring, simplified footer. Enter submits, Shift+Enter newlines.
 */

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
  placeholder = "Ask about eligibility criteria, washout periods, biomarkers...",
}: ChatInputProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-resize textarea as content grows
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(
        textareaRef.current.scrollHeight,
        160
      )}px`;
    }
  }, [input]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (input.trim() && !isLoading) {
        const form = e.currentTarget.form;
        if (form) form.requestSubmit();
      }
    }
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="relative flex flex-col w-full max-w-3xl mx-auto px-4 pb-4 pt-2"
    >
      <div className="relative flex items-end bg-slate-surface border border-ash rounded-xl p-1.5 focus-within:border-teal-border focus-within:ring-1 focus-within:ring-teal-border/30 transition-all">
        <textarea
          ref={textareaRef}
          value={input}
          onChange={handleInputChange}
          onKeyDown={handleKeyDown}
          rows={1}
          placeholder={placeholder}
          disabled={isLoading}
          className="w-full bg-transparent text-cloud placeholder:text-fog/50 text-[13px] resize-none px-3 py-2 focus:outline-none min-h-[40px] max-h-[160px] leading-relaxed"
        />

        <div className="flex items-center pb-1 pr-1 shrink-0">
          {isLoading ? (
            <button
              type="button"
              onClick={stop}
              className="flex items-center justify-center w-7 h-7 rounded-lg bg-danger-dim border border-danger/30 text-danger hover:bg-danger/20 transition-colors cursor-pointer"
              title="Stop generating"
            >
              <Square className="w-3 h-3 fill-current" />
            </button>
          ) : (
            <button
              type="submit"
              disabled={!input.trim() || isLoading}
              className="flex items-center justify-center w-7 h-7 rounded-lg bg-teal hover:bg-teal/85 disabled:opacity-30 disabled:hover:bg-teal text-void transition-all disabled:cursor-not-allowed cursor-pointer"
              title="Send (Enter)"
            >
              <ArrowUp className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>

      <p className="text-[10px] text-fog/50 text-center mt-2">
        Answers are grounded in ClinicalTrials.gov protocols. Not medical advice.
      </p>
    </form>
  );
}
