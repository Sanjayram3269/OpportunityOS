"use client";

import React from "react";
import { useApi } from "@/lib/hooks";
import { dashboard } from "@/lib/api";
import type { CommandCenterResponse } from "@/lib/types";
import {
  KPICard,
  Card,
  CardHeader,
  CardContent,
  EmptyState,
  ErrorState,
  Spinner,
  Badge,
  SectionHeader,
} from "@/components/ui";

export function OverviewDashboard() {
  const data = useApi(() => dashboard.overview(), []);

  if (data.loading) return <Spinner />;
  if (data.error)
    return (
      <ErrorState
        message={data.error}
        onRetry={() => data.refetch()}
      />
    );

  const cmd = data.data as CommandCenterResponse;
  if (!cmd) return null;

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Command Center</h1>
        <p className="text-sm text-gray-500 mt-1">
          What needs your attention right now
        </p>
      </div>

      {/* Overview KPIs */}
      <KPIRow overview={cmd.overview} />

      {/* Today / Urgent */}
      <TodaySection today={cmd.today} />

      {/* Two-column: Pipeline + Opportunities */}
      <div className="grid lg:grid-cols-2 gap-6">
        <PipelineCard pipeline={cmd.pipeline} />
        <OpportunityCard opportunities={cmd.opportunities} />
      </div>

      {/* Summer 2027 */}
      <Summer2027Card summer={cmd.summer_2027} />

      {/* Two-column: Campaigns + Outreach */}
      <div className="grid lg:grid-cols-2 gap-6">
        <CampaignCard campaigns={cmd.campaigns} />
        <OutreachCard outreach={cmd.outreach} />
      </div>

      {/* Follow-ups + Analytics */}
      <div className="grid lg:grid-cols-2 gap-6">
        <FollowUpCard followups={cmd.followups} />
        <AnalyticsCard analytics={cmd.analytics} />
      </div>
    </div>
  );
}

// ── Overview KPIs ────────────────────────────────────────────────────────

function KPIRow({ overview }: { overview: CommandCenterResponse["overview"] }) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-7 gap-3">
      <KPICard label="Opportunities" value={overview.total_opportunities} icon="🎯" color="blue" />
      <KPICard label="High Match" value={overview.high_match_opportunities} icon="🔥" color="green" />
      <KPICard label="Open Actions" value={overview.open_actions} icon="⚡" color="amber" />
      <KPICard label="Applications" value={overview.total_applications} icon="📋" color="purple" />
      <KPICard label="Campaigns" value={overview.active_campaigns} icon="📁" color="indigo" />
      <KPICard label="Total Actions" value={overview.total_actions} icon="📊" color="slate" />
      <KPICard label="Total Campaigns" value={overview.total_campaigns} icon="📂" color="gray" />
    </div>
  );
}

// ── Today ────────────────────────────────────────────────────────────────

function TodaySection({ today }: { today: CommandCenterResponse["today"] }) {
  const hasUrgency =
    today.overdue_actions > 0 ||
    today.p0_actions > 0 ||
    today.overdue_deadlines > 0 ||
    today.due_today_actions > 0 ||
    today.due_followups > 0;

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <span className="text-lg">📍</span>
          <h2 className="text-lg font-semibold">Today</h2>
          {!hasUrgency && (
            <Badge className="bg-green-100 text-green-700 ml-2">All clear</Badge>
          )}
        </div>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-4">
          <StatBlock
            label="Overdue Actions"
            value={today.overdue_actions}
            urgent={today.overdue_actions > 0}
            icon="🚨"
          />
          <StatBlock
            label="P0 Actions"
            value={today.p0_actions}
            urgent={today.p0_actions > 0}
            icon="🔥"
          />
          <StatBlock
            label="P1 Actions"
            value={today.p1_actions}
            urgent={today.p1_actions > 0}
            icon="⚡"
          />
          <StatBlock
            label="Due Today"
            value={today.due_today_actions}
            urgent={today.due_today_actions > 0}
            icon="📅"
          />
          <StatBlock
            label="Overdue Deadlines"
            value={today.overdue_deadlines}
            urgent={today.overdue_deadlines > 0}
            icon="⏰"
          />
          <StatBlock
            label="Deadlines ≤3d"
            value={today.deadlines_within_3_days}
            urgent={today.deadlines_within_3_days > 0}
            icon="⏳"
          />
          <StatBlock
            label="Follow-ups Due"
            value={today.due_followups}
            urgent={today.due_followups > 0}
            icon="🔔"
          />
        </div>
      </CardContent>
    </Card>
  );
}

