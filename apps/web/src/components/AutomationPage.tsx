"use client";

import React, { useState, useEffect } from "react";
import { useApi } from "@/lib/hooks";
import { automation } from "@/lib/api";
import type {
  AutomationConfig,
  AutomationRunResult,
  AutomationRunHistoryItem,
} from "@/lib/types";
import {
  Card,
  CardHeader,
  CardContent,
  Badge,
  Button,
  EmptyState,
  ErrorState,
  Spinner,
  KPICard,
  SectionHeader,
} from "@/components/ui";

export default function AutomationPage() {
  const {
    data: config,
    loading: configLoading,
    error: configError,
    refetch: refetchConfig,
  } = useApi(() => automation.status(), []);

  const {
    data: runHistoryData,
    loading: historyLoading,
    error: historyError,
    refetch: refetchHistory,
  } = useApi(() => automation.runs({ limit: 20 }), []);

  const [lastRun, setLastRun] = useState<AutomationRunResult | null>(null);
  const [running, setRunning] = useState(false);
  const [dryRunning, setDryRunning] = useState(false);

  const handleRun = async (dryRun: boolean) => {
    const setBusy = dryRun ? setDryRunning : setRunning;
    setBusy(true);
    try {
      const result = await automation.run({ dry_run: dryRun });
      setLastRun(result);
      refetchConfig();
      refetchHistory();
    } catch (err) {
      console.error("Automation run failed:", err);
    } finally {
      setBusy(false);
    }
  };

  if (configLoading) return <Spinner />;
  if (configError) return <ErrorState message={configError} onRetry={refetchConfig} />;
  if (!config) return <EmptyState title="No configuration" />;

  const runHistory = (runHistoryData as { runs?: AutomationRunHistoryItem[] } | null)?.runs || [];

  return (
    <div className="space-y-6">
      <SectionHeader
        title="Automation Engine"
        action={
          <div className="flex gap-2">
            <Button
              onClick={() => handleRun(false)}
              loading={running}
              disabled={dryRunning}
              size="sm"
            >
              Run Now
            </Button>
            <Button
              onClick={() => handleRun(true)}
              loading={dryRunning}
              disabled={running}
              variant="secondary"
              size="sm"
            >
              Dry Run
            </Button>
          </div>
        }
      />

      {/* Safety notice */}
      <Card className="border-amber-200 bg-amber-50">
        <CardContent className="py-3">
          <p className="text-sm text-amber-800">
            <strong>Safety:</strong> Automation discovers, scores, and plans opportunities — but{" "}
            <strong>outreach sending always requires human approval</strong>.
          </p>
        </CardContent>
      </Card>

      {/* Status KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <KPICard
          label="Status"
          value={config.enabled ? "Enabled" : "Disabled"}
          icon={config.enabled ? "🟢" : "🔴"}
          color={config.enabled ? "green" : "red"}
        />
        <KPICard
          label="Scheduler"
          value={config.scheduler_active ? "Active" : "Inactive"}
          icon={config.scheduler_active ? "⏱️" : "⏸️"}
          color={config.scheduler_active ? "green" : "gray"}
        />
        <KPICard
          label="Interval"
          value={`${config.scheduler_interval_minutes}m`}
          icon="🔄"
          color="blue"
        />
        <KPICard
          label="Min Match Score"
          value={config.min_match_score}
          icon="🎯"
          color="purple"
        />
      </div>

      {/* Configuration */}
      <Card>
        <CardHeader>
          <h3 className="text-sm font-semibold text-gray-900">Pipeline Configuration</h3>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
            <ConfigToggle label="Discovery" enabled={config.discovery_enabled} />
            <ConfigToggle label="Matching" enabled={config.matching_enabled} />
            <ConfigToggle label="AI Insights" enabled={config.ai_insights_enabled} />
            <ConfigToggle label="Outreach Drafts" enabled={config.outreach_drafts_enabled} />
            <ConfigToggle label="Follow-up Processing" enabled={config.followup_processing_enabled} />
            <ConfigToggle label="Dry Run Default" enabled={config.dry_run_default} />
          </div>
          <div className="mt-4">
            <p className="text-xs text-gray-500">
              Sources: {config.sources.join(", ") || "none configured"}
            </p>
            <p className="text-xs text-gray-500 mt-1">
              Max opportunities per run: {config.max_opportunities_per_run}
            </p>
            <p className="text-xs text-gray-500">
              Max drafts per run: {config.max_drafts_per_run}
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Last Run Results */}
      {lastRun && <RunResultCard result={lastRun} />}

      {/* Persistent Run History */}
      <RunHistorySection
        runs={runHistory}
        loading={historyLoading}
        error={historyError}
      />

      {/* Config requires environment variables */}
      <Card>
        <CardHeader>
          <h3 className="text-sm font-semibold text-gray-900">Configuration</h3>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-gray-600">
            Automation settings are configured via environment variables:
          </p>
          <ul className="mt-2 text-xs text-gray-500 space-y-1 font-mono">
            <li>AUTOMATION_ENABLED=true/false</li>
            <li>AUTOMATION_SCHEDULER_INTERVAL_MINUTES=60</li>
            <li>AUTOMATION_DISCOVERY_ENABLED=true/false</li>
            <li>AUTOMATION_MATCHING_ENABLED=true/false</li>
            <li>AUTOMATION_SOURCES=remotive,arbeitnow,himalayas</li>
            <li>AUTOMATION_MIN_MATCH_SCORE=60</li>
            <li>AUTOMATION_DRY_RUN=true/false</li>
          </ul>
        </CardContent>
      </Card>
    </div>
  );
}

