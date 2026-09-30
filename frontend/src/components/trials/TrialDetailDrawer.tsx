/**
 * Full protocol viewer drawer — slides in from the right.
 *
 * Fetches TrialDetail on mount and displays the complete protocol:
 * official title, phases, arms, conditions, primary outcomes,
 * and scrollable protocol chunks grouped by section type.
 */

import { useEffect, useState, useRef } from "react";
import { X, ExternalLink, ShieldCheck } from "lucide-react";
import { api, type TrialDetail, type TrialChunkOut } from "@/lib/api";
import { formatCategory } from "./TrialCard";

interface TrialDetailDrawerProps {
  nctId: string;
  onClose: () => void;
  highlightSection?: string;
  highlightQuote?: string;
}

/** Group chunks by their section_type for organized display. */
function groupChunksBySection(
  chunks: TrialDetail["chunks"]
): Map<string, TrialDetail["chunks"]> {
  const groups = new Map<string, TrialDetail["chunks"]>();
  for (const chunk of chunks) {
    const key = chunk.section_type;
    const existing = groups.get(key) ?? [];
    existing.push(chunk);
    groups.set(key, existing);
  }
  return groups;
}

/** Format a section type slug into a readable heading. */
function formatSectionType(sectionType: string): string {
  return sectionType
    .replace(/_/g, " ")
    .toLowerCase()
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

/** Check if a protocol chunk matches the target citation criteria. */
function isChunkTarget(
  chunk: TrialChunkOut,
  highlightSection?: string,
  highlightQuote?: string
): boolean {
  if (!highlightSection && !highlightQuote) return false;
  if (highlightSection) {
    const cleanSection = highlightSection.replace(/^eligibility:\s*/i, "").trim().toLowerCase();
    const cleanTitle = chunk.section_title.replace(/^eligibility:\s*/i, "").trim().toLowerCase();
    if (cleanTitle === cleanSection || cleanTitle.includes(cleanSection) || cleanSection.includes(cleanTitle)) {
      return true;
    }
    // Criterion number match (e.g. Exclusion Criterion #4)
    const secNum = highlightSection.match(/(?:criterion\s*#?|#)\s*(\d+)/i);
    const titleNum = chunk.section_title.match(/(?:criterion\s*#?|#)\s*(\d+)/i);
    if (secNum && titleNum && secNum[1] === titleNum[1]) {
      const secExcl = /exclusion/i.test(highlightSection);
      const titleExcl = /exclusion/i.test(chunk.section_title);
      if (secExcl === titleExcl) return true;
    }
  }
  if (highlightQuote && highlightQuote.length > 20) {
    const sample = highlightQuote.slice(0, 40).toLowerCase();
    if (chunk.chunk_text.toLowerCase().includes(sample)) {
      return true;
    }
  }
  return false;
}

export function TrialDetailDrawer({
  nctId,
  onClose,
  highlightSection,
  highlightQuote,
}: TrialDetailDrawerProps) {
  const [trial, setTrial] = useState<TrialDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const targetElementRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    api.trials
      .get(nctId)
      .then(setTrial)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [nctId]);

  // Auto-scroll to target chunk if highlighted
  useEffect(() => {
    if (!loading && trial && targetElementRef.current) {
      const timer = setTimeout(() => {
        targetElementRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
      }, 150);
      return () => clearTimeout(timer);
    }
  }, [loading, trial]);

  // Close on Escape
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  const chunks = trial?.chunks ?? [];
  const sectionGroups = groupChunksBySection(chunks);

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/60 z-40 animate-in fade-in-0 duration-200"
        onClick={onClose}
      />

      {/* Drawer panel */}
      <div className="fixed right-0 top-0 h-full w-full max-w-xl bg-slate-surface border-l border-ash z-50 flex flex-col shadow-2xl animate-slide-in-right">
        {/* Header */}
        <div className="flex items-start justify-between px-5 py-4 border-b border-ash bg-graphite/60 shrink-0">
          <div className="min-w-0 flex-1 pr-3">
            <div className="flex items-center gap-2 mb-1.5">
              <span className="font-mono text-[12px] text-teal font-semibold bg-teal-dim border border-teal-border px-2 py-0.5 rounded">
                {nctId}
              </span>
              {trial?.status && (
                <span className="text-[10px] text-fog bg-ash/40 px-2 py-0.5 rounded font-medium">
                  {formatSectionType(trial.status)}
                </span>
              )}
            </div>
            {trial && (
              <h2 className="text-[14px] font-semibold text-cloud leading-snug line-clamp-3">
                {trial.official_title ?? trial.brief_title}
              </h2>
            )}
          </div>
          <div className="flex items-center gap-1 shrink-0">
            <a
              href={`https://clinicaltrials.gov/study/${nctId}`}
              target="_blank"
              rel="noopener noreferrer"
              className="p-1.5 rounded-md text-fog hover:text-cloud hover:bg-ash/60 transition-colors"
              title="Open protocol on ClinicalTrials.gov"
            >
              <ExternalLink className="w-4 h-4" />
            </a>
            <button
              type="button"
              onClick={onClose}
              className="p-1.5 rounded-md text-fog hover:text-cloud hover:bg-ash/60 transition-colors cursor-pointer"
              title="Close drawer (Esc)"
              aria-label="Close drawer"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-5 py-4 scrollbar-clinical">
          {loading ? (
            <div className="flex items-center justify-center h-32 text-[12px] text-fog">
              Loading protocol...
            </div>
          ) : error ? (
            <div className="flex items-center justify-center h-32 text-[12px] text-danger">
              {error}
            </div>
          ) : trial ? (
            <div className="space-y-5">
              {/* Metadata grid */}
              <div className="grid grid-cols-2 gap-3">
                <MetaField label="Status" value={formatSectionType(trial.status)} />
                <MetaField
                  label="Phase"
                  value={
                    trial.phases?.map((p) => p.replace("PHASE", "Phase ")).join(" / ") ??
                    "—"
                  }
                />
                <MetaField label="Category" value={formatCategory(trial.category)} />
                <MetaField label="Organization" value={trial.organization ?? "—"} />
                <MetaField
                  label="Start date"
                  value={trial.start_date ?? "—"}
                />
                <MetaField
                  label="Last updated"
                  value={trial.last_update_posted_date ?? "—"}
                />
              </div>

              {/* Conditions */}
              {trial.conditions && trial.conditions.length > 0 && (
                <div>
                  <h3 className="text-[11px] font-medium text-fog mb-2">
                    Conditions
                  </h3>
                  <div className="flex flex-wrap gap-1.5">
                    {trial.conditions.map((c, i) => (
                      <span
                        key={i}
                        className="text-[10px] text-cloud bg-ash px-1.5 py-0.5 rounded"
                      >
                        {c}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Arms */}
              {trial.arms && trial.arms.length > 0 && (
                <div>
                  <h3 className="text-[11px] font-medium text-fog mb-2">
                    Treatment arms
                  </h3>
                  <div className="space-y-2">
                    {trial.arms.map((arm, i) => (
                      <div
                        key={i}
                        className="bg-slate-surface border border-ash rounded-md p-3 text-[12px] text-cloud/90"
                      >
                        <pre className="whitespace-pre-wrap font-sans">
                          {JSON.stringify(arm, null, 2)}
                        </pre>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Primary outcomes */}
              {trial.primary_outcomes && trial.primary_outcomes.length > 0 && (
                <div>
                  <h3 className="text-[11px] font-medium text-fog mb-2">
                    Primary outcomes
                  </h3>
                  <div className="space-y-2">
                    {trial.primary_outcomes.map((outcome, i) => (
                      <div
                        key={i}
                        className="bg-slate-surface border border-ash rounded-md p-3 text-[12px] text-cloud/90"
                      >
                        <pre className="whitespace-pre-wrap font-sans">
                          {JSON.stringify(outcome, null, 2)}
                        </pre>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Protocol chunks by section */}
              {sectionGroups.size > 0 && (
                <div>
                  <h3 className="text-[11px] font-medium text-fog mb-3">
                    Protocol sections
                  </h3>
                  <div className="space-y-4">
                    {Array.from(sectionGroups.entries()).map(
                      ([sectionType, sectionChunks]) => (
                        <div key={sectionType}>
                          <h4 className="text-[12px] font-medium text-teal mb-2">
                            {formatSectionType(sectionType)}
                          </h4>
                          <div className="space-y-2">
                            {sectionChunks.map((chunk) => {
                              const isTarget = isChunkTarget(chunk, highlightSection, highlightQuote);
                              return (
                                <div
                                  key={chunk.id}
                                  ref={(el) => {
                                    if (isTarget && !targetElementRef.current) {
                                      targetElementRef.current = el;
                                    }
                                  }}
                                  className={`transition-all rounded-r-lg ${
                                    isTarget
                                      ? "border-l-4 border-l-teal bg-teal-dim/35 ring-1 ring-teal/50 shadow-xs p-3.5 my-2"
                                      : "border-l-2 border-ash pl-3 py-1"
                                  }`}
                                >
                                  {isTarget && (
                                    <div className="flex items-center gap-1.5 font-mono text-[10px] font-bold text-teal bg-teal-dim px-2 py-0.5 rounded border border-teal-border/50 mb-2 w-fit">
                                      <ShieldCheck className="w-3 h-3 text-teal" />
                                      <span>TARGET CITATION REFERENCE</span>
                                    </div>
                                  )}
                                  <div
                                    className={`text-[10px] mb-1 font-medium ${
                                      isTarget ? "text-teal" : "text-fog"
                                    }`}
                                  >
                                    {chunk.section_title}
                                  </div>
                                  <p
                                    className={`text-[12px] leading-relaxed whitespace-pre-wrap select-text ${
                                      isTarget
                                        ? "text-cloud font-medium"
                                        : "text-cloud/85"
                                    }`}
                                  >
                                    {chunk.chunk_text}
                                  </p>
                                </div>
                              );
                            })}
                          </div>
                        </div>
                      )
                    )}
                  </div>
                </div>
              )}
            </div>
          ) : null}
        </div>
      </div>
    </>
  );
}

/** Small metadata label/value pair. */
function MetaField({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-[10px] text-fog mb-0.5">{label}</div>
      <div className="text-[12px] text-cloud">{value}</div>
    </div>
  );
}
