"use client";

import React, { useState, useCallback } from "react";
import { useApi } from "@/lib/hooks";
import { campaigns } from "@/lib/api";
import type { Campaign, EnhancedCampaignSummary, CampaignPlanningItem, CampaignActionSummary } from "@/lib/types";
import {
  Card,
  CardHeader,
  CardContent,
  EmptyState,
  ErrorState,
  Spinner,
  Button,
  Badge,
  StatusDot,
  SectionHeader,
} from "@/components/ui";
import { STATUS_COLORS, HORIZON_COLORS, OPPORTUNITY_TYPE_LABELS } from "@/lib/types";

export function CampaignsPage() {
  const { data, loading, error, refetch } = useApi(() => campaigns.list({ limit: 100 }), []);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  if (loading) return <Spinner />;
  if (error) return <ErrorState message={error} onRetry={refetch} />;

  const allCampaigns = data?.campaigns || [];

  const doAction = async (key: string, action: () => Promise<unknown>) => {
    setActionLoading(key);
    try {
      await action();
      refetch();
    } catch {
      // handled
    } finally {
      setActionLoading(null);
    }
  };

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Campaigns</h1>
        <p className="text-sm text-gray-500 mt-1">
          Organize opportunities into targeted campaigns and track progress
        </p>
      </div>

      {allCampaigns.length === 0 ? (
        <Card>
          <EmptyState
            icon="📁"
            title="No campaigns yet"
            description="Create a campaign to organize related opportunities."
          />
        </Card>
      ) : (
        <div className="space-y-4">
          {allCampaigns.map((campaign) => (
            <CampaignCard
              key={campaign.id}
              campaign={campaign}
              isSelected={selectedId === campaign.id}
              onSelect={() => setSelectedId(selectedId === campaign.id ? null : campaign.id)}
              actionLoading={actionLoading}
              onAction={doAction}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function CampaignCard({
  campaign,
  isSelected,
  onSelect,
  actionLoading,
  onAction,
}: {
  campaign: Campaign;
  isSelected: boolean;
  onSelect: () => void;
  actionLoading: string | null;
  onAction: (key: string, action: () => Promise<unknown>) => void;
}) {
  const { data: summary, loading: summaryLoading } = useApi(
    useCallback(() => campaigns.enhancedSummary(campaign.id), [campaign.id]),
    [campaign.id],
  );

  const { data: planning, loading: planningLoading } = useApi(
    useCallback(
      () => isSelected ? campaigns.planning(campaign.id) : Promise.resolve(null),
      [isSelected, campaign.id],
    ),
    [isSelected, campaign.id],
  );

  const { data: actionSummary, loading: actionLoading2 } = useApi(
    useCallback(
      () => isSelected ? campaigns.actionSummary(campaign.id) : Promise.resolve(null),
      [isSelected, campaign.id],
    ),
    [isSelected, campaign.id],
  );

  return (
    <Card
      className={`transition-colors ${
        isSelected ? "border-blue-300" : "hover:border-gray-300"
      }`}
    >
      <div
        className="p-5 cursor-pointer"
        onClick={onSelect}
      >
        <div className="flex items-start justify-between mb-2">
          <div className="min-w-0">
            <h3 className="text-sm font-semibold text-gray-900 truncate">
              {campaign.name}
            </h3>
            <div className="text-xs text-gray-500 mt-0.5">
              {campaign.type}
            </div>
          </div>
          <div className="flex items-center gap-2">
            <StatusDot status={campaign.status} />
            <Badge
              className={
                STATUS_COLORS[campaign.status] ||
                "bg-gray-100 text-gray-600"
              }
            >
              {campaign.status}
            </Badge>
          </div>
        </div>

        {campaign.description && (
          <p className="text-xs text-gray-500 line-clamp-2 mb-3">
            {campaign.description}
          </p>
        )}

        {/* Enhanced Summary Cards */}
        {summary && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mb-3">
            <div className="bg-gray-50 rounded-lg p-2 text-center">
              <div className="text-lg font-bold text-gray-900">
                {summary.total_opportunities}
              </div>
              <div className="text-[10px] text-gray-500">Opportunities</div>
            </div>
            <div className="bg-gray-50 rounded-lg p-2 text-center">
              <div className="text-lg font-bold text-blue-600">
                {summary.not_applied}
              </div>
              <div className="text-[10px] text-gray-500">Not Applied</div>
            </div>
            <div className="bg-gray-50 rounded-lg p-2 text-center">
              <div className="text-lg font-bold text-amber-600">
                {summary.interviews}
              </div>
              <div className="text-[10px] text-gray-500">Interviews</div>
            </div>
            <div className="bg-gray-50 rounded-lg p-2 text-center">
              <div className="text-lg font-bold text-green-600">
                {summary.offers}
              </div>
              <div className="text-[10px] text-gray-500">Offers</div>
            </div>
          </div>
        )}

        {summaryLoading && (
          <div className="text-xs text-gray-400 mb-3">Loading summary...</div>
        )}

        {/* Planning horizon distribution */}
        {summary?.planning_horizon_distribution && Object.keys(summary.planning_horizon_distribution).length > 0 && (
          <div className="flex flex-wrap gap-1.5 mb-3">
            {Object.entries(summary.planning_horizon_distribution).map(([horizon, count]) => (
              <span
                key={horizon}
                className={`inline-flex items-center px-2 py-0.5 text-xs font-medium rounded-full ${
                  HORIZON_COLORS[horizon as keyof typeof HORIZON_COLORS] || "bg-gray-100 text-gray-600"
                }`}
              >
                {horizon}: {count}
              </span>
            ))}
          </div>
        )}

        {/* Action summary */}
        {actionSummary && actionSummary.total_actions > 0 && (
          <div className="flex items-center gap-2 text-xs">
            <span className="text-gray-500">Actions:</span>
            {Object.entries(actionSummary.by_priority).map(([priority, count]) => (
              <span
                key={priority}
                className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${
                  priority === "P0"
                    ? "bg-red-100 text-red-700"
                    : priority === "P1"
                    ? "bg-amber-100 text-amber-700"
                    : priority === "P2"
                    ? "bg-blue-100 text-blue-700"
                    : "bg-gray-100 text-gray-600"
                }`}
              >
                {priority}: {count}
              </span>
            ))}
            {actionSummary.overdue_actions > 0 && (
              <span className="text-red-600 font-medium">
                {actionSummary.overdue_actions} overdue
              </span>
            )}
          </div>
        )}

        {/* Lifecycle actions */}
        {isSelected && (
          <div className="mt-3 flex gap-2 flex-wrap border-t border-gray-100 pt-3">
            {campaign.status === "DRAFT" && (
              <Button
                size="sm"
                onClick={(e?) => {
                  e?.stopPropagation();
                  onAction(`activate-${campaign.id}`, () =>
                    campaigns.activate(campaign.id),
                  );
                }}
                loading={actionLoading === `activate-${campaign.id}`}
              >
                Activate
              </Button>
            )}
            {campaign.status === "ACTIVE" && (
              <>
                <Button
                  size="sm"
                  onClick={(e?) => {
                    e?.stopPropagation();
                    onAction(`pause-${campaign.id}`, () =>
                      campaigns.pause(campaign.id),
                    );
                  }}
                  loading={actionLoading === `pause-${campaign.id}`}
                >
                  Pause
                </Button>
                <Button
                  size="sm"
                  onClick={(e?) => {
                    e?.stopPropagation();
                    onAction(`complete-${campaign.id}`, () =>
                      campaigns.complete(campaign.id),
                    );
                  }}
                  loading={actionLoading === `complete-${campaign.id}`}
                >
                  Complete
                </Button>
              </>
            )}
            {campaign.status === "PAUSED" && (
              <>
                <Button
                  size="sm"
                  onClick={(e?) => {
                    e?.stopPropagation();
                    onAction(`activate-${campaign.id}`, () =>
                      campaigns.activate(campaign.id),
                    );
                  }}
                  loading={actionLoading === `activate-${campaign.id}`}
                >
                  Resume
                </Button>
                <Button
                  size="sm"
                  onClick={(e?) => {
                    e?.stopPropagation();
                    onAction(`complete-${campaign.id}`, () =>
                      campaigns.complete(campaign.id),
                    );
                  }}
                  loading={actionLoading === `complete-${campaign.id}`}
                >
                  Complete
                </Button>
              </>
            )}
            {campaign.status !== "ARCHIVED" && (
              <Button
                size="sm"
                variant="secondary"
                onClick={(e?) => {
                  e?.stopPropagation();
                  onAction(`archive-${campaign.id}`, () =>
                    campaigns.archive(campaign.id),
                  );
                }}
                loading={actionLoading === `archive-${campaign.id}`}
              >
                Archive
              </Button>
            )}
          </div>
        )}
      </div>

      {/* Campaign planning opportunities */}
      {isSelected && planning && planning.opportunities && planning.opportunities.length > 0 && (
        <div className="border-t border-gray-100 px-5 pb-4">
          <h4 className="text-xs font-semibold text-gray-700 mb-2 mt-3">
            Planning ({planning.total} opportunities)
          </h4>
          <div className="divide-y divide-gray-50">
            {planning.opportunities.slice(0, 5).map((opp) => (
              <div key={opp.opportunity_id} className="py-2 flex items-center gap-3 text-xs">
                <ScoreBadgeInline score={opp.match_score} />
                <div className="flex-1 min-w-0">
                  <span className="font-medium text-gray-800 truncate block">
                    {opp.title}
                  </span>
                  <span className="text-gray-400">
                    {opp.company_name || "Unknown"} · {opp.application_status.replace("_", " ")}
                  </span>
                </div>
                <span
                  className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${
                    HORIZON_COLORS[opp.planning_horizon as keyof typeof HORIZON_COLORS] ||
                    "bg-gray-100 text-gray-600"
                  }`}
                >
                  {opp.planning_horizon}
                </span>
              </div>
            ))}
            {planning.total > 5 && (
              <div className="py-2 text-xs text-gray-400 text-center">
                +{planning.total - 5} more opportunities
              </div>
            )}
          </div>
        </div>
      )}

      {isSelected && planningLoading && (
        <div className="border-t border-gray-100 px-5 pb-4">
          <div className="text-xs text-gray-400 mt-3">Loading planning data...</div>
        </div>
      )}
    </Card>
  );
}

function ScoreBadgeInline({ score }: { score: number | null }) {
  if (score === null) {
    return (
      <span className="w-7 h-7 rounded-full bg-gray-100 flex items-center justify-center text-[10px] text-gray-400">
        —
      </span>
    );
  }

  const color =
    score >= 80
      ? "bg-green-100 text-green-700"
      : score >= 60
      ? "bg-blue-100 text-blue-700"
      : score >= 40
      ? "bg-amber-100 text-amber-700"
      : "bg-gray-100 text-gray-600";

  return (
    <span
      className={`w-7 h-7 rounded-full flex items-center justify-center text-[10px] font-bold ${color}`}
    >
      {score}
    </span>
  );
}
