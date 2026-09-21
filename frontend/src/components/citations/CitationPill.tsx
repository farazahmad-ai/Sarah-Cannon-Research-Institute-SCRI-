/**
 * Clickable citation badge rendered inline within assistant messages.
 *
 * Displays a bracketed NCT reference like [NCT07659782, Exclusion #4].
 * On click, toggles the CitationPopover to show the verbatim protocol quote.
 */

import { useState, useRef } from "react";
import { CitationPopover } from "./CitationPopover";

export interface CitationData {
  nct_id: string;
  section_header: string;
  verbatim_quote: string;
  citation_index: number;
  last_update_posted_date?: string | null;
  created_at?: string | null;
}

interface CitationPillProps {
  /** The raw citation text displayed in the pill, e.g. "[NCT07659782, Exclusion #4]" */
  label: string;
  /** Structured citation data for the popover. If unavailable, pill is non-interactive. */
  citation?: CitationData;
}

export function CitationPill({ label, citation }: CitationPillProps) {
  const [open, setOpen] = useState(false);
  const pillRef = useRef<HTMLButtonElement>(null);

  if (!citation) {
    // Unverified or unlinked reference — render with distinct muted dashed styling
    return (
      <span className="inline-flex items-center font-mono text-[11px] text-muted-foreground bg-ash/20 border border-dashed border-ash/60 px-1.5 py-0.5 rounded mx-0.5 select-all" title="Unverified citation reference">
        {label}
      </span>
    );
  }

  return (
    <span className="relative inline-flex">
      <button
        ref={pillRef}
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        className="inline-flex items-center font-mono text-[11px] text-teal bg-teal-dim border border-teal-border px-1.5 py-0.5 rounded mx-0.5 cursor-pointer hover:bg-teal/15 hover:border-teal/40 transition-colors select-none"
        aria-expanded={open}
        aria-haspopup="dialog"
      >
        {label}
      </button>
      {open && (
        <CitationPopover
          citation={citation}
          onClose={() => setOpen(false)}
          anchorRef={pillRef}
        />
      )}
    </span>
  );
}
