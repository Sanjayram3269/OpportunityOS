"use client";

import React from "react";
import { useApi } from "@/lib/hooks";
import { notifications } from "@/lib/api";
import type { NotificationItem } from "@/lib/types";
import {
  Card,
  CardHeader,
  CardContent,
  EmptyState,
  ErrorState,
  Spinner,
  Badge,
  Button,
  SectionHeader,
} from "@/components/ui";

const SEVERITY_CONFIG: Record<string, { icon: string; color: string; bgColor: string }> = {
  CRITICAL: { icon: "🚨", color: "text-red-700", bgColor: "bg-red-50 border-red-200" },
  HIGH: { icon: "⚠️", color: "text-orange-700", bgColor: "bg-orange-50 border-orange-200" },
  MEDIUM: { icon: "📌", color: "text-blue-700", bgColor: "bg-blue-50 border-blue-200" },
  LOW: { icon: "ℹ️", color: "text-gray-600", bgColor: "bg-gray-50 border-gray-200" },
};

const TYPE_LABELS: Record<string, string> = {
  OVERDUE_ACTION: "Overdue Action",
  FOLLOW_UP_DUE: "Follow-up Due",
  DEADLINE_APPROACHING: "Deadline Approaching",
  OUTREACH_PENDING_APPROVAL: "Pending Approval",
  OUTREACH_READY_TO_SEND: "Ready to Send",
  APPLICATION_UPDATE: "Application Update",
  HIGH_PRIORITY_OPPORTUNITY: "High Priority",
};

const SOURCE_ROUTES: Record<string, string> = {
  action: "/actions",
  followup: "/follow-ups",
  opportunity: "/opportunities",
  message: "/outreach",
  application_event: "/opportunities",
};

function getSourceRoute(sourceType: string): string {
  return SOURCE_ROUTES[sourceType] || "/actions";
}

function formatDate(iso: string): string {
  const d = new Date(iso);
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return "Just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

export function NotificationsPage() {
  const { data: unreadData, loading: unreadLoading, refetch: refetchUnread } = useApi(
    () => notifications.unreadCount(),
    [],
  );

  const { data, loading, error, refetch } = useApi(
    () => notifications.list({ limit: 100 }),
    [],
  );

  const handleSync = async () => {
    await notifications.sync();
    refetch();
    refetchUnread();
  };

  const handleMarkRead = async (id: number) => {
    await notifications.markRead(id);
    refetch();
    refetchUnread();
  };

  const handleMarkAllRead = async () => {
    await notifications.markAllRead();
    refetch();
    refetchUnread();
  };

  if (loading || unreadLoading) return <Spinner />;
  if (error) return <ErrorState message={error} onRetry={refetch} />;

  const allNotifications = (data as NotificationItem[]) || [];
  const unreadCount = (unreadData as { unread_count: number })?.unread_count || 0;
  const unread = allNotifications.filter((n) => !n.read_at);
  const read = allNotifications.filter((n) => n.read_at);

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">
            Attention Center
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            What needs your attention right now
          </p>
        </div>
        <div className="flex items-center gap-2">
          {unreadCount > 0 && (
            <Button variant="secondary" size="sm" onClick={handleMarkAllRead}>
              Mark all read
            </Button>
          )}
          <Button size="sm" onClick={handleSync}>
            🔄 Sync
          </Button>
        </div>
      </div>

      {/* Unread badge summary */}
      {unreadCount > 0 && (
        <Card className="border-blue-200 bg-blue-50">
          <CardContent className="py-3">
            <div className="flex items-center gap-3">
              <span className="text-2xl">🔔</span>
              <div>
                <span className="text-lg font-bold text-blue-700">
                  {unreadCount}
                </span>
                <span className="text-sm text-blue-600 ml-2">
                  unread notification{unreadCount !== 1 ? "s" : ""}
                </span>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Empty state */}
      {allNotifications.length === 0 && (
        <Card>
          <EmptyState
            icon="✅"
            title="All caught up"
            description="No notifications right now. Click Sync to check for new attention items."
          />
        </Card>
      )}

      {/* Unread notifications */}
      {unread.length > 0 && (
        <div>
          <SectionHeader title="Needs Attention" count={unread.length} />
          <div className="space-y-2">
            {unread.map((n) => (
              <NotificationCard
                key={n.id}
                notification={n}
                onMarkRead={handleMarkRead}
              />
            ))}
          </div>
        </div>
      )}

      {/* Read notifications */}
      {read.length > 0 && (
        <div>
          <SectionHeader title="Previously Read" count={read.length} />
          <div className="space-y-2">
            {read.map((n) => (
              <NotificationCard
                key={n.id}
                notification={n}
                onMarkRead={handleMarkRead}
                read
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function NotificationCard({
  notification,
  onMarkRead,
  read = false,
}: {
  notification: NotificationItem;
  onMarkRead: (id: number) => void;
  read?: boolean;
}) {
  const config = SEVERITY_CONFIG[notification.severity] || SEVERITY_CONFIG.MEDIUM;
  const typeLabel = TYPE_LABELS[notification.notification_type] || notification.notification_type;
  const route = getSourceRoute(notification.source_type);

  return (
    <Card className={`${read ? "opacity-70" : config.bgColor} transition-opacity`}>
      <div className="p-4 flex items-start gap-3">
        <span className="text-xl shrink-0">{config.icon}</span>
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <h3 className={`text-sm font-semibold ${config.color}`}>
                {notification.title}
              </h3>
              {notification.message && (
                <p className="text-xs text-gray-500 mt-0.5 line-clamp-2">
                  {notification.message}
                </p>
              )}
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <Badge className="bg-gray-100 text-gray-600">
                {typeLabel}
              </Badge>
              <span className="text-xs text-gray-400 whitespace-nowrap">
                {formatDate(notification.created_at)}
              </span>
            </div>
          </div>
          <div className="flex items-center gap-3 mt-2">
            <a
              href={route}
              className="text-xs text-blue-600 hover:text-blue-800 underline"
            >
              View details →
            </a>
            {!read && (
              <button
                onClick={() => onMarkRead(notification.id)}
                className="text-xs text-gray-400 hover:text-gray-600"
              >
                Mark read
              </button>
            )}
          </div>
        </div>
      </div>
    </Card>
  );
}
