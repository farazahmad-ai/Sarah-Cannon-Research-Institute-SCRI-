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

class TolerantCitationMap extends Map<string, CitationData> {
  private citationsList: CitationData[] = [];

  constructor(citations: CitationData[]) {
    super();
    this.citationsList = citations;
    for (const c of citations) {
      // Direct exact key
      this.set(`[${c.nct_id}, ${c.section_header}]`, c);
      this.set(`[${c.nct_id}, ${c.section_header}]`.toLowerCase(), c);
      // Register without 'Eligibility: ' prefix if present
      const cleanHeader = c.section_header.replace(/^eligibility:\s*/i, "").trim();
      this.set(`[${c.nct_id}, ${cleanHeader}]`, c);
      this.set(`[${c.nct_id}, ${cleanHeader}]`.toLowerCase(), c);
    }
  }

  override get(rawKey: string): CitationData | undefined {
    // 1. Exact match lookup
    const direct = super.get(rawKey) || super.get(rawKey.toLowerCase());
    if (direct) return direct;

    // 2. Extract NCT ID
    const nctMatch = rawKey.match(/\[(NCT\d{8})/i);
    if (!nctMatch) return undefined;
    const nctId = nctMatch[1].toUpperCase();

    const candidates = this.citationsList.filter(
      (c) => c.nct_id.toUpperCase() === nctId
    );
    if (candidates.length === 0) return undefined;
    if (candidates.length === 1) return candidates[0];

    // 3. Match criterion number & section type
    const numMatch =
      rawKey.match(/(?:criterion\s*#?|#)\s*(\d+)/i) ||
      rawKey.match(/\b(\d+)\b/);
    const isExcl = /exclusion/i.test(rawKey);
    const isIncl = /inclusion/i.test(rawKey);

    if (numMatch) {
      const targetNum = numMatch[1];
      for (const cand of candidates) {
        const candNumMatch =
          cand.section_header.match(/(?:criterion\s*#?|#)\s*(\d+)/i) ||
          cand.section_header.match(/\b(\d+)\b/);
        const candIsExcl = /exclusion/i.test(cand.section_header);
        const candIsIncl = /inclusion/i.test(cand.section_header);

        if (candNumMatch && candNumMatch[1] === targetNum) {
          if (isExcl && candIsExcl) return cand;
          if (isIncl && candIsIncl) return cand;
          if (!isExcl && !isIncl) return cand;
        }
      }
    }

    // 4. Substring similarity
    const normKey = rawKey.toLowerCase().replace(/[^a-z0-9]/g, " ");
    for (const cand of candidates) {
      const normHeader = cand.section_header.toLowerCase().replace(/[^a-z0-9]/g, " ");
      if (normKey.includes(normHeader) || normHeader.includes(normKey)) {
        return cand;
      }
    }

    // 5. Fallback to first candidate for this NCT
    return candidates[0];
  }
}

/**
 * Build a lookup from bracket label → CitationData with tolerant matching
 * so pills match LLM variations like "[NCT07659782, Exclusion #4]" to metadata.
 */
function buildCitationMap(
  citations: CitationOut[] | undefined
): Map<string, CitationData> {
  if (!citations || citations.length === 0) return new Map();

  const dataList: CitationData[] = citations.map((c) => ({
    nct_id: c.nct_id,
    section_header: c.section_header,
    verbatim_quote: c.verbatim_quote,
    citation_index: c.citation_index,
    last_update_posted_date: c.last_update_posted_date,
    created_at: c.created_at,
  }));

  return new TolerantCitationMap(dataList);
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
