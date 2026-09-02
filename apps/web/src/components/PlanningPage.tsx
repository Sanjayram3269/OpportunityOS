"use client";

import React, { useState, useCallback } from "react";
import { useApi } from "@/lib/hooks";
import { planning } from "@/lib/api";
import type { EnrichedPlanningItem } from "@/lib/types";
import {
  Card,
  EmptyState,
  ErrorState,
  Spinner,
  ScoreBadge,
  Select,
  SectionHeader,
} from "@/components/ui";
import {
  HORIZON_COLORS,
  OPPORTUNITY_TYPE_LABELS,
  type PlanningHorizon,
} from "@/lib/types";

const HORIZON_CONFIG: {
  key: PlanningHorizon;
  label: string;
  icon: string;
  description: string;
}[] = [
  {
    key: "NOW",
    label: "Now",
    icon: "🔴",
    description: "Deadline within 7 days — act immediately",
  },
  {
    key: "UPCOMING",
    label: "Upcoming",
    icon: "🟡",
    description: "Deadline within 8–30 days",
  },
  {
    key: "SUMMER_2027",
    label: "Summer 2027",
    icon: "☀️",
    description: "May–June 2027 planning window",
  },
  {
    key: "FUTURE",
    label: "Future",
    icon: "🔵",
    description: "Deadline more than 30 days away",
  },
  {
    key: "UNKNOWN",
    label: "Unknown",
    icon: "⚪",
    description: "Insufficient temporal data",
  },
];

const APPLICATION_STATUS_COLORS: Record<string, string> = {
  NOT_APPLIED: "bg-gray-100 text-gray-600",
  READY: "bg-blue-100 text-blue-700",
  APPLIED: "bg-purple-100 text-purple-700",
  ASSESSMENT: "bg-indigo-100 text-indigo-700",
  INTERVIEW: "bg-amber-100 text-amber-800",
  FINAL_ROUND: "bg-orange-100 text-orange-800",
  OFFER: "bg-green-100 text-green-700",
  ACCEPTED: "bg-emerald-100 text-emerald-700",
  REJECTED: "bg-red-100 text-red-700",
  WITHDRAWN: "bg-gray-100 text-gray-500",
};

const OUTREACH_STATUS_COLORS: Record<string, string> = {
  NO_OUTREACH: "bg-gray-50 text-gray-400",
  DRAFT: "bg-slate-100 text-slate-600",
  PENDING_APPROVAL: "bg-amber-100 text-amber-700",
  READY_TO_SEND: "bg-blue-100 text-blue-700",
  SENT: "bg-emerald-100 text-emerald-700",
};

export function PlanningPage() {
  const [horizonFilter, setHorizonFilter] = useState("");
  const [minScore, setMinScore] = useState("");
  const [campaignFilter, setCampaignFilter] = useState<string>("");

  const { data, loading, error, refetch } = useApi(
    useCallback(() => planning.enriched({ limit: 100 }), []),
    [],
  );

  if (loading) return <Spinner />;
  if (error) return <ErrorState message={error} onRetry={refetch} />;

  const allOpps = data?.opportunities || [];

  // Group by horizon
  const grouped: Record<PlanningHorizon, EnrichedPlanningItem[]> = {
    NOW: [],
    UPCOMING: [],
    SUMMER_2027: [],
    FUTURE: [],
    UNKNOWN: [],
  };

  allOpps.forEach((opp) => {
    const h = opp.planning_horizon as PlanningHorizon;
    if (grouped[h]) grouped[h].push(opp);
  });

  // Collect all unique campaign names for filter
  const allCampaigns = new Set<string>();
  allOpps.forEach((opp) => {
    opp.campaigns?.forEach((c) => allCampaigns.add(c));
  });

  // Filter
  const visibleHorizons = horizonFilter
    ? HORIZON_CONFIG.filter((h) => h.key === horizonFilter)
    : HORIZON_CONFIG;

  const filterByScore = (opps: EnrichedPlanningItem[]) => {
    let filtered = opps;
    if (minScore) {
      const min = parseInt(minScore, 10);
      filtered = filtered.filter((o) => (o.match_score || 0) >= min);
    }
    if (campaignFilter) {
      filtered = filtered.filter((o) => o.campaigns?.includes(campaignFilter));
    }
    return filtered;
  };

  // Summary stats
  const totalNotApplied = allOpps.filter(
    (o) => o.application_status === "NOT_APPLIED"
  ).length;
  const totalInInterview = allOpps.filter(
    (o) => o.application_status === "INTERVIEW" || o.application_status === "FINAL_ROUND"
  ).length;
  const totalOffers = allOpps.filter(
    (o) => o.application_status === "OFFER" || o.application_status === "ACCEPTED"
  ).length;

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Planning</h1>
        <p className="text-sm text-gray-500 mt-1">
          Organize opportunities by time horizon, application status, and priority
        </p>
      </div>

      {/* Quick stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Card className="p-3">
          <div className="text-2xl font-bold text-gray-900">{allOpps.length}</div>
          <div className="text-xs text-gray-500">Total Opportunities</div>
        </Card>
        <Card className="p-3">
          <div className="text-2xl font-bold text-blue-600">{totalNotApplied}</div>
          <div className="text-xs text-gray-500">Not Applied</div>
        </Card>
        <Card className="p-3">
          <div className="text-2xl font-bold text-amber-600">{totalInInterview}</div>
          <div className="text-xs text-gray-500">In Interview</div>
        </Card>
        <Card className="p-3">
          <div className="text-2xl font-bold text-green-600">{totalOffers}</div>
          <div className="text-xs text-gray-500">Offers</div>
        </Card>
      </div>

      {/* Filters */}
      <Card className="p-4">
        <div className="flex flex-wrap gap-3">
          <Select
            value={horizonFilter}
            onChange={setHorizonFilter}
            options={HORIZON_CONFIG.map((h) => ({
              label: `${h.icon} ${h.label} (${(grouped[h.key] || []).length})`,
              value: h.key,
            }))}
            placeholder="All horizons"
            className="w-48"
          />
          {allCampaigns.size > 0 && (
            <Select
              value={campaignFilter}
              onChange={setCampaignFilter}
              options={Array.from(allCampaigns).map((c) => ({
                label: c,
                value: c,
              }))}
              placeholder="All campaigns"
              className="w-48"
            />
          )}
          <div className="flex items-center gap-2">
            <span className="text-sm text-gray-500">Min score:</span>
            <input
              type="number"
              min={0}
              max={100}
              value={minScore}
              onChange={(e) => setMinScore(e.target.value)}
              placeholder="0"
              className="w-20 rounded-lg border border-gray-300 px-2 py-1.5 text-sm focus:border-blue-500 focus:outline-none"
            />
          </div>
        </div>
      </Card>

      {/* Horizon sections */}
      {visibleHorizons.map((config) => {
        const opps = filterByScore(grouped[config.key] || []);
        if (opps.length === 0 && horizonFilter) return null;

        const isSummer2027 = config.key === "SUMMER_2027";

        return (
          <section key={config.key}>
            <SectionHeader
              title={`${config.icon} ${config.label}`}
              count={opps.length}
            />
            {opps.length === 0 ? (
              <Card className="p-4">
                <p className="text-sm text-gray-500 text-center py-4">
                  No opportunities in this horizon
                  {minScore ? ` with score ≥ ${minScore}` : ""}
                  {campaignFilter ? ` in campaign "${campaignFilter}"` : ""}
                </p>
              </Card>
            ) : (
              <Card
                className={
                  isSummer2027
                    ? "border-2 border-orange-200"
                    : ""
                }
              >
                <div className="divide-y divide-gray-100">
                  {opps.map((opp) => (
                    <PlanningRow key={opp.opportunity_id} opp={opp} />
                  ))}
                </div>
              </Card>
            )}
          </section>
        );
      })}

      {/* Summer 2027 info */}
      {(!horizonFilter || horizonFilter === "SUMMER_2027") &&
        grouped.SUMMER_2027.length > 0 && (
          <Card className="p-4 bg-orange-50 border-orange-200">
            <div className="flex items-start gap-3">
              <span className="text-2xl">☀️</span>
              <div>
                <h3 className="text-sm font-semibold text-orange-900">
                  Summer 2027 Planning Window
                </h3>
                <p className="text-xs text-orange-700 mt-1">
                  Opportunities with deadlines between May 1 and June 30, 2027
                  are classified as Summer 2027. Start preparing applications
                  now — many summer programs open early.
                </p>
              </div>
            </div>
          </Card>
        )}
    </div>
  );
}

