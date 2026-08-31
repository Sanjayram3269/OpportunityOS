"use client";

import React, { useState } from "react";
import { useApi } from "@/lib/hooks";
import { followups } from "@/lib/api";
import type { FollowUp } from "@/lib/types";
import {
  Card,
  EmptyState,
  ErrorState,
  Spinner,
  Button,
  Badge,
  StatusDot,
} from "@/components/ui";
import {
  STATUS_COLORS,
} from "@/lib/types";

type TabKey = "all" | "PENDING" | "DUE" | "PENDING_APPROVAL" | "APPROVED" | "READY_TO_SEND" | "COMPLETED" | "CANCELLED";

const TABS: { key: TabKey; label: string }[] = [
  { key: "all", label: "All" },
  { key: "PENDING", label: "Scheduled" },
  { key: "DUE", label: "Due" },
  { key: "PENDING_APPROVAL", label: "Pending" },
  { key: "APPROVED", label: "Approved" },
  { key: "READY_TO_SEND", label: "Ready" },
  { key: "COMPLETED", label: "Completed" },
  { key: "CANCELLED", label: "Cancelled" },
];

export function FollowUpsPage() {
  const { data, loading, error, refetch } = useApi(() => followups.list({ limit: 100 }), []);
  const [activeTab, setActiveTab] = useState<TabKey>("all");
  const [actionLoading, setActionLoading] = useState<number | null>(null);

  if (loading) return <Spinner />;
  if (error) return <ErrorState message={error} onRetry={refetch} />;

  const allFollowups = data?.follow_ups || [];
  const filtered =
    activeTab === "all"
      ? allFollowups
      : allFollowups.filter((f) => f.status === activeTab);

  const doAction = async (id: number, action: () => Promise<unknown>) => {
    setActionLoading(id);
    try {
      await action();
      refetch();
    } catch {
      // handled
    } finally {
      setActionLoading(null);
    }
  };

  const now = new Date();

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Follow-ups</h1>
        <p className="text-sm text-gray-500 mt-1">
          Schedule and manage follow-up actions
        </p>
      </div>

      {/* Tab bar */}
      <div className="flex gap-1 overflow-x-auto pb-1">
        {TABS.map((tab) => {
          const count =
            tab.key === "all"
              ? allFollowups.length
              : allFollowups.filter((f) => f.status === tab.key).length;
          return (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`px-3 py-1.5 text-sm font-medium rounded-lg whitespace-nowrap transition-colors ${
                activeTab === tab.key
                  ? "bg-blue-100 text-blue-700"
                  : "text-gray-600 hover:bg-gray-100"
              }`}
            >
              {tab.label}
              {count > 0 && (
                <span className="ml-1.5 text-xs text-gray-400">{count}</span>
              )}
            </button>
          );
        })}
      </div>

      {/* List */}
      {filtered.length === 0 ? (
        <Card>
          <EmptyState
            icon="🔔"
            title="No follow-ups"
            description="Create follow-ups to schedule future outreach actions."
          />
        </Card>
      ) : (
        <Card>
          <div className="divide-y divide-gray-100">
            {filtered.map((fu) => {
              const isOverdue =
                fu.status === "PENDING" &&
                new Date(fu.scheduled_for) < now;
              const statusColor =
                STATUS_COLORS[fu.status] || "bg-gray-100 text-gray-600";

              return (
                <div key={fu.id} className="px-5 py-3">
                  <div className="flex items-center gap-3">
                    <StatusDot status={fu.status} />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-gray-900">
                          {fu.reason || `Follow-up #${fu.id}`}
                        </span>
                        {isOverdue && (
                          <Badge variant="error">Overdue</Badge>
                        )}
                      </div>
                      <div className="text-xs text-gray-500 mt-0.5">
                        Lead #{fu.lead_id}
                        {fu.opportunity_id &&
                          ` · Opportunity #${fu.opportunity_id}`}
                        {" · Due "}
                        {new Date(fu.scheduled_for).toLocaleString()}
                      </div>
                    </div>
                    <Badge className={statusColor}>{fu.status}</Badge>
                  </div>

                  {/* Actions */}
                  <div className="mt-2 flex gap-2 flex-wrap">
                    {fu.status === "PENDING" && (
                      <Button
                        size="sm"
                        onClick={() =>
                          doAction(fu.id, () => followups.markDue(fu.id))
                        }
                        loading={actionLoading === fu.id}
                      >
                        Mark Due
                      </Button>
                    )}
                    {fu.status === "DUE" && (
                      <Button
                        size="sm"
                        onClick={() =>
                          doAction(fu.id, () => followups.submit(fu.id))
                        }
                        loading={actionLoading === fu.id}
                      >
                        Submit
                      </Button>
                    )}
                    {fu.status === "PENDING_APPROVAL" && (
                      <Button
                        size="sm"
                        onClick={() =>
                          doAction(fu.id, () => followups.approve(fu.id))
                        }
                        loading={actionLoading === fu.id}
                      >
                        Approve
                      </Button>
                    )}
                    {fu.status === "APPROVED" && (
                      <Button
                        size="sm"
                        onClick={() =>
                          doAction(fu.id, () => followups.ready(fu.id))
                        }
                        loading={actionLoading === fu.id}
                      >
                        Ready
                      </Button>
                    )}
                    {fu.status === "READY_TO_SEND" && (
                      <Button
                        size="sm"
                        onClick={() =>
                          doAction(fu.id, () => followups.complete(fu.id))
                        }
                        loading={actionLoading === fu.id}
                      >
                        Complete
                      </Button>
                    )}
                    {fu.status !== "COMPLETED" && fu.status !== "CANCELLED" && (
                      <Button
                        size="sm"
                        variant="danger"
                        onClick={() =>
                          doAction(fu.id, () => followups.cancel(fu.id))
                        }
                        loading={actionLoading === fu.id}
                      >
                        Cancel
                      </Button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </Card>
      )}
    </div>
  );
}
