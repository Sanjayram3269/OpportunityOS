"use client";

import React, { useEffect, useState, useCallback } from "react";
import { actions as actionsApi } from "@/lib/api";
import type { ActionItem, ActionSummary } from "@/lib/types";

const PRIORITY_CONFIG: Record<string, { label: string; color: string; icon: string }> = {
  P0: { label: "P0 — Urgent", color: "bg-red-100 text-red-800 border-red-200", icon: "🔥" },
  P1: { label: "P1 — Important", color: "bg-amber-100 text-amber-800 border-amber-200", icon: "⚡" },
  P2: { label: "P2 — Review", color: "bg-blue-100 text-blue-800 border-blue-200", icon: "🎯" },
  P3: { label: "P3 — Later", color: "bg-gray-100 text-gray-600 border-gray-200", icon: "📋" },
};

const ACTION_TYPE_LABELS: Record<string, string> = {
  REVIEW_OPPORTUNITY: "Review",
  APPLY: "Apply",
  APPROVE_OUTREACH: "Approve",
  SEND_OUTREACH: "Send",
  FOLLOW_UP: "Follow Up",
  INTERVIEW: "Interview",
  ASSESSMENT: "Assessment",
  UPDATE_APPLICATION: "Update",
  REVIEW_DEADLINE: "Deadline",
  RESEARCH_COMPANY: "Research",
};

const ACTION_TYPE_COLORS: Record<string, string> = {
  REVIEW_OPPORTUNITY: "bg-slate-100 text-slate-700",
  APPLY: "bg-indigo-100 text-indigo-700",
  APPROVE_OUTREACH: "bg-amber-100 text-amber-800",
  SEND_OUTREACH: "bg-green-100 text-green-700",
  FOLLOW_UP: "bg-orange-100 text-orange-800",
  INTERVIEW: "bg-purple-100 text-purple-700",
  ASSESSMENT: "bg-pink-100 text-pink-700",
  UPDATE_APPLICATION: "bg-blue-100 text-blue-700",
  REVIEW_DEADLINE: "bg-red-100 text-red-700",
  RESEARCH_COMPANY: "bg-teal-100 text-teal-700",
};

