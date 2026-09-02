"use client";

import React, { useState } from "react";
import { useApi } from "@/lib/hooks";
import { analyticsDeep } from "@/lib/api";
import type { AnalyticsDeepResponse } from "@/lib/types";
import {
  Card,
  CardHeader,
  CardContent,
  EmptyState,
  ErrorState,
  Spinner,
  Badge,
  SectionHeader,
} from "@/components/ui";

const DATE_PRESETS = [
  { label: "Last 7 days", days: 7 },
  { label: "Last 30 days", days: 30 },
  { label: "Last 90 days", days: 90 },
  { label: "This year", days: 365 },
];

function getDateRange(days: number) {
  const end = new Date();
  const start = new Date();
  start.setDate(end.getDate() - days);
  return {
    start_date: start.toISOString().split("T")[0],
    end_date: end.toISOString().split("T")[0],
  };
}

export function AnalyticsDeepPage() {
  const [selectedPreset, setSelectedPreset] = useState(90);
  const range = getDateRange(selectedPreset);

  const data = useApi(
    () => analyticsDeep.overview(range),
    [selectedPreset],
  );

  if (data.loading) return <Spinner />;
  if (data.error)
    return (
      <ErrorState message={data.error} onRetry={() => data.refetch()} />
    );

  const analytics = data.data as AnalyticsDeepResponse;
  if (!analytics) return null;

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Analytics</h1>
          <p className="text-sm text-gray-500 mt-1">
            Deep dive into your opportunity pipeline performance
          </p>
        </div>
        <div className="flex gap-2">
          {DATE_PRESETS.map((preset) => (
            <button
              key={preset.days}
              onClick={() => setSelectedPreset(preset.days)}
              className={`px-3 py-1.5 text-sm rounded-lg transition-colors ${
                selectedPreset === preset.days
                  ? "bg-indigo-100 text-indigo-700 font-medium"
                  : "bg-gray-100 text-gray-600 hover:bg-gray-200"
              }`}
            >
              {preset.label}
            </button>
          ))}
        </div>
      </div>

      {/* Overview KPIs */}
      <OverviewStats overview={analytics.overview} />

      {/* Trends */}
      <TrendsCard trends={analytics.trends} />

      {/* Two-column: Conversion + Velocity */}
      <div className="grid lg:grid-cols-2 gap-6">
        <ConversionCard conversion={analytics.conversion} />
        <VelocityCard velocity={analytics.velocity} />
      </div>

      {/* Source Analytics */}
      <SourceCard sources={analytics.source_analytics} />

      {/* Campaign Analytics */}
      <CampaignAnalyticsCard campaigns={analytics.campaign_analytics} />

      {/* Two-column: Type + Match */}
      <div className="grid lg:grid-cols-2 gap-6">
        <TypeCard types={analytics.type_analytics} />
        <MatchCard match={analytics.match_analytics} />
      </div>

      {/* Summer 2027 */}
      <Summer2027Card summer={analytics.summer_2027} />
    </div>
  );
}

// ── Overview Stats ────────────────────────────────────────────────────────

function OverviewStats({ overview }: { overview: AnalyticsDeepResponse["overview"] }) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      <StatCard label="Total Opportunities" value={overview.total_opportunities} icon="🎯" />
      <StatCard label="Active Applications" value={overview.active_applications} icon="📋" />
      <StatCard label="Interviews" value={overview.interviews} icon="🎤" />
      <StatCard label="Offers" value={overview.offers} icon="🎉" />
    </div>
  );
}

// ── Trends ────────────────────────────────────────────────────────────────

function TrendsCard({ trends }: { trends: AnalyticsDeepResponse["trends"] }) {
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">Trends</h2>
          <Badge className="bg-gray-100 text-gray-600">
            {trends.period_days} days
          </Badge>
        </div>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-3 gap-4">
          <TrendBlock label="Applications" data={trends.applications} />
          <TrendBlock label="Interviews" data={trends.interviews} />
          <TrendBlock label="Offers" data={trends.offers} />
        </div>
      </CardContent>
    </Card>
  );
}

function TrendBlock({
  label,
  data,
}: {
  label: string;
  data: { current: number; previous: number; change: number; change_pct: number | null };
}) {
  const isPositive = data.change > 0;
  const isNegative = data.change < 0;
  return (
    <div className="p-4 rounded-lg bg-gray-50">
      <div className="text-sm text-gray-500">{label}</div>
      <div className="text-2xl font-bold text-gray-900 mt-1">{data.current}</div>
      <div className="flex items-center gap-2 mt-1">
        <span className="text-sm text-gray-400">prev: {data.previous}</span>
        {data.change_pct != null && (
          <span
            className={`text-sm font-medium ${
              isPositive ? "text-green-600" : isNegative ? "text-red-600" : "text-gray-500"
            }`}
          >
            {isPositive ? "+" : ""}
            {data.change_pct}%
          </span>
        )}
        {data.change_pct == null && data.previous === 0 && data.current > 0 && (
          <span className="text-sm text-gray-400">new</span>
        )}
      </div>
    </div>
  );
}

