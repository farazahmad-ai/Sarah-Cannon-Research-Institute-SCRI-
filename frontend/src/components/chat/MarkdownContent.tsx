/**
 * Markdown parser and renderer for SCRI Oncology Copilot.
 *
 * Renders structured oncology responses:
 * - Bold key terms (**term**) -> <strong>
 * - Bullet lists (* or -) -> styled <ul> / <li>
 * - Numbered lists (1.) -> styled <ol> / <li>
 * - Section headers (### or ##) -> clean clinical headings
 * - Code blocks and inline code (`code`)
 * - Protocol citations ([NCT05794958, Section Header]) -> interactive CitationPill
 *
 * Zero external markdown dependencies — zero React 19 peer conflict issues.
 */

import React from "react";
import { CitationPill, type CitationData } from "@/components/citations/CitationPill";

interface MarkdownContentProps {
  content: string;
  citationMap: Map<string, CitationData>;
  citationNumberMap?: Map<string, number>;
  onSelectCitation?: (citation: CitationData) => void;
  onViewInProtocol?: (citation: CitationData) => void;
}

/** Parse inline tokens: citations, bold, italic, code */
function renderInline(
  text: string,
  citationMap: Map<string, CitationData>,
  citationNumberMap?: Map<string, number>,
  onSelectCitation?: (citation: CitationData) => void,
  onViewInProtocol?: (citation: CitationData) => void
): React.ReactNode[] {
  // Regex to match:
  // 1. Citations: [NCT01234567, Section Name] or [1]
  // 2. Bold: **text**
  // 3. Inline code: `text`
  // 4. Italic: *text* or _text_
  const tokenRegex = /(\[(?:NCT\d{8}[^\]]*)\]|\*\*[^*]+\*\*|`[^`]+`|\*[^*]+\*|_[^_]+_)/gi;

  const parts = text.split(tokenRegex);
  const elements: React.ReactNode[] = [];

  for (let i = 0; i < parts.length; i++) {
    const part = parts[i];
    if (!part) continue;

    // 1. Citation check: [NCT12345678, ...]
    if (/^\[NCT\d{8}/i.test(part) && part.endsWith("]")) {
      const citation = citationMap.get(part);
      if (citation && onSelectCitation) {
        const key = `${citation.nct_id}:${citation.section_header}`;
        const num = citationNumberMap?.get(key) ?? citation.citation_index ?? 1;
        elements.push(
          <button
            key={`cit-${i}-${part}`}
            type="button"
            onClick={() => onSelectCitation(citation)}
            className="inline-flex items-center justify-center font-mono text-[10px] font-bold text-teal bg-teal-dim border border-teal-border hover:bg-teal hover:text-void rounded px-1.5 py-0.2 mx-0.5 align-baseline transition-all cursor-pointer shadow-xs select-none"
            title={`${citation.nct_id}: ${citation.section_header} (Click to inspect protocol)`}
          >
            [{num}]
          </button>
        );
      } else {
        elements.push(
          <CitationPill
            key={`cit-${i}-${part}`}
            label={part}
            citation={citation}
            onViewInProtocol={onViewInProtocol}
          />
        );
      }
    }
    // 2. Bold: **text**
    else if (part.startsWith("**") && part.endsWith("**") && part.length > 4) {
      const inner = part.slice(2, -2);
      elements.push(
        <strong key={`b-${i}`} className="font-semibold text-cloud">
          {renderInline(inner, citationMap, citationNumberMap, onSelectCitation, onViewInProtocol)}
        </strong>
      );
    }
    // 3. Inline code: `text`
    else if (part.startsWith("`") && part.endsWith("`") && part.length > 2) {
      elements.push(
        <code
          key={`c-${i}`}
          className="font-mono text-[11px] bg-ash/40 text-teal px-1 py-0.5 rounded border border-ash/50"
        >
          {part.slice(1, -1)}
        </code>
      );
    }
    // 4. Italic: *text* or _text_
    else if (
      ((part.startsWith("*") && part.endsWith("*")) ||
        (part.startsWith("_") && part.endsWith("_"))) &&
      part.length > 2
    ) {
      elements.push(
        <em key={`em-${i}`} className="italic text-cloud/90">
          {renderInline(part.slice(1, -1), citationMap, citationNumberMap, onSelectCitation, onViewInProtocol)}
        </em>
      );
    }
    // Plain text
    else {
      elements.push(part);
    }
  }

  return elements;
}

export function MarkdownContent({
  content,
  citationMap,
  citationNumberMap,
  onSelectCitation,
  onViewInProtocol,
}: MarkdownContentProps) {
  if (!content) return null;

  // Split into lines
  const lines = content.split("\n");
  const nodes: React.ReactNode[] = [];

  let currentList: { type: "ul" | "ol"; items: string[] } | null = null;

  const flushList = (key: number) => {
    if (!currentList) return;
    const { type, items } = currentList;
    currentList = null;

    if (type === "ul") {
      nodes.push(
        <ul key={`ul-${key}`} className="my-2 space-y-1.5 pl-4 list-disc marker:text-teal">
          {items.map((item, idx) => (
            <li key={idx} className="leading-relaxed text-cloud text-[13px]">
              {renderInline(item, citationMap, citationNumberMap, onSelectCitation, onViewInProtocol)}
            </li>
          ))}
        </ul>
      );
    } else {
      nodes.push(
        <ol key={`ol-${key}`} className="my-2 space-y-1.5 pl-4 list-decimal marker:text-teal font-mono text-[12px]">
          {items.map((item, idx) => (
            <li key={idx} className="leading-relaxed text-cloud text-[13px] font-sans">
              {renderInline(item, citationMap, citationNumberMap, onSelectCitation, onViewInProtocol)}
            </li>
          ))}
        </ol>
      );
    }
  };

  for (let idx = 0; idx < lines.length; idx++) {
    const rawLine = lines[idx];
    const trimmed = rawLine.trim();

    // Check for empty line
    if (!trimmed) {
      flushList(idx);
      continue;
    }

    // 1. Heading 3: ### Title
    if (trimmed.startsWith("### ")) {
      flushList(idx);
      nodes.push(
        <h4 key={`h4-${idx}`} className="font-semibold text-[13px] text-cloud tracking-tight mt-3 mb-1">
          {renderInline(trimmed.slice(4), citationMap, citationNumberMap, onSelectCitation, onViewInProtocol)}
        </h4>
      );
      continue;
    }

    // 2. Heading 2: ## Title
    if (trimmed.startsWith("## ")) {
      flushList(idx);
      nodes.push(
        <h3 key={`h3-${idx}`} className="font-semibold text-[14px] text-cloud tracking-tight mt-3.5 mb-1.5">
          {renderInline(trimmed.slice(3), citationMap, citationNumberMap, onSelectCitation, onViewInProtocol)}
        </h3>
      );
      continue;
    }

    // 3. Heading 1: # Title
    if (trimmed.startsWith("# ")) {
      flushList(idx);
      nodes.push(
        <h2 key={`h2-${idx}`} className="font-bold text-[15px] text-cloud tracking-tight mt-4 mb-2">
          {renderInline(trimmed.slice(2), citationMap, citationNumberMap, onSelectCitation, onViewInProtocol)}
        </h2>
      );
      continue;
    }

    // 4. Bullet list items: * or -
    const bulletMatch = trimmed.match(/^[-*]\s+(.*)$/);
    if (bulletMatch) {
      if (!currentList || currentList.type !== "ul") {
        flushList(idx);
        currentList = { type: "ul", items: [] };
      }
      currentList.items.push(bulletMatch[1]);
      continue;
    }

    // 5. Numbered list items: 1. or 2.
    const numberedMatch = trimmed.match(/^\d+\.\s+(.*)$/);
    if (numberedMatch) {
      if (!currentList || currentList.type !== "ol") {
        flushList(idx);
        currentList = { type: "ol", items: [] };
      }
      currentList.items.push(numberedMatch[1]);
      continue;
    }

    // 6. Blockquote: > text
    if (trimmed.startsWith("> ")) {
      flushList(idx);
      nodes.push(
        <div key={`bq-${idx}`} className="my-2 pl-3 border-l-2 border-teal/40 text-fog text-[12px] italic">
          {renderInline(trimmed.slice(2), citationMap, citationNumberMap, onSelectCitation, onViewInProtocol)}
        </div>
      );
      continue;
    }

    // 7. Regular paragraph
    flushList(idx);
    nodes.push(
      <p key={`p-${idx}`} className="my-1.5 leading-relaxed text-cloud text-[13px]">
        {renderInline(trimmed, citationMap, citationNumberMap, onSelectCitation, onViewInProtocol)}
      </p>
    );
  }

  flushList(lines.length);

  return <div className="space-y-1">{nodes}</div>;
}