// ── Pipeline ─────────────────────────────────────────────────────────────

function PipelineCard({ pipeline }: { pipeline: CommandCenterResponse["pipeline"] }) {
  const stages = [
    { label: "Not Applied", key: "NOT_APPLIED", color: "bg-gray-100 text-gray-700" },
    { label: "Ready", key: "READY", color: "bg-blue-100 text-blue-700" },
    { label: "Applied", key: "APPLIED", color: "bg-indigo-100 text-indigo-700" },
    { label: "Assessment", key: "ASSESSMENT", color: "bg-violet-100 text-violet-700" },
    { label: "Interview", key: "INTERVIEW", color: "bg-amber-100 text-amber-800" },
    { label: "Final Round", key: "FINAL_ROUND", color: "bg-orange-100 text-orange-800" },
    { label: "Offer", key: "OFFER", color: "bg-green-100 text-green-700" },
    { label: "Accepted", key: "ACCEPTED", color: "bg-emerald-100 text-emerald-700" },
    { label: "Rejected", key: "REJECTED", color: "bg-red-100 text-red-700" },
    { label: "Withdrawn", key: "WITHDRAWN", color: "bg-gray-100 text-gray-500" },
  ];

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">Application Pipeline</h2>
          <Badge className="bg-indigo-100 text-indigo-700">
            {pipeline.active_count} active
          </Badge>
        </div>
      </CardHeader>
      <CardContent>
        {pipeline.total === 0 ? (
          <EmptyState
            icon="📋"
            title="No applications yet"
            description="Start tracking your applications."
          />
        ) : (
          <>
            <div className="grid grid-cols-2 gap-2 mb-4">
              {stages.map((s) => {
                const count = pipeline.by_status[s.key] || 0;
                if (count === 0) return null;
                return (
                  <div key={s.key} className="flex items-center justify-between px-3 py-1.5 rounded-lg bg-gray-50">
                    <span className="text-sm text-gray-700">{s.label}</span>
                    <Badge className={s.color}>{count}</Badge>
                  </div>
                );
              })}
            </div>
            <div className="flex gap-4 text-sm text-gray-500 border-t pt-3">
              <span>Active: <strong>{pipeline.active_count}</strong></span>
              <span>Closed: <strong>{pipeline.terminal_count}</strong></span>
              {pipeline.interview_rate != null && (
                <span>Interview rate: <strong>{(pipeline.interview_rate * 100).toFixed(0)}%</strong></span>
              )}
              {pipeline.offer_rate != null && (
                <span>Offer rate: <strong>{(pipeline.offer_rate * 100).toFixed(0)}%</strong></span>
              )}
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}

// ── Opportunities ────────────────────────────────────────────────────────

function OpportunityCard({ opportunities }: { opportunities: CommandCenterResponse["opportunities"] }) {
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">Opportunities</h2>
          <Badge className="bg-blue-100 text-blue-700">
            {opportunities.total} total
          </Badge>
        </div>
      </CardHeader>
      <CardContent>
        {opportunities.total === 0 ? (
          <EmptyState
            icon="🎯"
            title="No opportunities yet"
            description="Run discovery or add opportunities manually."
          />
        ) : (
          <>
            <div className="grid grid-cols-2 gap-2 mb-4">
              <StatBlock label="High Match (≥80)" value={opportunities.high_match} icon="🔥" />
              <StatBlock label="Not Applied" value={opportunities.not_applied} icon="📋" />
              <StatBlock label="With Deadline" value={opportunities.with_deadline} icon="⏰" />
              <StatBlock label="No Deadline" value={opportunities.without_deadline} icon="❓" />
              {opportunities.average_match_score != null && (
                <StatBlock
                  label="Avg Match"
                  value={`${opportunities.average_match_score}`}
                  icon="📊"
                />
              )}
            </div>
            {/* Match distribution */}
            {Object.keys(opportunities.match_distribution).length > 0 && (
              <div className="border-t pt-3">
                <div className="text-xs font-medium text-gray-500 mb-2">Match Distribution</div>
                <div className="flex gap-2 flex-wrap">
                  {Object.entries(opportunities.match_distribution).map(([bucket, count]) => (
                    <Badge key={bucket} className="bg-gray-100 text-gray-700">
                      {bucket.replace("_", "-")}: {count}
                    </Badge>
                  ))}
                </div>
              </div>
            )}
            {/* By horizon */}
            {Object.keys(opportunities.by_horizon).length > 0 && (
              <div className="border-t pt-3 mt-3">
                <div className="text-xs font-medium text-gray-500 mb-2">By Planning Horizon</div>
                <div className="flex gap-2 flex-wrap">
                  {Object.entries(opportunities.by_horizon).map(([hz, count]) => (
                    <Badge key={hz} className="bg-gray-100 text-gray-700">
                      {hz}: {count}
                    </Badge>
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}

// ── Summer 2027 ─────────────────────────────────────────────────────────

function Summer2027Card({ summer }: { summer: CommandCenterResponse["summer_2027"] }) {
  return (
    <Card className="border-orange-200">
      <CardHeader>
        <div className="flex items-center gap-2">
          <span className="text-lg">☀️</span>
          <h2 className="text-lg font-semibold">Summer 2027</h2>
          <Badge className="bg-orange-100 text-orange-800">{summer.total} opportunities</Badge>
        </div>
      </CardHeader>
      <CardContent>
        {summer.total === 0 ? (
          <EmptyState
            icon="☀️"
            title="No Summer 2027 opportunities"
            description="Opportunities with May-June 2027 deadlines will appear here."
          />
        ) : (
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
            <StatBlock label="Total" value={summer.total} icon="🎯" />
            <StatBlock label="High Match" value={summer.high_match} icon="🔥" urgent={summer.high_match > 0} />
            <StatBlock label="Not Applied" value={summer.not_applied} icon="📋" urgent={summer.not_applied > 0} />
            <StatBlock label="Applications" value={summer.applications} icon="📝" />
            <StatBlock label="Campaigns" value={summer.active_campaigns} icon="📁" />
            <div className="flex flex-col justify-center">
              {Object.keys(summer.application_status).length > 0 && (
                <div className="flex gap-1 flex-wrap">
                  {Object.entries(summer.application_status).map(([status, count]) => (
                    <Badge key={status} className="bg-gray-100 text-gray-600 text-xs">
                      {status}: {count}
                    </Badge>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// ── Campaigns ────────────────────────────────────────────────────────────

function CampaignCard({ campaigns }: { campaigns: CommandCenterResponse["campaigns"] }) {
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">Campaigns</h2>
          <Badge className="bg-indigo-100 text-indigo-700">
            {campaigns.active_count} active
          </Badge>
        </div>
      </CardHeader>
      <CardContent>
        {campaigns.total === 0 ? (
          <EmptyState
            icon="📁"
            title="No campaigns"
            description="Create a campaign to organize opportunities."
          />
        ) : (
          <>
            <div className="space-y-2 mb-4">
              {campaigns.active_campaigns.map((c) => (
                <div key={c.id} className="flex items-center justify-between px-3 py-2 rounded-lg bg-gray-50">
                  <div className="min-w-0">
                    <div className="text-sm font-medium text-gray-900 truncate">{c.name}</div>
                    {c.type && <div className="text-xs text-gray-500">{c.type}</div>}
                  </div>
                  <Badge className="bg-indigo-100 text-indigo-700 shrink-0 ml-2">
                    {c.opportunity_count} opps
                  </Badge>
                </div>
              ))}
            </div>
            <div className="flex gap-4 text-sm text-gray-500 border-t pt-3">
              <span>Total: <strong>{campaigns.total}</strong></span>
              <span>Opps in campaigns: <strong>{campaigns.total_campaign_opportunities}</strong></span>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}

// ── Outreach ─────────────────────────────────────────────────────────────

function OutreachCard({ outreach }: { outreach: CommandCenterResponse["outreach"] }) {
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">Outreach</h2>
          {outreach.approval_needed > 0 && (
            <Badge className="bg-amber-100 text-amber-800">
              {outreach.approval_needed} need action
            </Badge>
          )}
        </div>
      </CardHeader>
      <CardContent>
        {outreach.total === 0 ? (
          <EmptyState
            icon="✉️"
            title="No outreach yet"
            description="Draft messages to start outreach."
          />
        ) : (
          <div className="grid grid-cols-2 gap-2">
            <StatBlock label="Drafts" value={outreach.drafts} icon="📝" />
            <StatBlock
              label="Pending Approval"
              value={outreach.pending_approval}
              icon="⏳"
              urgent={outreach.pending_approval > 0}
            />
            <StatBlock label="Approved" value={outreach.approved} icon="✅" />
            <StatBlock
              label="Ready to Send"
              value={outreach.ready_to_send}
              icon="📤"
              urgent={outreach.ready_to_send > 0}
            />
            <StatBlock label="Sent" value={outreach.sent} icon="📬" />
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// ── Follow-ups ───────────────────────────────────────────────────────────

function FollowUpCard({ followups }: { followups: CommandCenterResponse["followups"] }) {
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">Follow-ups</h2>
          {followups.overdue > 0 && (
            <Badge className="bg-orange-100 text-orange-800">
              {followups.overdue} overdue
            </Badge>
          )}
        </div>
      </CardHeader>
      <CardContent>
        {followups.total === 0 ? (
          <EmptyState
            icon="🔔"
            title="No follow-ups"
            description="Follow-ups will appear as you track outreach."
          />
        ) : (
          <div className="grid grid-cols-2 gap-2">
            <StatBlock
              label="Overdue"
              value={followups.overdue}
              icon="🚨"
              urgent={followups.overdue > 0}
            />
            <StatBlock label="Pending" value={followups.pending} icon="⏳" />
            <StatBlock label="Completed" value={followups.completed} icon="✅" />
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// ── Analytics ────────────────────────────────────────────────────────────

function AnalyticsCard({ analytics }: { analytics: CommandCenterResponse["analytics"] }) {
  const funnel = analytics.application_funnel;

  return (
    <Card>
      <CardHeader>
        <h2 className="text-lg font-semibold">Analytics</h2>
      </CardHeader>
      <CardContent>
        {funnel.length === 0 ? (
          <EmptyState
            icon="📊"
            title="No analytics yet"
            description="Start applying to opportunities to see analytics."
          />
        ) : (
          <>
            {/* Application Funnel */}
            <div className="mb-4">
              <div className="text-xs font-medium text-gray-500 mb-2">Application Funnel</div>
              <div className="space-y-1">
                {funnel.map((stage) => (
                  <div key={stage.stage} className="flex items-center gap-2">
                    <div className="text-sm text-gray-700 w-40 truncate">{stage.stage}</div>
                    <div className="flex-1 bg-gray-100 rounded-full h-2">
                      <div
                        className="bg-indigo-500 rounded-full h-2 transition-all"
                        style={{
                          width:
                            funnel[0].count > 0
                              ? `${(stage.count / funnel[0].count) * 100}%`
                              : "0%",
                        }}
                      />
                    </div>
                    <span className="text-sm font-medium text-gray-900 w-10 text-right">
                      {stage.count}
                    </span>
                  </div>
                ))}
              </div>
            </div>
            {/* Rates */}
            <div className="grid grid-cols-2 gap-2 border-t pt-3">
              {analytics.application_rate != null && (
                <StatBlock
                  label="Application Rate"
                  value={`${(analytics.application_rate * 100).toFixed(0)}%`}
                  icon="📋"
                />
              )}
              {analytics.interview_rate != null && (
                <StatBlock
                  label="Interview Rate"
                  value={`${(analytics.interview_rate * 100).toFixed(0)}%`}
                  icon="🎤"
                />
              )}
              {analytics.offer_rate != null && (
                <StatBlock
                  label="Offer Rate"
                  value={`${(analytics.offer_rate * 100).toFixed(0)}%`}
                  icon="🎉"
                />
              )}
              {analytics.acceptance_rate != null && (
                <StatBlock
                  label="Acceptance Rate"
                  value={`${(analytics.acceptance_rate * 100).toFixed(0)}%`}
                  icon="✅"
                />
              )}
            </div>
            {/* Source performance */}
            {analytics.source_performance.length > 0 && (
              <div className="border-t pt-3 mt-3">
                <div className="text-xs font-medium text-gray-500 mb-2">Top Companies</div>
                <div className="space-y-1">
                  {analytics.source_performance.slice(0, 5).map((sp) => (
                    <div key={sp.source} className="flex items-center justify-between text-sm">
                      <span className="text-gray-700 truncate">{sp.source}</span>
                      <span className="text-gray-500">{sp.opportunities} opps</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}

// ── Shared ───────────────────────────────────────────────────────────────

function StatBlock({
  label,
  value,
  icon,
  urgent,
}: {
  label: string;
  value: number | string;
  icon: string;
  urgent?: boolean;
}) {
  return (
    <div className={`flex flex-col p-3 rounded-lg ${urgent ? "bg-red-50 border border-red-200" : "bg-gray-50"}`}>
      <span className="text-lg">{icon}</span>
      <span className={`text-xl font-bold ${urgent ? "text-red-700" : "text-gray-900"}`}>
        {value}
      </span>
      <span className="text-xs text-gray-500">{label}</span>
    </div>
  );
}