// ── Sub-components ────────────────────────────────────────────────────────

function ConfigToggle({ label, enabled }: { label: string; enabled: boolean }) {
  return (
    <div className="flex items-center justify-between py-2 px-3 rounded-lg bg-gray-50">
      <span className="text-sm text-gray-700">{label}</span>
      <Badge variant={enabled ? "success" : "muted"}>
        {enabled ? "ON" : "OFF"}
      </Badge>
    </div>
  );
}

function RunResultCard({ result }: { result: AutomationRunResult }) {
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-gray-900">Latest Run</h3>
          <div className="flex items-center gap-2">
            <Badge variant={result.status === "COMPLETED" ? "success" : result.status === "FAILED" ? "error" : "warning"}>
              {result.status}
            </Badge>
            {result.dry_run && <Badge variant="info">Dry Run</Badge>}
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
          <div>
            <p className="text-xs text-gray-500">Run ID</p>
            <p className="text-sm font-mono text-gray-900">{result.run_id}</p>
          </div>
          <div>
            <p className="text-xs text-gray-500">Trigger</p>
            <p className="text-sm text-gray-900">{result.trigger}</p>
          </div>
          <div>
            <p className="text-xs text-gray-500">Duration</p>
            <p className="text-sm text-gray-900">
              {result.duration_seconds !== null ? `${result.duration_seconds.toFixed(1)}s` : "—"}
            </p>
          </div>
          <div>
            <p className="text-xs text-gray-500">Sources</p>
            <p className="text-sm text-gray-900">
              {result.sources_succeeded}/{result.sources_attempted} succeeded
            </p>
          </div>
        </div>

        {/* Discovery results */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
          <MetricBox label="Seen" value={result.opportunities_seen} />
          <MetricBox label="Created" value={result.opportunities_created} color="green" />
          <MetricBox label="Deduped" value={result.opportunities_deduplicated} color="amber" />
          <MetricBox label="Scored" value={result.opportunities_scored} color="blue" />
        </div>

        {/* Planning + Match */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
          <MetricBox label="High Match" value={result.high_match_count} color="green" />
          <MetricBox label="Summer 2027" value={result.summer_2027_count} color="orange" />
          <MetricBox label="Follow-ups Due" value={result.followups_marked_due} color="amber" />
          <MetricBox label="Drafts Created" value={result.drafts_created} color="blue" />
        </div>

        {/* Source details */}
        {result.source_results.length > 0 && (
          <div className="mt-4">
            <p className="text-xs font-medium text-gray-500 mb-2">Source Results</p>
            <div className="space-y-2">
              {result.source_results.map((sr, i) => (
                <div
                  key={`${sr.source_name}-${i}`}
                  className="flex items-center justify-between py-2 px-3 rounded-lg bg-gray-50 text-sm"
                >
                  <div className="flex items-center gap-2">
                    <Badge variant={sr.success ? "success" : "error"}>
                      {sr.source_name}
                    </Badge>
                    <span className="text-gray-500">
                      {sr.raw_count} raw → {sr.ingested} new
                    </span>
                    {sr.duplicates_skipped > 0 && (
                      <span className="text-amber-600 text-xs">
                        ({sr.duplicates_skipped} deduped)
                      </span>
                    )}
                  </div>
                  {sr.errors.length > 0 && (
                    <span className="text-red-600 text-xs">
                      {sr.errors[0]}
                    </span>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Errors */}
        {result.errors.length > 0 && (
          <div className="mt-4 p-3 rounded-lg bg-red-50 border border-red-200">
            <p className="text-xs font-medium text-red-800 mb-1">Errors</p>
            {result.errors.map((err, i) => (
              <p key={i} className="text-xs text-red-700">{err}</p>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function RunHistorySection({
  runs,
  loading,
  error,
}: {
  runs: AutomationRunHistoryItem[];
  loading: boolean;
  error: string | null;
}) {
  return (
    <Card>
      <CardHeader>
        <h3 className="text-sm font-semibold text-gray-900">Run History</h3>
      </CardHeader>
      <CardContent>
        {loading && <Spinner />}
        {error && <ErrorState message={error} />}
        {!loading && !error && runs.length === 0 && (
          <EmptyState icon="📜" title="No runs yet" description="Run automation to see history here." />
        )}
        {!loading && !error && runs.length > 0 && (
          <div className="space-y-1">
            {runs.map((run) => {
              const statusColors: Record<string, string> = {
                COMPLETED: "bg-green-100 text-green-700",
                FAILED: "bg-red-100 text-red-700",
                RUNNING: "bg-blue-100 text-blue-700",
              };
              const time = run.started_at ? new Date(run.started_at).toLocaleTimeString() : "—";
              const duration = run.duration_seconds != null ? `${run.duration_seconds.toFixed(1)}s` : "—";

              return (
                <div
                  key={run.run_id}
                  className="flex items-center gap-3 py-2 px-3 rounded-lg bg-gray-50 text-sm"
                >
                  <span className="text-gray-500 w-16 shrink-0">{time}</span>
                  <Badge className="bg-gray-100 text-gray-600 text-xs">
                    {run.trigger}
                  </Badge>
                  <Badge className={statusColors[run.status] || "bg-gray-100 text-gray-600"}>
                    {run.status}
                  </Badge>
                  {run.dry_run && <Badge variant="info">Dry</Badge>}
                  <span className="text-gray-500 shrink-0">{duration}</span>
                  <span className="text-gray-400">|</span>
                  <span className="text-green-600">
                    {run.opportunities_created} new
                  </span>
                  <span className="text-blue-600">
                    {run.actions_generated} actions
                  </span>
                  <span className="text-amber-600">
                    {run.notifications_generated} notifs
                  </span>
                  {run.error_summary && (
                    <span className="text-red-600 text-xs truncate max-w-48">
                      {run.error_summary}
                    </span>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function MetricBox({
  label,
  value,
  color = "gray",
}: {
  label: string;
  value: number;
  color?: string;
}) {
  const colors: Record<string, string> = {
    gray: "text-gray-900",
    green: "text-green-700",
    amber: "text-amber-700",
    blue: "text-blue-700",
    orange: "text-orange-700",
  };

  return (
    <div className="text-center py-2 rounded-lg bg-gray-50">
      <p className={`text-lg font-bold ${colors[color] || "text-gray-900"}`}>
        {value}
      </p>
      <p className="text-xs text-gray-500">{label}</p>
    </div>
  );
}
