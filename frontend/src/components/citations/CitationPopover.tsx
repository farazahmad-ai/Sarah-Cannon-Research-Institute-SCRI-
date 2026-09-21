/**
 * Floating popover that displays the verbatim protocol quote for a citation.
 *
 * Positioned below the citation pill. Dismisses on click outside or Escape.
 * Shows the NCT ID, section header, the exact text passage, and amendment date.
 */

import { useEffect, useRef, type RefObject } from "react";
import type { CitationData } from "./CitationPill";

interface CitationPopoverProps {
  citation: CitationData;
  onClose: () => void;
  anchorRef: RefObject<HTMLElement | null>;
}

export function CitationPopover({
  citation,
  onClose,
  anchorRef,
}: CitationPopoverProps) {
  const popoverRef = useRef<HTMLDivElement>(null);

  // Close on Escape or click outside
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };

    const handleClickOutside = (e: MouseEvent) => {
      const target = e.target as Node;
      if (
        popoverRef.current &&
        !popoverRef.current.contains(target) &&
        anchorRef.current &&
        !anchorRef.current.contains(target)
      ) {
        onClose();
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [onClose, anchorRef]);

  const amendmentDate = citation.last_update_posted_date
    ? new Date(citation.last_update_posted_date).toLocaleDateString(undefined, {
        year: "numeric",
        month: "short",
        day: "numeric",
      })
    : null;

  return (
    <div
      ref={popoverRef}
      role="dialog"
      aria-label={`Citation: ${citation.nct_id}, ${citation.section_header}`}
      className="absolute left-0 top-full mt-2 z-50 w-80 max-w-[90vw] bg-slate-surface border border-ash rounded-lg shadow-xl shadow-black/40 animate-in fade-in-0 zoom-in-95 duration-150"
    >
      {/* Header */}
      <div className="flex items-center justify-between px-3.5 py-2.5 border-b border-ash">
        <div className="flex items-center gap-2 min-w-0">
          <span className="font-mono text-[11px] font-medium text-teal shrink-0">
            {citation.nct_id}
          </span>
          <span className="text-[11px] text-fog truncate">
            {citation.section_header}
          </span>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="text-fog hover:text-cloud p-0.5 rounded transition-colors shrink-0 ml-2"
          aria-label="Close citation"
        >
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      {/* Verbatim Quote */}
      <div className="px-3.5 py-3">
        <div className="border-l-2 border-teal/40 pl-3 py-1">
          <p className="text-[12px] leading-relaxed text-cloud/90 whitespace-pre-wrap select-text">
            {citation.verbatim_quote}
          </p>
        </div>
      </div>

      {/* Footer */}
      {amendmentDate && (
        <div className="px-3.5 py-2 border-t border-ash">
          <span className="text-[10px] text-fog">
            Protocol amendment: {amendmentDate}
          </span>
        </div>
      )}
    </div>
  );
}
