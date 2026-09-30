/**
 * Slide-over drawer displaying the verbatim clinical protocol quote for a citation.
 *
 * Slides in smoothly from the right side.
 * Features:
 * - Direct link to ClinicalTrials.gov for the NCT ID
 * - Protocol section header and amendment date
 * - Scrollable verbatim quote text with high readability
 * - '✕' close button, escape key listener, and backdrop dismissal
 */

import { useEffect } from "react";
import { X, ExternalLink, ShieldCheck, Calendar, BookOpen } from "lucide-react";
import type { CitationData } from "./CitationPill";

interface CitationDrawerProps {
  citation: CitationData | null;
  onClose: () => void;
  onViewInProtocol?: (citation: CitationData) => void;
}

export function CitationDrawer({
  citation,
  onClose,
  onViewInProtocol,
}: CitationDrawerProps) {
  // Close on Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  if (!citation) return null;

  const externalUrl = `https://clinicaltrials.gov/study/${citation.nct_id}`;
  const amendmentDate = citation.last_update_posted_date
    ? new Date(citation.last_update_posted_date).toLocaleDateString(undefined, {
        year: "numeric",
        month: "short",
        day: "numeric",
      })
    : null;

  return (
    <>
      {/* Backdrop */}
      <div
        onClick={onClose}
        className="fixed inset-0 bg-black/40 backdrop-blur-[2px] z-40 transition-opacity"
        aria-hidden="true"
      />

      {/* Slide-over Drawer */}
      <div
        role="dialog"
        aria-modal="true"
        aria-label={`Citation reference ${citation.nct_id}`}
        className="fixed inset-y-0 right-0 z-50 w-full max-w-md md:max-w-lg bg-slate-surface border-l border-ash shadow-2xl flex flex-col animate-slide-in-right overflow-hidden text-cloud select-text"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-ash bg-graphite/60 shrink-0">
          <div className="flex items-center gap-2.5 min-w-0">
            <span className="font-mono text-[12px] font-semibold text-teal bg-teal-dim border border-teal-border px-2 py-0.5 rounded">
              {citation.nct_id}
            </span>
            <span className="text-[11px] font-medium text-fog bg-ash/40 px-2 py-0.5 rounded">
              Ref [{citation.citation_index}]
            </span>
          </div>

          <div className="flex items-center gap-1">
            <a
              href={externalUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="p-1.5 rounded-md text-fog hover:text-cloud hover:bg-ash/50 transition-colors"
              title="Open protocol on ClinicalTrials.gov"
            >
              <ExternalLink className="w-4 h-4" />
            </a>
            <button
              type="button"
              onClick={onClose}
              className="p-1.5 rounded-md text-fog hover:text-cloud hover:bg-ash/50 transition-colors cursor-pointer"
              title="Close drawer (Esc)"
              aria-label="Close drawer"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Scrollable Content */}
        <div className="flex-1 overflow-y-auto p-5 space-y-4 scrollbar-clinical">
          {/* Section info */}
          <div>
            <div className="flex items-center gap-1.5 text-[11px] text-teal font-medium uppercase tracking-wider mb-1">
              <BookOpen className="w-3.5 h-3.5" />
              <span>Protocol Section</span>
            </div>
            <h3 className="text-[15px] font-semibold text-cloud leading-snug">
              {citation.section_header}
            </h3>
          </div>

          {/* Verbatim quote block */}
          <div>
            <div className="flex items-center gap-1.5 text-[11px] text-fog font-medium mb-1.5">
              <ShieldCheck className="w-3.5 h-3.5 text-teal" />
              <span>Verbatim Protocol Text (Ground Truth)</span>
            </div>
            <div className="p-3.5 rounded-lg bg-graphite/80 border border-ash/80 border-l-4 border-l-teal">
              <p className="text-[13px] leading-relaxed text-cloud/95 whitespace-pre-wrap font-sans">
                {citation.verbatim_quote}
              </p>
            </div>
          </div>

          {/* Metadata chips */}
          <div className="pt-2 border-t border-ash/60 space-y-2 text-[11px] text-fog">
            {amendmentDate && (
              <div className="flex items-center gap-1.5">
                <Calendar className="w-3.5 h-3.5 text-fog/70" />
                <span>Protocol update posted: {amendmentDate}</span>
              </div>
            )}
            <div className="text-[10px] text-fog/60 leading-normal">
              Passage retrieved from Sarah Cannon Research Institute active trial index via ClinicalTrials.gov REST API.
            </div>
          </div>
        </div>

        {/* Footer actions */}
        <div className="p-4 border-t border-ash bg-graphite/40 flex items-center justify-between shrink-0 gap-2">
          {onViewInProtocol && (
            <button
              type="button"
              onClick={() => {
                onClose();
                onViewInProtocol(citation);
              }}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-[12px] font-medium bg-slate-surface border border-teal-border/60 text-teal hover:bg-teal hover:text-void transition-all cursor-pointer shadow-xs"
              title="Open full protocol and highlight this criterion"
            >
              <BookOpen className="w-3.5 h-3.5" />
              <span>View in Protocol</span>
            </button>
          )}
          <a
            href={externalUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-[12px] font-medium bg-teal hover:bg-teal/85 text-void transition-colors cursor-pointer ml-auto"
          >
            <span>View on ClinicalTrials.gov</span>
            <ExternalLink className="w-3.5 h-3.5" />
          </a>
        </div>
      </div>
    </>
  );
}
