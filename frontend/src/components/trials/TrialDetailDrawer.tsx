/**
 * Full protocol viewer drawer — slides in from the right.
 *
 * Fetches TrialDetail on mount and displays the complete protocol:
 * official title, phases, arms, conditions, primary outcomes,
 * and scrollable protocol chunks grouped by section type.
 */

import { useEffect, useState } from "react";
import { X } from "lucide-react";
import { api, type TrialDetail } from "@/lib/api";
import { formatCategory } from "./TrialCard";

interface TrialDetailDrawerProps {
  nctId: string;
  onClose: () => void;
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

export function TrialDetailDrawer({ nctId, onClose }: TrialDetailDrawerProps) {
  const [trial, setTrial] = useState<TrialDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    api.trials
      .get(nctId)
      .then(setTrial)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [nctId]);

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
      <div className="fixed right-0 top-0 h-full w-full max-w-xl bg-graphite border-l border-ash z-50 flex flex-col animate-in slide-in-from-right duration-250">
        {/* Header */}
        <div className="flex items-start justify-between px-5 py-4 border-b border-ash shrink-0">
          <div className="min-w-0 flex-1 pr-3">
            <span className="font-mono text-[11px] text-teal font-medium">
              {nctId}
            </span>
            {trial && (
              <h2 className="text-[14px] font-medium text-cloud leading-snug mt-1.5 line-clamp-3">
                {trial.official_title ?? trial.brief_title}
              </h2>
            )}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-md text-fog hover:text-cloud hover:bg-ash/60 transition-colors shrink-0 cursor-pointer"
            aria-label="Close drawer"
          >
            <X className="w-4 h-4" />
          </button>
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
                            {sectionChunks.map((chunk) => (
                              <div
                                key={chunk.id}
                                className="border-l-2 border-ash pl-3 py-1"
                              >
                                <div className="text-[10px] text-fog mb-1">
                                  {chunk.section_title}
                                </div>
                                <p className="text-[12px] text-cloud/85 leading-relaxed whitespace-pre-wrap select-text">
                                  {chunk.chunk_text}
                                </p>
                              </div>
                            ))}
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