export function ActionCenterPage() {
  const [actionItems, setActionItems] = useState<ActionItem[]>([]);
  const [summary, setSummary] = useState<ActionSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<string>("OPEN");
  const [priorityFilter, setPriorityFilter] = useState<string>("");

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const params: Record<string, string | number> = {};
      if (filter) params.status = filter;
      if (priorityFilter) params.priority = priorityFilter;

      const [actionsList, summaryData] = await Promise.all([
        actionsApi.list(params),
        actionsApi.summary(),
      ]);
      setActionItems(actionsList);
      setSummary(summaryData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load actions");
    } finally {
      setLoading(false);
    }
  }, [filter, priorityFilter]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleGenerate = async () => {
    try {
      setGenerating(true);
      await actionsApi.generate();
      await fetchData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to generate actions");
    } finally {
      setGenerating(false);
    }
  };

  const handleComplete = async (id: number) => {
    try {
      await actionsApi.complete(id);
      await fetchData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to complete action");
    }
  };

  const handleDismiss = async (id: number) => {
    try {
      await actionsApi.dismiss(id);
      await fetchData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to dismiss action");
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-400">Loading action center...</div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Action Center</h1>
          <p className="text-sm text-gray-500 mt-1">
            What should you do next? Automation prepares actions — you decide.
          </p>
        </div>
        <button
          onClick={handleGenerate}
          disabled={generating}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {generating ? "Generating..." : "Generate Actions"}
        </button>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
          {error}
        </div>
      )}

      {/* Summary Cards */}
      {summary && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          <SummaryCard label="Open" value={summary.open} color="bg-blue-50 text-blue-700" />
          <SummaryCard label="In Progress" value={summary.in_progress} color="bg-amber-50 text-amber-700" />
          <SummaryCard label="Completed" value={summary.completed} color="bg-green-50 text-green-700" />
          <SummaryCard label="P0 Urgent" value={summary.by_priority.P0 || 0} color="bg-red-50 text-red-700" />
          <SummaryCard label="P1 Important" value={summary.by_priority.P1 || 0} color="bg-orange-50 text-orange-700" />
        </div>
      )}

      {/* Filters */}
      <div className="flex gap-2 flex-wrap">
        {["OPEN", "IN_PROGRESS", "COMPLETED", "DISMISSED", ""].map((f) => (
          <button
            key={f || "all"}
            onClick={() => setFilter(f)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
              filter === f
                ? "bg-gray-900 text-white"
                : "bg-gray-100 text-gray-600 hover:bg-gray-200"
            }`}
          >
            {f || "All"}
          </button>
        ))}
        <span className="border-l border-gray-200 mx-1" />
        {["P0", "P1", "P2", "P3", ""].map((p) => (
          <button
            key={p || "all-priority"}
            onClick={() => setPriorityFilter(p)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
              priorityFilter === p
                ? "bg-gray-900 text-white"
                : "bg-gray-100 text-gray-600 hover:bg-gray-200"
            }`}
          >
            {p || "Any Priority"}
          </button>
        ))}
      </div>

      {/* Action List */}
      {actionItems.length === 0 ? (
        <div className="text-center py-16">
          <div className="text-gray-300 text-4xl mb-3">✨</div>
          <div className="text-gray-500 font-medium">No actions</div>
          <div className="text-gray-400 text-sm mt-1">
            {filter === "COMPLETED"
              ? "No completed actions yet"
              : "Click Generate Actions to create action items from your opportunities."}
          </div>
        </div>
      ) : (
        <div className="space-y-2">
          {actionItems.map((action) => {
            const pConfig = PRIORITY_CONFIG[action.priority] || PRIORITY_CONFIG.P3;
            const typeColor = ACTION_TYPE_COLORS[action.action_type] || "bg-gray-100 text-gray-600";
            const typeLabel = ACTION_TYPE_LABELS[action.action_type] || action.action_type;

            return (
              <div
                key={action.id}
                className={`flex items-center gap-4 p-4 rounded-lg border ${pConfig.color} transition-opacity ${
                  action.status === "COMPLETED" || action.status === "DISMISSED"
                    ? "opacity-50"
                    : ""
                }`}
              >
                <span className="text-lg flex-shrink-0">{pConfig.icon}</span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span
                      className={`px-2 py-0.5 rounded text-xs font-medium ${typeColor}`}
                    >
                      {typeLabel}
                    </span>
                    <span className="font-medium text-sm text-gray-900 truncate">
                      {action.title}
                    </span>
                  </div>
                  {action.description && (
                    <div className="text-xs text-gray-600 mt-0.5 truncate">
                      {action.description}
                    </div>
                  )}
                  <div className="flex items-center gap-3 mt-1 text-xs text-gray-500">
                    <span>{action.entity_type}: {action.entity_id}</span>
                    {action.due_at && <span>Due: {new Date(action.due_at).toLocaleDateString()}</span>}
                    <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${
                      action.status === "OPEN" ? "bg-white/50 text-gray-700" :
                      action.status === "IN_PROGRESS" ? "bg-blue-50 text-blue-700" :
                      action.status === "COMPLETED" ? "bg-green-50 text-green-700" :
                      "bg-gray-50 text-gray-500"
                    }`}>
                      {action.status}
                    </span>
                  </div>
                </div>
                {action.status === "OPEN" && (
                  <div className="flex gap-1.5 flex-shrink-0">
                    <button
                      onClick={() => handleComplete(action.id)}
                      className="px-3 py-1 bg-green-600 text-white rounded text-xs font-medium hover:bg-green-700"
                    >
                      Done
                    </button>
                    <button
                      onClick={() => handleDismiss(action.id)}
                      className="px-3 py-1 bg-gray-200 text-gray-600 rounded text-xs font-medium hover:bg-gray-300"
                    >
                      Dismiss
                    </button>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Safety notice */}
      <div className="bg-blue-50 border border-blue-100 rounded-lg p-3 text-xs text-blue-700">
        <strong>Safety:</strong> Actions are suggestions. Automation prepares action items but never
        submits applications, sends emails, or approves outreach without your explicit decision.
      </div>
    </div>
  );
}

function SummaryCard({
  label,
  value,
  color,
}: {
  label: string;
  value: number;
  color: string;
}) {
  return (
    <div className={`rounded-lg p-3 ${color}`}>
      <div className="text-2xl font-bold">{value}</div>
      <div className="text-xs font-medium opacity-80">{label}</div>
    </div>
  );
}
