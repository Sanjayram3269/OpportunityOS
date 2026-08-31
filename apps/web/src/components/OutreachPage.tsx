"use client";

import React, { useState } from "react";
import { useApi } from "@/lib/hooks";
import { outreach } from "@/lib/api";
import type { DraftResponse } from "@/lib/types";
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
  Select,
} from "@/components/ui";
import { STATUS_COLORS } from "@/lib/types";

type TabKey = "all" | "DRAFT" | "PENDING_APPROVAL" | "APPROVED" | "READY_TO_SEND" | "SENT" | "REJECTED";

const TABS: { key: TabKey; label: string }[] = [
  { key: "all", label: "All" },
  { key: "DRAFT", label: "Drafts" },
  { key: "PENDING_APPROVAL", label: "Pending" },
  { key: "APPROVED", label: "Approved" },
  { key: "READY_TO_SEND", label: "Ready" },
  { key: "SENT", label: "Sent" },
  { key: "REJECTED", label: "Rejected" },
];

export function OutreachPage() {
  const { data, loading, error, refetch } = useApi(() => outreach.list({ limit: 100 }), []);
  const [activeTab, setActiveTab] = useState<TabKey>("all");
  const [selectedDraft, setSelectedDraft] = useState<number | null>(null);
  const [actionLoading, setActionLoading] = useState<number | null>(null);

  if (loading) return <Spinner />;
  if (error) return <ErrorState message={error} onRetry={refetch} />;

  const allDrafts = data?.drafts || [];
  const filtered =
    activeTab === "all"
      ? allDrafts
      : allDrafts.filter((d) => d.status === activeTab);

  const selected = selectedDraft !== null ? allDrafts.find((d) => d.id === selectedDraft) : null;

  const doAction = async (id: number, action: () => Promise<unknown>) => {
    setActionLoading(id);
    try {
      await action();
      refetch();
    } catch {
      // errors handled by refetch
    } finally {
      setActionLoading(null);
    }
  };

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Outreach</h1>
        <p className="text-sm text-gray-500 mt-1">
          Draft, approve, and manage outreach messages
        </p>
      </div>

      {/* Tab bar */}
      <div className="flex gap-1 overflow-x-auto pb-1">
        {TABS.map((tab) => {
          const count =
            tab.key === "all"
              ? allDrafts.length
              : allDrafts.filter((d) => d.status === tab.key).length;
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

      {/* Draft list */}
      {filtered.length === 0 ? (
        <Card>
          <EmptyState
            icon="✉️"
            title="No drafts"
            description="Create outreach drafts from the Opportunity detail page."
          />
        </Card>
      ) : (
        <Card>
          <div className="divide-y divide-gray-100">
            {filtered.map((draft) => (
              <DraftRow
                key={draft.id}
                draft={draft}
                isSelected={selectedDraft === draft.id}
                onSelect={() =>
                  setSelectedDraft(
                    selectedDraft === draft.id ? null : draft.id,
                  )
                }
                isLoading={actionLoading === draft.id}
                onAction={(action) => doAction(draft.id, action)}
              />
            ))}
          </div>
        </Card>
      )}

      {/* Detail panel */}
      {selected && (
        <DraftDetail draft={selected} onClose={() => setSelectedDraft(null)} />
      )}
    </div>
  );
}

function DraftRow({
  draft,
  isSelected,
  onSelect,
  isLoading,
  onAction,
}: {
  draft: DraftResponse;
  isSelected: boolean;
  onSelect: () => void;
  isLoading: boolean;
  onAction: (action: () => Promise<unknown>) => void;
}) {
  const statusColor =
    STATUS_COLORS[draft.status] || "bg-gray-100 text-gray-600";

  return (
    <div
      className={`px-5 py-3 cursor-pointer transition-colors ${
        isSelected ? "bg-blue-50" : "hover:bg-gray-50"
      }`}
      onClick={onSelect}
    >
      <div className="flex items-center gap-3">
        <StatusDot status={draft.status} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-gray-900 truncate">
              {draft.subject || `Draft #${draft.id}`}
            </span>
            {draft.ai_generated && (
              <Badge variant="info">AI</Badge>
            )}
          </div>
          <div className="text-xs text-gray-500 mt-0.5">
            Lead #{draft.lead_id}
            {draft.opportunity_id && ` · Opportunity #${draft.opportunity_id}`}
            {draft.personalization_score !== null && (
              <span className="ml-2">
                Personalization: {draft.personalization_score}%
              </span>
            )}
          </div>
        </div>
        <Badge className={statusColor}>{draft.status}</Badge>
        <span className="text-xs text-gray-400 whitespace-nowrap">
          {new Date(draft.created_at).toLocaleDateString()}
        </span>
      </div>

      {/* Quick actions */}
      {isSelected && (
        <div className="mt-3 flex gap-2 flex-wrap">
          {draft.status === "DRAFT" && (              <Button
                size="sm"
                onClick={() => {
                  onAction(() => outreach.submit(draft.id));
                }}
                loading={isLoading}
              >
                Submit for Approval
              </Button>
          )}
          {draft.status === "PENDING_APPROVAL" && (              <Button
                size="sm"
                onClick={() => {
                  onAction(() => outreach.approve(draft.id));
                }}
                loading={isLoading}
              >
                Approve
              </Button>
          )}
          {draft.status === "APPROVED" && (              <Button
                size="sm"
                onClick={() => {
                  onAction(() => outreach.ready(draft.id));
                }}
                loading={isLoading}
              >
                Mark Ready
              </Button>
          )}
          {draft.status === "READY_TO_SEND" && (              <Button
                size="sm"
                onClick={() => {
                  onAction(() => outreach.send(draft.id));
                }}
                loading={isLoading}
              >
                Send
              </Button>
          )}
          {draft.status !== "SENT" && draft.status !== "REJECTED" && (
            <Button
              size="sm"
              variant="danger"
              onClick={() => {
                onAction(() => outreach.reject(draft.id));
              }}
              loading={isLoading}
            >
              Reject
            </Button>
          )}
        </div>
      )}
    </div>
  );
}

function DraftDetail({
  draft,
  onClose,
}: {
  draft: DraftResponse;
  onClose: () => void;
}) {
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold text-gray-900">
              {draft.subject || `Draft #${draft.id}`}
            </h3>
            <p className="text-xs text-gray-500 mt-0.5">
              Channel: {draft.channel} · Created:{" "}
              {new Date(draft.created_at).toLocaleString()}
            </p>
          </div>
          <Button variant="ghost" size="sm" onClick={onClose}>
            ✕
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        <div className="prose prose-sm max-w-none">
          <div className="whitespace-pre-wrap text-sm text-gray-700 bg-gray-50 rounded-lg p-4">
            {draft.body}
          </div>
        </div>
        {draft.personalization_points.length > 0 && (
          <div className="mt-3">
            <div className="text-xs font-medium text-gray-500 mb-1">
              Personalization Points
            </div>
            <div className="flex flex-wrap gap-1">
              {draft.personalization_points.map((point, i) => (
                <Badge key={i} variant="info">
                  {point}
                </Badge>
              ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
