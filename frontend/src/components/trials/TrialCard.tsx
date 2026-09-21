/**
 * Trial summary card — compact clinical trial overview.
 *
 * Shows NCT ID, brief title, cancer type, phase, and recruitment status.
 * Click to open the full protocol detail drawer.
 * Supports both dark and light ChatGPT themes cleanly.
 */

interface TrialCardProps {
  nctId: string;
  briefTitle: string;
  category: string;
  phases: string[] | null;
  status: string;
  organization: string | null;
  onClick: () => void;
}

const CATEGORY_LABELS: Record<string, string> = {
  breast_cancer: "Breast Cancer",
  non_small_cell_lung_cancer: "Lung (NSCLC)",
  colorectal_cancer: "Colorectal",
  melanoma: "Melanoma",
  lymphoma_car_t: "Lymphoma & CAR-T",
};

export function formatCategory(cat: string): string {
  if (!cat) return "Oncology";
  return (
    CATEGORY_LABELS[cat] ||
    CATEGORY_LABELS[cat.toLowerCase()] ||
    cat.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())
  );
}

/** Map recruitment status to a colored dot. */
function statusDot(status: string) {
  const s = status.toUpperCase();
  if (s.includes("RECRUITING") && !s.includes("NOT"))
    return "bg-emerald";
  if (s.includes("ACTIVE") || s.includes("ENROLLING") || s.includes("NOT_YET"))
    return "bg-amber";
  return "bg-fog";
}

/** Format phase array to readable string. */
function formatPhases(phases: string[] | null): string {
  if (!phases || phases.length === 0) return "—";
  return phases
    .map((p) => p.replace("PHASE", "Phase "))
    .join(" / ");
}

/** Format status string to readable label. */
function formatStatus(status: string): string {
  return status
    .replace(/_/g, " ")
    .toLowerCase()
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

export function TrialCard({
  nctId,
  briefTitle,
  category,
  phases,
  status,
  organization,
  onClick,
}: TrialCardProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="w-full text-left bg-slate-surface border border-ash rounded-xl p-4 hover:border-teal-border hover:shadow-md transition-all group cursor-pointer"
    >
      {/* Top row: NCT ID + status */}
      <div className="flex items-center justify-between gap-2 mb-2">
        <span className="font-mono text-[11px] text-teal font-medium">
          {nctId}
        </span>
        <div className="flex items-center gap-1.5">
          <span className={`w-1.5 h-1.5 rounded-full ${statusDot(status)}`} />
          <span className="text-[10px] text-fog font-medium">{formatStatus(status)}</span>
        </div>
      </div>

      {/* Title */}
      <h3 className="text-[13px] font-medium text-cloud leading-snug line-clamp-2 mb-3 group-hover:text-teal transition-colors">
        {briefTitle}
      </h3>

      {/* Tags row */}
      <div className="flex items-center gap-2 flex-wrap">
        <span className="inline-flex text-[10px] font-medium text-teal bg-teal-dim border border-teal-border/40 px-2 py-0.5 rounded-md">
          {formatCategory(category)}
        </span>
        <span className="text-[10px] text-fog">
          {formatPhases(phases)}
        </span>
        {organization && (
          <span className="text-[10px] text-fog/70 truncate max-w-[140px]" title={organization}>
            {organization}
          </span>
        )}
      </div>
    </button>
  );
}
