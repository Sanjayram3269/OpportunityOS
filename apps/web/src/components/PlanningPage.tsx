"use client";

import React, { useState } from "react";
import { useApi } from "@/lib/hooks";
import { planning } from "@/lib/api";
import type { PlanningHorizonInfo } from "@/lib/types";
import {
  Card,
  EmptyState,
  ErrorState,
  Spinner,
  Badge,
  ScoreBadge,
  Select,
  SectionHeader,
} from "@/components/ui";
import {
  HORIZON_COLORS,
  OPPORTUNITY_TYPE_LABELS,
  PRIORITY_COLORS,
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

export function PlanningPage() {
  const { data, loading, error, refetch } = useApi(
    () => planning.list({ limit: 100 }),
    [],
  );
  const [horizonFilter, setHorizonFilter] = useState("");
  const [minScore, setMinScore] = useState("");

  if (loading) return <Spinner />;
  if (error) return <ErrorState message={error} onRetry={refetch} />;

  const allOpps = data?.opportunities || [];

  // Group by horizon
  const grouped: Record<PlanningHorizon, PlanningHorizonInfo[]> = {
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

  // Filter
  const visibleHorizons = horizonFilter
    ? HORIZON_CONFIG.filter((h) => h.key === horizonFilter)
    : HORIZON_CONFIG;

  const filterByScore = (opps: PlanningHorizonInfo[]) => {
    if (!minScore) return opps;
    const min = parseInt(minScore, 10);
    return opps.filter((o) => (o.match_score || 0) >= min);
  };

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Planning</h1>
        <p className="text-sm text-gray-500 mt-1">
          Organize opportunities by time horizon and priority
        </p>
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

function PlanningRow({ opp }: { opp: PlanningHorizonInfo }) {
  const horizonColor =
    HORIZON_COLORS[opp.planning_horizon as PlanningHorizon] ||
    "bg-gray-100 text-gray-600";

  return (
    <div className="px-5 py-3 flex items-center gap-4 hover:bg-gray-50 transition-colors">
      <ScoreBadge score={opp.match_score} />
      <div className="flex-1 min-w-0">
        <div className="text-sm font-medium text-gray-900 truncate">
          {opp.title}
        </div>
        <div className="text-xs text-gray-500">
          {opp.company_name || "Unknown"} ·{" "}
          {OPPORTUNITY_TYPE_LABELS[opp.opportunity_type] || opp.opportunity_type}
        </div>
      </div>
      <span
        className={`inline-flex items-center px-2 py-0.5 text-xs font-medium rounded-full ${horizonColor}`}
      >
        {opp.planning_horizon}
      </span>
      <span
        className={`inline-flex items-center px-2 py-0.5 text-xs font-medium rounded-full ${PRIORITY_COLORS[opp.priority] || "bg-gray-100 text-gray-600"}`}
      >
        Priority: {opp.planning_priority}
      </span>
      {opp.deadline && (
        <span className="text-xs text-gray-400 whitespace-nowrap">
          Due {new Date(opp.deadline).toLocaleDateString()}
        </span>
      )}
      {opp.planning_priority_reasons.length > 0 && (
        <div className="hidden lg:block">
          {opp.planning_priority_reasons.slice(0, 2).map((r, i) => (
            <div key={i} className="text-[10px] text-gray-400">
              {r}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