function PlanningRow({ opp }: { opp: EnrichedPlanningItem }) {
  const horizonColor =
    HORIZON_COLORS[opp.planning_horizon as PlanningHorizon] ||
    "bg-gray-100 text-gray-600";

  const appColor =
    APPLICATION_STATUS_COLORS[opp.application_status] ||
    "bg-gray-100 text-gray-600";

  const outreachColor =
    OUTREACH_STATUS_COLORS[opp.outreach_status] ||
    "bg-gray-100 text-gray-600";

  return (
    <div className="px-5 py-3 flex items-center gap-3 hover:bg-gray-50 transition-colors">
      <ScoreBadge score={opp.match_score} />
      <div className="flex-1 min-w-0">
        <div className="text-sm font-medium text-gray-900 truncate">
          {opp.title}
        </div>
        <div className="text-xs text-gray-500">
          {opp.company_name || "Unknown"} ·{" "}
          {OPPORTUNITY_TYPE_LABELS[opp.opportunity_type] || opp.opportunity_type}
        </div>
        {/* Planning explanation */}
        {opp.planning_explanation && (
          <div className="text-[11px] text-gray-400 mt-0.5 truncate">
            {opp.planning_explanation}
          </div>
        )}
      </div>

      {/* Application status */}
      <span
        className={`inline-flex items-center px-2 py-0.5 text-xs font-medium rounded-full ${appColor}`}
      >
        {opp.application_status.replace("_", " ")}
      </span>

      {/* Outreach status */}
      {opp.outreach_status !== "NO_OUTREACH" && (
        <span
          className={`inline-flex items-center px-2 py-0.5 text-xs font-medium rounded-full ${outreachColor}`}
        >
          {opp.outreach_status.replace("_", " ")}
        </span>
      )}

      {/* Horizon */}
      <span
        className={`inline-flex items-center px-2 py-0.5 text-xs font-medium rounded-full ${horizonColor}`}
      >
        {opp.planning_horizon}
      </span>

      {/* Campaign badges */}
      {opp.campaigns && opp.campaigns.length > 0 && (
        <div className="hidden md:flex gap-1">
          {opp.campaigns.slice(0, 2).map((c) => (
            <span
              key={c}
              className="inline-flex items-center px-1.5 py-0.5 text-[10px] font-medium rounded bg-indigo-50 text-indigo-600"
            >
              {c}
            </span>
          ))}
          {opp.campaigns.length > 2 && (
            <span className="text-[10px] text-gray-400">
              +{opp.campaigns.length - 2}
            </span>
          )}
        </div>
      )}

      {/* Deadline */}
      {opp.deadline && (
        <span className="text-xs text-gray-400 whitespace-nowrap">
          Due {new Date(opp.deadline).toLocaleDateString()}
        </span>
      )}
    </div>
  );
}
