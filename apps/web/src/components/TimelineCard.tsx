"use client";

import React from "react";
import { useApi } from "@/lib/hooks";
import { timeline as timelineApi, applications as applicationsApi } from "@/lib/api";
import type { TimelineEvent, TimelineResponse, ApplicationWith } from "@/lib/types";
import {
  Card,
  CardHeader,
  CardContent,
  EmptyState,
  Spinner,
  Badge,
} from "@/components/ui";

// ── Event type → visual config ──────────────────────────────────────────

const EVENT_CONFIG: Record<
  string,
  { icon: string; color: string; bgColor: string }
> = {
  APPLICATION_CREATED: {
    icon: "📋",
    color: "text-gray-600",
    bgColor: "bg-gray-100",
  },
  STATUS_CHANGED: {
    icon: "🔄",
    color: "text-blue-600",
    bgColor: "bg-blue-100",
  },
  APPLICATION_SUBMITTED: {
    icon: "📤",
    color: "text-purple-600",
    bgColor: "bg-purple-100",
  },
  ASSESSMENT: {
    icon: "📝",
    color: "text-amber-600",
    bgColor: "bg-amber-100",
  },
  INTERVIEW: {
    icon: "🎤",
    color: "text-orange-600",
    bgColor: "bg-orange-100",
  },
  FINAL_ROUND: {
    icon: "🏁",
    color: "text-indigo-600",
    bgColor: "bg-indigo-100",
  },
  OFFER: {
    icon: "🎉",
    color: "text-green-600",
    bgColor: "bg-green-100",
  },
  ACCEPTED: {
    icon: "✅",
    color: "text-green-700",
    bgColor: "bg-green-100",
  },
  REJECTED: {
    icon: "❌",
    color: "text-red-600",
    bgColor: "bg-red-100",
  },
  WITHDRAWN: {
    icon: "🔙",
    color: "text-gray-600",
    bgColor: "bg-gray-100",
  },
};

function getEventConfig(eventType: string) {
  return EVENT_CONFIG[eventType] || {
    icon: "📌",
    color: "text-gray-600",
    bgColor: "bg-gray-100",
  };
}

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

function formatTime(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleTimeString("en-US", {
    hour: "2-digit",
    minute: "2-digit",
  });
}

// ── Application Detail with Timeline ────────────────────────────────────

