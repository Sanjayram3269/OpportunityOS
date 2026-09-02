"use client";

import React, { useState } from "react";
import { useApi } from "@/lib/hooks";
import { planning, opportunities as oppsApi, applications as applicationsApi } from "@/lib/api";
import type { PlanningHorizonInfo, Opportunity } from "@/lib/types";
import {
  Card,
  EmptyState,
  ErrorState,
  Spinner,
  ScoreBadge,
  Badge,
  Button,
  Input,
  Select,
  SectionHeader,
} from "@/components/ui";
import {
  HORIZON_COLORS,
  STATUS_COLORS,
  PRIORITY_COLORS,
  OPPORTUNITY_TYPE_LABELS,
} from "@/lib/types";
import { ApplicationDetail } from "@/components/TimelineCard";

export function OpportunitiesPage() {
  // Use the planning API which returns opportunity data + planning horizon
  // This avoids duplicating the backend planning algorithm
  const { data, loading, error, refetch } = useApi(
    () => planning.list({ limit: 100 }),
    [],
  );
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [horizonFilter, setHorizonFilter] = useState("");
  const [sortField, setSortField] = useState<"match_score" | "deadline" | "title">("match_score");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [selectedOpp, setSelectedOpp] = useState<number | null>(null);

  if (loading) return <Spinner />;
  if (error) return <ErrorState message={error} onRetry={refetch} />;

  const allOpps = data?.opportunities || [];

  // Client-side filtering
  let filtered = allOpps.filter((o) => {
    if (search) {
      const q = search.toLowerCase();
      if (!o.title.toLowerCase().includes(q)) return false;
    }
    if (typeFilter && o.opportunity_type !== typeFilter) return false;
    if (statusFilter && o.status !== statusFilter) return false;
    if (horizonFilter && o.planning_horizon !== horizonFilter) return false;
    return true;
  });

  // Sort
  filtered.sort((a, b) => {
    const dir = sortDir === "asc" ? 1 : -1;
    if (sortField === "match_score") {
      return ((a.match_score || 0) - (b.match_score || 0)) * dir;
    }
    if (sortField === "deadline") {
      const aVal = a.deadline ? new Date(a.deadline).getTime() : Infinity;
      const bVal = b.deadline ? new Date(b.deadline).getTime() : Infinity;
      return (aVal - bVal) * dir;
    }
    return a.title.localeCompare(b.title) * dir;
  });

  const toggleSort = (field: typeof sortField) => {
    if (sortField === field) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortField(field);
      setSortDir("desc");
    }
  };

  const selected = selectedOpp !== null ? allOpps.find((o) => o.opportunity_id === selectedOpp) : null;

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Opportunities</h1>
        <p className="text-sm text-gray-500 mt-1">
          {allOpps.length} total · {filtered.length} shown
        </p>
      </div>

      {/* Filters */}
      <Card className="p-4">
        <div className="flex flex-wrap gap-3">
          <Input
            value={search}
            onChange={setSearch}
            placeholder="Search opportunities..."
            className="w-64"
          />
          <Select
            value={typeFilter}
            onChange={setTypeFilter}
            options={Object.entries(OPPORTUNITY_TYPE_LABELS).map(([k, v]) => ({
              label: v,
              value: k,
            }))}
            placeholder="All types"
            className="w-40"
          />
          <Select
            value={statusFilter}
            onChange={setStatusFilter}
            options={[
              { label: "Discovered", value: "DISCOVERED" },
              { label: "Matched", value: "MATCHED" },
              { label: "Qualified", value: "QUALIFIED" },
              { label: "Applied", value: "APPLIED" },
              { label: "Interviewing", value: "INTERVIEWING" },
              { label: "Accepted", value: "ACCEPTED" },
            ]}
            placeholder="All statuses"
            className="w-40"
          />
          <Select
            value={horizonFilter}
            onChange={setHorizonFilter}
            options={[
              { label: "Now", value: "NOW" },
              { label: "Upcoming", value: "UPCOMING" },
              { label: "Summer 2027", value: "SUMMER_2027" },
              { label: "Future", value: "FUTURE" },
              { label: "Unknown", value: "UNKNOWN" },
            ]}
            placeholder="All horizons"
            className="w-40"
          />
        </div>
      </Card>

      {/* Table or empty state */}
      {filtered.length === 0 ? (
        <Card>
          <EmptyState
            icon="🎯"
            title="No opportunities found"
            description={
              search || typeFilter || statusFilter || horizonFilter
                ? "Try adjusting your filters."
                : "Run discovery to find opportunities, or create one manually."
            }
          />
        </Card>
      ) : (
        <Card>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  <th className="px-4 py-3">Score</th>
                  <th className="px-4 py-3 cursor-pointer hover:text-gray-700" onClick={() => toggleSort("title")}>
                    Title {sortField === "title" ? (sortDir === "asc" ? "↑" : "↓") : ""}
                  </th>
                  <th className="px-4 py-3">Type</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Priority</th>
                  <th className="px-4 py-3 cursor-pointer hover:text-gray-700" onClick={() => toggleSort("match_score")}>
                    Match {sortField === "match_score" ? (sortDir === "asc" ? "↑" : "↓") : ""}
                  </th>
                  <th className="px-4 py-3">Horizon</th>
                  <th className="px-4 py-3 cursor-pointer hover:text-gray-700" onClick={() => toggleSort("deadline")}>
                    Deadline {sortField === "deadline" ? (sortDir === "asc" ? "↑" : "↓") : ""}
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {filtered.map((opp) => (
                  <tr
                    key={opp.opportunity_id}
                    className="table-row-hover cursor-pointer"
                    onClick={() => setSelectedOpp(selectedOpp === opp.opportunity_id ? null : opp.opportunity_id)}
                  >
                    <td className="px-4 py-3">
                      <ScoreBadge score={opp.match_score} />
                    </td>
                    <td className="px-4 py-3">
                      <div className="font-medium text-gray-900 truncate max-w-xs">
                        {opp.title}
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <Badge>{OPPORTUNITY_TYPE_LABELS[opp.opportunity_type] || opp.opportunity_type}</Badge>
                    </td>
                    <td className="px-4 py-3">
                      <Badge
                        className={
                          STATUS_COLORS[opp.status] || "bg-gray-100 text-gray-600"
                        }
                      >
                        {opp.status}
                      </Badge>
                    </td>
                    <td className="px-4 py-3">
                      <Badge
                        className={
                          PRIORITY_COLORS[opp.priority] || "bg-gray-100 text-gray-600"
                        }
                      >
                        {opp.priority}
                      </Badge>
                    </td>
                    <td className="px-4 py-3 text-gray-600">
                      {opp.match_score ?? "—"}
                    </td>
                    <td className="px-4 py-3">
                      <HorizonBadge horizon={opp.planning_horizon} />
                    </td>
                    <td className="px-4 py-3 text-gray-500 whitespace-nowrap">
                      {opp.deadline
                        ? new Date(opp.deadline).toLocaleDateString()
                        : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* Detail panel */}
      {selected && (
        <OpportunityDetailWithTimeline
          oppId={selected.opportunity_id}
          onClose={() => setSelectedOpp(null)}
        />
      )}
    </div>
  );
}

function HorizonBadge({ horizon }: { horizon: string }) {
  const colorClass =
    HORIZON_COLORS[horizon as keyof typeof HORIZON_COLORS] ||
    "bg-gray-100 text-gray-600";

  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 text-xs font-medium rounded-full ${colorClass}`}
    >
      {horizon}
    </span>
  );
}

function OpportunityDetailWithTimeline({
  oppId,
  onClose,
}: {
  oppId: number;
  onClose: () => void;
}) {
  const { data: opp, loading } = useApi(
    () => oppsApi.get(oppId),
    [oppId],
  );

  // Check if an application exists for this opportunity
  const { data: apps } = useApi(
    () => applicationsApi.list({ opportunity_id: oppId, limit: 1 }),
    [oppId],
  );

  const appId = apps && Array.isArray(apps) && apps.length > 0 ? apps[0].id : null;

  if (loading) return <Card className="p-4"><Spinner size="sm" /></Card>;
  if (!opp) return null;

  return (
    <div className="space-y-4">
      {/* Opportunity detail */}
      <Card className="mt-4">
        <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
          <div>
            <h3 className="text-lg font-semibold text-gray-900">{opp.title}</h3>
            <p className="text-sm text-gray-500">Opportunity #{opp.id}</p>
          </div>
          <Button variant="ghost" size="sm" onClick={onClose}>
            ✕ Close
          </Button>
        </div>
        <div className="p-5 space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div>
              <span className="text-gray-500">Type</span>
              <div className="font-medium">{OPPORTUNITY_TYPE_LABELS[opp.type] || opp.type}</div>
            </div>
            <div>
              <span className="text-gray-500">Status</span>
              <div className="font-medium">{opp.status}</div>
            </div>
            <div>
              <span className="text-gray-500">Priority</span>
              <div className="font-medium">{opp.priority}</div>
            </div>
            <div>
              <span className="text-gray-500">Score</span>
              <div>
                <ScoreBadge score={opp.match_score} />
              </div>
            </div>
            <div>
              <span className="text-gray-500">Deadline</span>
              <div className="font-medium">
                {opp.deadline ? new Date(opp.deadline).toLocaleDateString() : "—"}
              </div>
            </div>
            <div>
              <span className="text-gray-500">Company ID</span>
              <div className="font-medium">{opp.company_id}</div>
            </div>
            <div>
              <span className="text-gray-500">Lead ID</span>
              <div className="font-medium">{opp.lead_id ?? "—"}</div>
            </div>
            <div>
              <span className="text-gray-500">Created</span>
              <div className="font-medium">
                {new Date(opp.created_at).toLocaleDateString()}
              </div>
            </div>
          </div>

          {opp.description && (
            <div>
              <span className="text-sm text-gray-500">Description</span>
              <p className="mt-1 text-sm text-gray-700 whitespace-pre-wrap">
                {opp.description}
              </p>
            </div>
          )}

          {opp.source_url && (
            <div>
              <a
                href={opp.source_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm text-blue-600 hover:text-blue-800 underline"
              >
                View Source →
              </a>
            </div>
          )}
        </div>
      </Card>

      {/* Application Timeline (if application exists) */}
      {appId && <ApplicationDetail applicationId={appId} onClose={() => {}} />}
    </div>
  );
}
