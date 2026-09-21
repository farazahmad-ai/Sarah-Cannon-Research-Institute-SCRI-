/**
 * Chat message row — flat layout without chat bubbles.
 *
 * User messages: slightly dimmer, left-aligned with user icon.
 * Assistant messages: full contrast, left-aligned with bot icon.
 * Citations: interactive CitationPill components that open popovers.
 */

import { Bot, User } from "lucide-react";
import type { CitationData } from "@/components/citations/CitationPill";
import type { CitationOut } from "@/lib/api";
import { MarkdownContent } from "./MarkdownContent";

export interface MessageProps {
  role: "user" | "assistant" | "system";
  content: string;
  createdAt?: string;
  isStreaming?: boolean;
  /** Structured citation data from backend for this message. */
  citations?: CitationOut[];
}

/**
 * Build a lookup from bracket label → CitationData so pills can match
 * the inline text like "[NCT07659782, Exclusion #4]" to its metadata.
 */
function buildCitationMap(
  citations: CitationOut[] | undefined
): Map<string, CitationData> {
  const map = new Map<string, CitationData>();
  if (!citations) return map;

  for (const c of citations) {
    // Normalize label format to match what the LLM typically produces
    const key = `[${c.nct_id}, ${c.section_header}]`;
    map.set(key, {
      nct_id: c.nct_id,
      section_header: c.section_header,
      verbatim_quote: c.verbatim_quote,
      citation_index: c.citation_index,
      created_at: c.created_at,
    });
  }
  return map;
}

export function ChatMessage({
  role,
  content,
  createdAt,
  isStreaming = false,
  citations,
}: MessageProps) {
  const isUser = role === "user";
  const citationMap = buildCitationMap(citations);

  return (
    <div className={`flex gap-3 py-4 ${isUser ? "opacity-90" : ""}`}>
      {/* Role icon */}
      <div
        className={`w-7 h-7 rounded-lg flex items-center justify-center shrink-0 mt-0.5 ${
          isUser
            ? "bg-ash text-fog"
            : "bg-teal-dim border border-teal-border text-teal"
        }`}
      >
        {isUser ? (
          <User className="w-3.5 h-3.5" />
        ) : (
          <Bot className="w-3.5 h-3.5" />
        )}
      </div>

      {/* Content column */}
      <div className="flex-1 min-w-0">
        {/* Role label + timestamp */}
        <div className="flex items-center gap-2 mb-1.5">
          <span
            className={`text-[11px] font-medium ${
              isUser ? "text-fog" : "text-teal"
            }`}
          >
            {isUser ? "You" : "SCRI Copilot"}
          </span>
          {createdAt && (
            <span className="text-[10px] text-fog/60">
              {new Date(createdAt).toLocaleTimeString([], {
                hour: "2-digit",
                minute: "2-digit",
              })}
            </span>
          )}
        </div>

        {/* Message body */}
        <div className="text-[13px] leading-relaxed text-cloud select-text">
          {isUser ? (
            <p className="whitespace-pre-wrap text-cloud/90">{content}</p>
          ) : (
            <MarkdownContent content={content} citationMap={citationMap} />
          )}
          {isStreaming && (
            <span className="inline-block w-1.5 h-3.5 ml-1 bg-teal animate-pulse align-middle rounded-sm" />
          )}
        </div>
      </div>
    </div>
  );
}