export function ApplicationDetail({
  applicationId,
  onClose,
}: {
  applicationId: number;
  onClose: () => void;
}) {
  const { data: appData, loading: appLoading } = useApi(
    () => applicationsApi.get(applicationId),
    [applicationId],
  );

  const { data: timelineData, loading: timelineLoading } = useApi(
    () => timelineApi.get(applicationId),
    [applicationId],
  );

  if (appLoading) return <Card className="p-4"><Spinner size="sm" /></Card>;
  if (!appData) return null;

  const app = appData as ApplicationWith;
  const timeline = (timelineData as TimelineResponse) || null;

  return (
    <Card className="mt-4">
      <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold text-gray-900">
            {app.opportunity?.title || `Application #${app.id}`}
          </h3>
          <p className="text-sm text-gray-500">
            {app.company?.name || "Company"} · {app.status}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge
            className={
              ["ACCEPTED"].includes(app.status)
                ? "bg-green-100 text-green-700"
                : ["REJECTED", "WITHDRAWN"].includes(app.status)
                ? "bg-red-100 text-red-700"
                : ["INTERVIEW", "FINAL_ROUND", "OFFER"].includes(app.status)
                ? "bg-amber-100 text-amber-800"
                : "bg-blue-100 text-blue-700"
            }
          >
            {app.status}
          </Badge>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 text-lg"
          >
            ✕
          </button>
        </div>
      </div>

      <div className="p-5 space-y-5">
        {/* Context */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
          {app.opportunity && (
            <>
              <div>
                <span className="text-gray-500 text-xs">Match Score</span>
                <div className="font-medium mt-0.5">
                  {app.opportunity.match_score ?? "—"}
                </div>
              </div>
              <div>
                <span className="text-gray-500 text-xs">Type</span>
                <div className="font-medium mt-0.5">{app.opportunity.type}</div>
              </div>
              <div>
                <span className="text-gray-500 text-xs">Deadline</span>
                <div className="font-medium mt-0.5">
                  {app.opportunity.deadline
                    ? new Date(app.opportunity.deadline).toLocaleDateString()
                    : "—"}
                </div>
              </div>
            </>
          )}
          <div>
            <span className="text-gray-500 text-xs">Applied At</span>
            <div className="font-medium mt-0.5">
              {app.applied_at ? formatDate(app.applied_at) : "—"}
            </div>
          </div>
        </div>

        {app.notes && (
          <div>
            <span className="text-sm text-gray-500">Notes</span>
            <p className="mt-1 text-sm text-gray-700 whitespace-pre-wrap">
              {app.notes}
            </p>
          </div>
        )}

        {app.rejection_reason && (
          <div className="p-3 rounded-lg bg-red-50 border border-red-100">
            <span className="text-sm font-medium text-red-700">
              Rejection Reason
            </span>
            <p className="mt-1 text-sm text-red-600">
              {app.rejection_reason}
            </p>
          </div>
        )}

        {/* Timeline */}
        <div>
          <h4 className="text-sm font-semibold text-gray-900 mb-3">
            Application Timeline
          </h4>
          {timelineLoading ? (
            <Spinner size="sm" />
          ) : !timeline || timeline.events.length === 0 ? (
            <div className="py-6 text-center text-sm text-gray-400">
              No timeline events recorded yet.
            </div>
          ) : (
            <TimelineVisual events={timeline.events} />
          )}
        </div>
      </div>
    </Card>
  );
}

// ── Standalone Timeline Card (for list integration) ─────────────────────

export function TimelineCard({ applicationId }: { applicationId: number }) {
  const { data, loading } = useApi(
    () => timelineApi.get(applicationId),
    [applicationId],
  );

  if (loading) return <Spinner size="sm" />;
  const timeline = data as TimelineResponse | null;
  if (!timeline || timeline.events.length === 0) {
    return (
      <EmptyState
        icon="📋"
        title="No timeline events"
        description="Timeline events will appear here as the application progresses."
      />
    );
  }

  return (
    <Card>
      <CardHeader>
        <h3 className="text-sm font-semibold text-gray-900">
          Timeline · {timeline.events.length} event{timeline.events.length !== 1 ? "s" : ""}
        </h3>
      </CardHeader>
      <CardContent>
        <TimelineVisual events={timeline.events} />
      </CardContent>
    </Card>
  );
}

// ── Core Timeline Visual ────────────────────────────────────────────────

function TimelineVisual({ events }: { events: TimelineEvent[] }) {
  // Show oldest first (chronological)
  return (
    <div className="relative">
      {/* Vertical line */}
      <div className="absolute left-4 top-2 bottom-2 w-px bg-gray-200" />

      <div className="space-y-0">
        {events.map((event, idx) => {
          const config = getEventConfig(event.event_type);
          const isLast = idx === events.length - 1;

          return (
            <div key={event.id} className="relative flex gap-4 py-3">
              {/* Icon bubble */}
              <div
                className={`relative z-10 flex items-center justify-center w-8 h-8 rounded-full ${config.bgColor} text-sm shrink-0`}
              >
                {config.icon}
              </div>

              {/* Content */}
              <div className={`flex-1 min-w-0 ${isLast ? "" : "pb-1"}`}>
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <p className={`text-sm font-medium ${config.color}`}>
                      {event.label}
                    </p>
                    {(event.from_status || event.to_status) && (
                      <p className="text-xs text-gray-400 mt-0.5">
                        {event.from_status ? `${event.from_status} → ` : ""}
                        {event.to_status}
                      </p>
                    )}
                  </div>
                  <div className="text-right shrink-0">
                    <div className="text-xs text-gray-500">
                      {formatDate(event.occurred_at)}
                    </div>
                    <div className="text-xs text-gray-400">
                      {formatTime(event.occurred_at)}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
