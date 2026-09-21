/**
 * Filterable catalog of landmark clinical trials.
 *
 * Renders a grid of TrialCards with category filter pills and a search input.
 * Fetches trials from the backend on mount.
 * Correctly matches database categories (breast_cancer, non_small_cell_lung_cancer, etc.).
 */

import { useEffect, useState, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { Search, FlaskConical, X } from "lucide-react";
import { api, type TrialSummary } from "@/lib/api";
import { TrialCard, formatCategory } from "./TrialCard";
import { TrialDetailDrawer } from "./TrialDetailDrawer";

interface TrialListProps {
  onClose?: () => void;
}

export function TrialList({ onClose }: TrialListProps = {}) {
  const navigate = useNavigate();
  const [trials, setTrials] = useState<TrialSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedCategoryKey, setSelectedCategoryKey] = useState<string>("ALL");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedNctId, setSelectedNctId] = useState<string | null>(null);

  useEffect(() => {
    api.trials
      .list()
      .then(setTrials)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  // Compute unique categories from the loaded trials
  const categoryOptions = useMemo(() => {
    const set = new Set<string>();
    for (const t of trials) {
      if (t.category) set.add(t.category);
    }
    // Predefined order for known categories, followed by any additional
    const preferredOrder = [
      "breast_cancer",
      "non_small_cell_lung_cancer",
      "colorectal_cancer",
      "melanoma",
      "lymphoma_car_t",
    ];

    const sorted: { key: string; label: string }[] = [{ key: "ALL", label: "All Trials" }];

    for (const key of preferredOrder) {
      if (set.has(key)) {
        sorted.push({ key, label: formatCategory(key) });
        set.delete(key);
      }
    }

    for (const key of Array.from(set)) {
      sorted.push({ key, label: formatCategory(key) });
    }

    return sorted;
  }, [trials]);

  const filtered = useMemo(() => {
    return trials.filter((t) => {
      const matchesCategory =
        selectedCategoryKey === "ALL" ||
        t.category?.toLowerCase() === selectedCategoryKey.toLowerCase();

      const q = searchQuery.toLowerCase().trim();
      const matchesSearch =
        !q ||
        t.nct_id.toLowerCase().includes(q) ||
        t.brief_title.toLowerCase().includes(q) ||
        (t.organization && t.organization.toLowerCase().includes(q)) ||
        formatCategory(t.category).toLowerCase().includes(q);

      return matchesCategory && matchesSearch;
    });
  }, [trials, selectedCategoryKey, searchQuery]);

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden bg-void">
      {/* Header & Filter bar */}
      <div className="px-6 pt-6 pb-4 border-b border-ash shrink-0">
        <div className="flex items-center justify-between gap-4 mb-4">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-teal-dim border border-teal-border flex items-center justify-center text-teal">
              <FlaskConical className="w-4 h-4" />
            </div>
            <div>
              <h1 className="text-[18px] font-semibold text-cloud tracking-tight leading-none">
                Trial Catalog
              </h1>
              <p className="text-[11px] text-fog mt-1">
                Active SCRI landmark oncology protocols ({trials.length} trials loaded)
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={onClose || (() => navigate("/chat"))}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-ash bg-slate-surface hover:bg-ash/50 text-fog hover:text-cloud text-[12px] font-medium transition-colors cursor-pointer"
            title="Close catalog and return to screening chat"
          >
            <X className="w-4 h-4" />
            <span>Close</span>
          </button>
        </div>

        {/* Category filter pills */}
        <div className="flex items-center gap-1.5 mb-3 flex-wrap">
          {categoryOptions.map((cat) => {
            const isActive = selectedCategoryKey === cat.key;
            return (
              <button
                key={cat.key}
                type="button"
                onClick={() => setSelectedCategoryKey(cat.key)}
                className={`px-3 py-1 rounded-lg text-[11px] font-medium transition-all cursor-pointer ${
                  isActive
                    ? "bg-teal text-void font-semibold shadow-xs"
                    : "bg-slate-surface text-fog hover:text-cloud hover:bg-ash/50 border border-ash/60"
                }`}
              >
                {cat.label}
              </button>
            );
          })}
        </div>

        {/* Search */}
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-fog" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search by NCT ID (e.g. NCT05794958), cancer type, or title..."
            className="w-full bg-slate-surface border border-ash rounded-xl pl-9 pr-8 py-2 text-[12px] text-cloud placeholder:text-fog/60 focus:outline-none focus:border-teal-border focus:ring-1 focus:ring-teal-border/40 transition-all"
          />
          {searchQuery && (
            <button
              type="button"
              onClick={() => setSearchQuery("")}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 p-1 text-fog hover:text-cloud cursor-pointer"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>

      {/* Trial grid */}
      <div className="flex-1 overflow-y-auto px-6 py-5 scrollbar-clinical">
        {loading ? (
          <div className="flex flex-col items-center justify-center h-48 text-[12px] text-fog">
            <div className="w-5 h-5 border-2 border-ash border-t-teal rounded-full animate-spin mb-2.5" />
            Loading clinical protocols...
          </div>
        ) : error ? (
          <div className="flex items-center justify-center h-48 text-[12px] text-danger bg-danger-dim/30 border border-danger/20 rounded-xl p-4">
            {error}
          </div>
        ) : filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-48 text-center bg-slate-surface border border-ash rounded-xl p-6">
            <p className="text-[13px] font-medium text-cloud">No matching trials found</p>
            <p className="text-[11px] text-fog mt-1">
              Try selecting "All Trials" or clearing your search query.
            </p>
            <button
              type="button"
              onClick={() => {
                setSelectedCategoryKey("ALL");
                setSearchQuery("");
              }}
              className="text-[11px] font-medium text-teal hover:underline mt-3 cursor-pointer"
            >
              Reset filters
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3.5">
            {filtered.map((trial) => (
              <TrialCard
                key={trial.nct_id}
                nctId={trial.nct_id}
                briefTitle={trial.brief_title}
                category={trial.category}
                phases={trial.phases}
                status={trial.status}
                organization={trial.organization}
                onClick={() => setSelectedNctId(trial.nct_id)}
              />
            ))}
          </div>
        )}
      </div>

      {/* Detail drawer */}
      {selectedNctId && (
        <TrialDetailDrawer
          nctId={selectedNctId}
          onClose={() => setSelectedNctId(null)}
        />
      )}
    </div>
  );
}
