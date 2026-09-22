/**
 * Chat message row — flat layout without chat bubbles.
 *
 * User messages: slightly dimmer, left-aligned with user icon.
 * Assistant messages: full contrast, left-aligned with bot icon.
 * Citations: interactive CitationPill components that open popovers.
 */

import { User } from "lucide-react";
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
  /** Handler to open the citation drawer */
  onSelectCitation?: (citation: CitationData) => void;
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
      // Register by index if available
      this.set(`[${c.citation_index}]`, c);
    }
  }

  override get(rawKey: string): CitationData | undefined {
    // 1. Exact match lookup
    const direct = super.get(rawKey) || super.get(rawKey.toLowerCase());
    if (direct) return direct;

    // 2. Direct index lookup like [1], [2]
    const idxMatch = rawKey.match(/^\[(\d+)\]$/);
    if (idxMatch) {
      const targetIdx = parseInt(idxMatch[1], 10);
      const byIdx = this.citationsList.find((c) => c.citation_index === targetIdx);
      if (byIdx) return byIdx;
      if (targetIdx >= 1 && targetIdx <= this.citationsList.length) {
        return this.citationsList[targetIdx - 1];
      }
    }

    // 3. Extract NCT ID
    const nctMatch = rawKey.match(/\[(NCT\d{8})/i);
    if (!nctMatch) return undefined;
    const nctId = nctMatch[1].toUpperCase();

    const candidates = this.citationsList.filter(
      (c) => c.nct_id.toUpperCase() === nctId
    );
    if (candidates.length === 0) return undefined;
    if (candidates.length === 1) return candidates[0];

    // 4. Match criterion number & section type
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

    // 5. Substring similarity
    const normKey = rawKey.toLowerCase().replace(/[^a-z0-9]/g, " ");
    for (const cand of candidates) {
      const normHeader = cand.section_header.toLowerCase().replace(/[^a-z0-9]/g, " ");
      if (normKey.includes(normHeader) || normHeader.includes(normKey)) {
        return cand;
      }
    }

    // 6. Fallback to first candidate for this NCT
    return candidates[0];
  }
}

/**
 * Build deduplicated citation list and lookup maps with deterministic numbering
 */
function prepareCitations(citations: CitationOut[] | undefined): {
  citationMap: Map<string, CitationData>;
  citationNumberMap: Map<string, number>;
  uniqueCitations: CitationData[];
} {
  if (!citations || citations.length === 0) {
    return {
      citationMap: new Map(),
      citationNumberMap: new Map(),
      uniqueCitations: [],
    };
  }

  // Deduplicate by NCT ID + section_header
  const seen = new Set<string>();
  const uniqueCitations: CitationData[] = [];
  const citationNumberMap = new Map<string, number>();

  for (const c of citations) {
    const key = `${c.nct_id.toUpperCase()}:${c.section_header.trim()}`;
    if (!seen.has(key)) {
      seen.add(key);
      const index = uniqueCitations.length + 1;
      const data: CitationData = {
        nct_id: c.nct_id,
        section_header: c.section_header,
        verbatim_quote: c.verbatim_quote,
        citation_index: index,
        last_update_posted_date: c.last_update_posted_date,
        created_at: c.created_at,
      };
      uniqueCitations.push(data);
      citationNumberMap.set(key, index);
      citationNumberMap.set(`${c.nct_id}:${c.section_header}`, index);
    }
  }

  const citationMap = new TolerantCitationMap(uniqueCitations);
  return { citationMap, citationNumberMap, uniqueCitations };
}

export function ChatMessage({
  role,
  content,
  createdAt,
  isStreaming = false,
  citations,
  onSelectCitation,
}: MessageProps) {
  const isUser = role === "user";
  const { citationMap, citationNumberMap, uniqueCitations } = prepareCitations(citations);

  return (
    <div className={`flex gap-3.5 py-4 ${isUser ? "opacity-90" : ""}`}>
      {/* Role icon */}
      <div
        className={`w-7 h-7 rounded-lg flex items-center justify-center shrink-0 mt-0.5 overflow-hidden ${
          isUser
            ? "bg-ash text-fog"
            : "bg-slate-surface border border-ash/80 p-0.5"
        }`}
      >
        {isUser ? (
          <User className="w-3.5 h-3.5" />
        ) : (
          <img
            src="/logo-genes.png"
            alt="SCRI"
            className="w-full h-full object-contain"
            onError={(e) => {
              // Fallback to text if asset not found
              (e.currentTarget as HTMLElement).style.display = "none";
            }}
          />
        )}
      </div>

      {/* Content column */}
      <div className="flex-1 min-w-0">
        {/* Role label + timestamp */}
        <div className="flex items-center gap-2 mb-1.5">
          <span
            className={`text-[11px] font-semibold tracking-tight ${
              isUser ? "text-fog" : "text-cloud"
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
            <>
              <MarkdownContent
                content={content}
                citationMap={citationMap}
                citationNumberMap={citationNumberMap}
                onSelectCitation={onSelectCitation}
              />

              {/* Bottom Reference Pills */}
              {uniqueCitations.length > 0 && !isStreaming && (
                <div className="mt-4 pt-3 border-t border-ash/70">
                  <div className="text-[11px] font-medium text-fog mb-2">
                    Evidence & Protocol References:
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {uniqueCitations.map((c, i) => (
                      <button
                        key={`${c.nct_id}-${i}`}
                        type="button"
                        onClick={() => onSelectCitation?.(c)}
                        className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] bg-graphite border border-ash hover:border-teal/50 hover:bg-teal-dim/30 text-cloud transition-all cursor-pointer shadow-xs group"
                        title="Click to view verbatim protocol excerpt"
                      >
                        <span className="font-mono text-[10px] font-bold text-teal bg-teal-dim px-1.5 py-0.2 rounded border border-teal-border/40">
                          {i + 1}
                        </span>
                        <span className="font-mono font-medium text-teal text-[11px]">
                          {c.nct_id}
                        </span>
                        <span className="text-fog group-hover:text-cloud transition-colors truncate max-w-[240px]">
                          {c.section_header.replace(/^eligibility:\s*/i, "")}
                        </span>
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
          {isStreaming && (
            <span className="inline-block w-1.5 h-3.5 ml-1 bg-teal animate-pulse align-middle rounded-sm" />
          )}
        </div>
      </div>
    </div>
  );
}