// ── Conversion ────────────────────────────────────────────────────────────

function ConversionCard({ conversion }: { conversion: AnalyticsDeepResponse["conversion"] }) {
  return (
    <Card>
      <CardHeader>
        <h2 className="text-lg font-semibold">Conversion Funnel</h2>
      </CardHeader>
      <CardContent>
        <div className="space-y-2">
          {conversion.stages.map((stage) => (
            <div key={stage.stage} className="flex items-center gap-3">
              <div className="w-32 text-sm text-gray-700 truncate">{stage.stage}</div>
              <div className="flex-1 bg-gray-100 rounded-full h-3">
                <div
                  className="bg-indigo-500 rounded-full h-3 transition-all"
                  style={{
                    width:
                      stage.at_or_beyond > 0
                        ? `${(stage.at_or_beyond / (conversion.stages[0]?.at_or_beyond || 1)) * 100}%`
                        : "0%",
                  }}
                />
              </div>
              <span className="text-sm font-medium text-gray-900 w-10 text-right">
                {stage.count}
              </span>
              {stage.conversion_rate != null && (
                <span className="text-xs text-gray-500 w-16 text-right">
                  {(stage.conversion_rate * 100).toFixed(0)}%
                </span>
              )}
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

// ── Velocity ──────────────────────────────────────────────────────────────

function VelocityCard({ velocity }: { velocity: AnalyticsDeepResponse["velocity"] }) {
  const transitions = Object.entries(velocity.transitions);

  return (
    <Card>
      <CardHeader>
        <h2 className="text-lg font-semibold">Pipeline Velocity</h2>
      </CardHeader>
      <CardContent>
        {transitions.length === 0 ? (
          <EmptyState
            icon="⏱️"
            title="No velocity data"
            description="Complete more pipeline transitions to see duration metrics."
          />
        ) : (
          <div className="space-y-2">
            {transitions.map(([key, t]) => (
              <div key={key} className="flex items-center justify-between px-3 py-2 rounded-lg bg-gray-50">
                <span className="text-sm text-gray-700">{key.replace("_to_", " → ")}</span>
                <div className="flex items-center gap-3">
                  {t.avg_days != null && (
                    <span className="text-sm text-gray-500">avg {t.avg_days}d</span>
                  )}
                  {t.median_days != null && (
                    <span className="text-sm text-gray-500">med {t.median_days}d</span>
                  )}
                  <Badge className="bg-gray-100 text-gray-600">n={t.count}</Badge>
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// ── Source Analytics ──────────────────────────────────────────────────────

function SourceCard({ sources }: { sources: AnalyticsDeepResponse["source_analytics"] }) {
  return (
    <Card>
      <CardHeader>
        <h2 className="text-lg font-semibold">Source Performance</h2>
      </CardHeader>
      <CardContent>
        {sources.sources.length === 0 ? (
          <EmptyState
            icon="🏢"
            title="No source data"
            description="Discover and match opportunities to see source analytics."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-gray-500 border-b">
                  <th className="pb-2 font-medium">Company</th>
                  <th className="pb-2 font-medium text-right">Opps</th>
                  <th className="pb-2 font-medium text-right">High Match</th>
                  <th className="pb-2 font-medium text-right">Applied</th>
                  <th className="pb-2 font-medium text-right">Interviews</th>
                  <th className="pb-2 font-medium text-right">Offers</th>
                </tr>
              </thead>
              <tbody>
                {sources.sources.map((s) => (
                  <tr key={s.company} className="border-b border-gray-50">
                    <td className="py-2 font-medium text-gray-900 truncate max-w-[200px]">{s.company}</td>
                    <td className="py-2 text-right">{s.opportunities}</td>
                    <td className="py-2 text-right">{s.high_match}</td>
                    <td className="py-2 text-right">{s.applications}</td>
                    <td className="py-2 text-right">{s.interviews}</td>
                    <td className="py-2 text-right">{s.offers}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// ── Campaign Analytics ────────────────────────────────────────────────────

function CampaignAnalyticsCard({ campaigns }: { campaigns: AnalyticsDeepResponse["campaign_analytics"] }) {
  return (
    <Card>
      <CardHeader>
        <h2 className="text-lg font-semibold">Campaign Performance</h2>
      </CardHeader>
      <CardContent>
        {campaigns.campaigns.length === 0 ? (
          <EmptyState
            icon="📁"
            title="No campaign data"
            description="Create campaigns and add opportunities to see analytics."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-gray-500 border-b">
                  <th className="pb-2 font-medium">Campaign</th>
                  <th className="pb-2 font-medium">Status</th>
                  <th className="pb-2 font-medium text-right">Opps</th>
                  <th className="pb-2 font-medium text-right">Applied</th>
                  <th className="pb-2 font-medium text-right">Interviews</th>
                  <th className="pb-2 font-medium text-right">Offers</th>
                </tr>
              </thead>
              <tbody>
                {campaigns.campaigns.map((c) => (
                  <tr key={c.campaign_id} className="border-b border-gray-50">
                    <td className="py-2 font-medium text-gray-900">{c.campaign_name}</td>
                    <td className="py-2">
                      <Badge className={c.status === "ACTIVE" ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-600"}>
                        {c.status}
                      </Badge>
                    </td>
                    <td className="py-2 text-right">{c.opportunities}</td>
                    <td className="py-2 text-right">{c.applications}</td>
                    <td className="py-2 text-right">{c.interviews}</td>
                    <td className="py-2 text-right">{c.offers}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// ── Type Analytics ────────────────────────────────────────────────────────

function TypeCard({ types }: { types: AnalyticsDeepResponse["type_analytics"] }) {
  return (
    <Card>
      <CardHeader>
        <h2 className="text-lg font-semibold">By Opportunity Type</h2>
      </CardHeader>
      <CardContent>
        {types.types.length === 0 ? (
          <EmptyState icon="📊" title="No type data" description="Discover opportunities to see type analytics." />
        ) : (
          <div className="space-y-2">
            {types.types.map((t) => (
              <div key={t.type} className="flex items-center justify-between px-3 py-2 rounded-lg bg-gray-50">
                <span className="text-sm font-medium text-gray-900">{t.type}</span>
                <div className="flex items-center gap-4 text-sm text-gray-500">
                  <span>{t.opportunities} opps</span>
                  <span>{t.applications} applied</span>
                  <span>{t.interviews} interviews</span>
                  <span>{t.offers} offers</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// ── Match Analytics ───────────────────────────────────────────────────────

function MatchCard({ match }: { match: AnalyticsDeepResponse["match_analytics"] }) {
  return (
    <Card>
      <CardHeader>
        <h2 className="text-lg font-semibold">By Match Score</h2>
      </CardHeader>
      <CardContent>
        {match.buckets.length === 0 ? (
          <EmptyState icon="🎯" title="No match data" description="Score opportunities to see match analytics." />
        ) : (
          <div className="space-y-2">
            {match.buckets.map((b) => (
              <div key={b.bucket} className="flex items-center gap-3 px-3 py-2 rounded-lg bg-gray-50">
                <span className="text-sm font-medium text-gray-900 w-16">{b.range}</span>
                <div className="flex-1 bg-gray-200 rounded-full h-2">
                  <div
                    className="bg-indigo-500 rounded-full h-2 transition-all"
                    style={{
                      width:
                        match.buckets[0]?.opportunities > 0
                          ? `${(b.opportunities / match.buckets[0].opportunities) * 100}%`
                          : "0%",
                    }}
                  />
                </div>
                <span className="text-sm text-gray-500 w-20 text-right">{b.opportunities} opps</span>
                <span className="text-sm text-gray-500 w-16 text-right">{b.applications} app</span>
                {b.application_rate != null && (
                  <span className="text-xs text-gray-400 w-12 text-right">
                    {(b.application_rate * 100).toFixed(0)}%
                  </span>
                )}
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// ── Summer 2027 ──────────────────────────────────────────────────────────

function Summer2027Card({ summer }: { summer: AnalyticsDeepResponse["summer_2027"] }) {
  return (
    <Card className="border-orange-200">
      <CardHeader>
        <div className="flex items-center gap-2">
          <span className="text-lg">☀️</span>
          <h2 className="text-lg font-semibold">Summer 2027 Analytics</h2>
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
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="p-3 rounded-lg bg-orange-50">
              <div className="text-2xl font-bold text-orange-700">{summer.total}</div>
              <div className="text-xs text-orange-600">Total</div>
            </div>
            <div className="p-3 rounded-lg bg-orange-50">
              <div className="text-2xl font-bold text-orange-700">{summer.high_match}</div>
              <div className="text-xs text-orange-600">High Match</div>
            </div>
            <div className="p-3 rounded-lg bg-orange-50">
              <div className="text-2xl font-bold text-orange-700">{summer.not_applied}</div>
              <div className="text-xs text-orange-600">Not Applied</div>
            </div>
            <div className="p-3 rounded-lg bg-orange-50">
              <div className="text-2xl font-bold text-orange-700">{summer.interviews}</div>
              <div className="text-xs text-orange-600">Interviews</div>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// ── Shared ────────────────────────────────────────────────────────────────

function StatCard({
  label,
  value,
  icon,
}: {
  label: string;
  value: number;
  icon: string;
}) {
  return (
    <Card className="p-4">
      <div className="flex items-center gap-3">
        <span className="text-2xl">{icon}</span>
        <div>
          <div className="text-2xl font-bold text-gray-900">{value}</div>
          <div className="text-sm text-gray-500">{label}</div>
        </div>
      </div>
    </Card>
  );
}
