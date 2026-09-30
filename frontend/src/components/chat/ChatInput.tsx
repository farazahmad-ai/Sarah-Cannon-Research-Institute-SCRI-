/**
 * Chat input — auto-growing textarea with send/stop controls.
 *
 * Minimal design: dark field blending with the void background,
 * teal focus ring, simplified footer. Enter submits, Shift+Enter newlines.
 */

import React, { useEffect, useRef } from "react";
import { ArrowUp, Square, ShieldAlert } from "lucide-react";

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
      <div className="relative flex items-end bg-slate-surface border border-gray-300 dark:border-ash rounded-2xl p-2 shadow-[0_2px_12px_rgba(0,0,0,0.06)] dark:shadow-[0_4px_20px_rgba(0,0,0,0.3)] focus-within:border-teal focus-within:ring-2 focus-within:ring-teal/20 transition-all">
        <textarea
          ref={textareaRef}
          value={input}
          onChange={handleInputChange}
          onKeyDown={handleKeyDown}
          rows={1}
          placeholder={placeholder}
          disabled={isLoading}
          className="w-full bg-transparent text-cloud placeholder:text-fog/80 text-[13px] resize-none px-3 py-1.5 focus:outline-none min-h-[42px] max-h-[160px] leading-relaxed font-sans"
        />

        <div className="flex items-center pb-1 pr-1 shrink-0">
          {isLoading ? (
            <button
              type="button"
              onClick={stop}
              className="flex items-center justify-center w-8 h-8 rounded-xl bg-danger-dim border border-danger/40 text-danger hover:bg-danger/25 transition-colors cursor-pointer"
              title="Stop generating"
            >
              <Square className="w-3 h-3 fill-current" />
            </button>
          ) : (
            <button
              type="submit"
              disabled={!input.trim() || isLoading}
              className="flex items-center justify-center w-8 h-8 rounded-xl bg-teal hover:bg-teal/85 disabled:opacity-35 disabled:hover:bg-teal text-void transition-all disabled:cursor-not-allowed cursor-pointer shadow-xs"
              title="Send (Enter)"
            >
              <ArrowUp className="w-4 h-4 stroke-[2.5]" />
            </button>
          )}
        </div>
      </div>

      <div className="flex items-center justify-center gap-1.5 mt-2 px-3 py-1 rounded-md text-[11px] text-fog/90 bg-graphite/40 border border-ash/40 max-w-2xl mx-auto text-center leading-normal select-none">
        <ShieldAlert className="w-3.5 h-3.5 text-teal shrink-0" />
        <span>
          <strong className="font-semibold text-cloud">Clinical Screening Assistant:</strong> Not a clinical decision system. All eligibility determinations must be confirmed against the source protocol before enrollment.
        </span>
      </div>
    </form>
  );
}
