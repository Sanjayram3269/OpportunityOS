"use client";

import React, { useState } from "react";
import { useApi } from "@/lib/hooks";
import { campaigns } from "@/lib/api";
import type { Campaign, CampaignSummary } from "@/lib/types";
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
import { STATUS_COLORS } from "@/lib/types";

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
          Organize opportunities into targeted campaigns
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
        <div className="grid md:grid-cols-2 gap-4">
          {allCampaigns.map((campaign) => (
            <Card
              key={campaign.id}
              className={`p-5 cursor-pointer transition-colors ${
                selectedId === campaign.id
                  ? "border-blue-300"
                  : "hover:border-gray-300"
              }`}
              onClick={() =>
                setSelectedId(
                  selectedId === campaign.id ? null : campaign.id,
                )
              }
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

              {/* Lifecycle actions */}
              {selectedId === campaign.id && (
                <div className="mt-3 flex gap-2 flex-wrap border-t border-gray-100 pt-3">
                  {campaign.status === "DRAFT" && (
                    <Button
                      size="sm"
                      onClick={() => {
                        doAction(`activate-${campaign.id}`, () =>
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
                        onClick={() => {
                          doAction(`pause-${campaign.id}`, () =>
                            campaigns.pause(campaign.id),
                          );
                        }}
                        loading={actionLoading === `pause-${campaign.id}`}
                      >
                        Pause
                      </Button>
                      <Button
                        size="sm"
                        onClick={() => {
                          doAction(`complete-${campaign.id}`, () =>
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
                        onClick={() => {
                          doAction(`activate-${campaign.id}`, () =>
                            campaigns.activate(campaign.id),
                          );
                        }}
                        loading={actionLoading === `activate-${campaign.id}`}
                      >
                        Resume
                      </Button>
                      <Button
                        size="sm"
                        onClick={() => {
                          doAction(`complete-${campaign.id}`, () =>
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
                      onClick={() => {
                        doAction(`archive-${campaign.id}`, () =>
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
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
