"use client";

import React from "react";
import { useApi } from "@/lib/hooks";
import { opportunities, planning, outreach, followups } from "@/lib/api";
import type { Opportunity, PlanningHorizonInfo, DraftResponse, FollowUp } from "@/lib/types";
import {
  KPICard,
  Card,
  CardHeader,
  CardContent,
  EmptyState,
  ErrorState,
  Spinner,
  ScoreBadge,
  Badge,
  StatusDot,
  SectionHeader,
} from "@/components/ui";
import {
  HORIZON_COLORS,
  OPPORTUNITY_TYPE_LABELS,
  PRIORITY_COLORS,
} from "@/lib/types";

export function OverviewDashboard() {
  const opps = useApi(() => opportunities.list(), []);
  const plan = useApi(() => planning.list({ limit: 100 }), []);
  const drafts = useApi(() => outreach.list({ limit: 100 }), []);
  const fus = useApi(() => followups.list({ limit: 100 }), []);

  const loading = opps.loading || plan.loading;
  const error = opps.error || plan.error;

  if (loading) return <Spinner />;
  if (error) return <ErrorState message={error} onRetry={() => { opps.refetch(); plan.refetch(); }} />;

  const allOpps = opps.data || [];
  const planningData = plan.data?.opportunities || [];
  const allDrafts = drafts.data?.drafts || [];
  const allFollowups = fus.data?.follow_ups || [];

  // Derive KPIs from real data
  const totalOpps = allOpps.length;
  const highMatch = allOpps.filter((o) => (o.match_score || 0) >= 80).length;

  const now = new Date();
  const soonDeadline = allOpps.filter((o) => {
    if (!o.deadline) return false;
    const d = new Date(o.deadline);
    const diff = (d.getTime() - now.getTime()) / (1000 * 60 * 60 * 24);
    return diff >= 0 && diff <= 14;
  }).length;

  const summer2027 = planningData.filter(
    (p) => p.planning_horizon === "SUMMER_2027",
  ).length;

  const activeOutreach = allDrafts.filter(
    (d) =>
      d.status !== "REJECTED" &&
      d.status !== "SENT" &&
      d.status !== "DRAFT",
  ).length;

  const pendingFollowups = allFollowups.filter(
    (f) =>
      f.status === "DUE" ||
      f.status === "PENDING" ||
      f.status === "PENDING_APPROVAL",
  ).length;

  // Priority opportunities — top by match_score, then by planning_priority
  const priorityOpps = [...planningData]
    .sort((a, b) => (b.match_score || 0) - (a.match_score || 0))
    .slice(0, 8);

  // Summer 2027 opportunities
  const summerOpps = planningData
    .filter((p) => p.planning_horizon === "SUMMER_2027")
    .slice(0, 6);

  // Needs attention: high match + no outreach, or READY_TO_SEND, or due soon
  const needsAttention = [
    ...allDrafts
      .filter((d) => d.status === "READY_TO_SEND" || d.status === "PENDING_APPROVAL")
      .slice(0, 4)
      .map((d) => ({
        type: "outreach" as const,
        label: d.status === "READY_TO_SEND" ? "Ready to send" : "Awaiting approval",
        detail: d.subject || `Draft #${d.id}`,
        status: d.status,
      })),
    ...allFollowups
      .filter((f) => f.status === "DUE")
      .slice(0, 4)
      .map((f) => ({
        type: "followup" as const,
        label: "Follow-up due",
        detail: f.reason || `Follow-up #${f.id}`,
        status: f.status,
      })),
  ];

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Overview</h1>
        <p className="text-sm text-gray-500 mt-1">
          Your opportunity pipeline at a glance
        </p>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        <KPICard label="Total Opportunities" value={totalOpps} icon="🎯" color="blue" />
        <KPICard label="High Match (80+)" value={highMatch} icon="🔥" color="green" />
        <KPICard label="Apply Soon (14d)" value={soonDeadline} icon="⏰" color="amber" />
        <KPICard label="Summer 2027" value={summer2027} icon="☀️" color="orange" />
        <KPICard label="Active Outreach" value={activeOutreach} icon="✉️" color="purple" />
        <KPICard label="Pending Follow-ups" value={pendingFollowups} icon="🔔" color="red" />
      </div>

      {/* Two-column layout */}
      <div className="grid lg:grid-cols-3 gap-6">
        {/* Priority Opportunities */}
        <div className="lg:col-span-2">
          <SectionHeader title="Priority Opportunities" count={priorityOpps.length} />
          {priorityOpps.length === 0 ? (
            <Card>
              <EmptyState
                icon="🎯"
                title="No opportunities yet"
                description="Run discovery to find opportunities, or create one manually."
              />
            </Card>
          ) : (
            <Card>
              <div className="divide-y divide-gray-100">
                {priorityOpps.map((opp) => (
                  <PriorityOppRow key={opp.opportunity_id} opp={opp} />
                ))}
              </div>
            </Card>
          )}
        </div>

        {/* Needs Attention */}
        <div>
          <SectionHeader title="Needs Attention" count={needsAttention.length} />
          {needsAttention.length === 0 ? (
            <Card>
              <EmptyState
                icon="✅"
                title="All clear"
                description="No items need your attention right now."
              />
            </Card>
          ) : (
            <Card>
              <div className="divide-y divide-gray-100">
                {needsAttention.map((item, i) => (
                  <div key={i} className="px-5 py-3 flex items-start gap-3">
                    <StatusDot status={item.status} />
                    <div className="min-w-0">
                      <div className="text-sm font-medium text-gray-900 truncate">
                        {item.label}
                      </div>
                      <div className="text-xs text-gray-500 truncate">
                        {item.detail}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          )}
        </div>
      </div>

      {/* Summer 2027 */}
      {summerOpps.length > 0 && (
        <div>
          <SectionHeader title="☀️ Summer 2027" count={summerOpps.length} />
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
            {summerOpps.map((opp) => (
              <Card key={opp.opportunity_id} className="p-4 border-orange-200">
                <div className="flex items-start justify-between mb-2">
                  <div className="min-w-0 flex-1">
                    <div className="text-sm font-semibold text-gray-900 truncate">
                      {opp.title}
                    </div>
                    <div className="text-xs text-gray-500 mt-0.5">
                      {opp.company_name || "Unknown company"}
                    </div>
                  </div>
                  <Badge className="bg-orange-100 text-orange-800 shrink-0 ml-2">
                    SUMMER 2027
                  </Badge>
                </div>
                <div className="flex items-center gap-3 text-xs text-gray-500">
                  <ScoreBadge score={opp.match_score} />
                  <span>{OPPORTUNITY_TYPE_LABELS[opp.opportunity_type] || opp.opportunity_type}</span>
                  {opp.deadline && (
                    <span>Due {new Date(opp.deadline).toLocaleDateString()}</span>
                  )}
                </div>
              </Card>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function PriorityOppRow({ opp }: { opp: PlanningHorizonInfo }) {
  const horizonClass =
    HORIZON_COLORS[opp.planning_horizon as keyof typeof HORIZON_COLORS] ||
    "bg-gray-100 text-gray-600";

  return (
    <div className="px-5 py-3 flex items-center gap-4 hover:bg-gray-50 transition-colors">
      <ScoreBadge score={opp.match_score} />
      <div className="flex-1 min-w-0">
        <div className="text-sm font-medium text-gray-900 truncate">
          {opp.title}
        </div>
        <div className="text-xs text-gray-500">
          {opp.company_name || "Unknown"} · {OPPORTUNITY_TYPE_LABELS[opp.opportunity_type] || opp.opportunity_type}
        </div>
      </div>
      <span
        className={`inline-flex items-center px-2 py-0.5 text-xs font-medium rounded-full ${horizonClass}`}
      >
        {opp.planning_horizon}
      </span>
      <span
        className={`inline-flex items-center px-2 py-0.5 text-xs font-medium rounded-full ${PRIORITY_COLORS[opp.priority] || "bg-gray-100 text-gray-600"}`}
      >
        {opp.priority}
      </span>
      {opp.deadline && (
        <span className="text-xs text-gray-400 whitespace-nowrap">
          {new Date(opp.deadline).toLocaleDateString()}
        </span>
      )}
    </div>
  );
}
