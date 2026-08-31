"use client";

import React, { useState } from "react";
import { useApi } from "@/lib/hooks";
import { discovery } from "@/lib/api";
import type { IngestionResult } from "@/lib/types";
import {
  Card,
  CardHeader,
  CardContent,
  EmptyState,
  ErrorState,
  Spinner,
  Button,
  Badge,
  SectionHeader,
} from "@/components/ui";

const SOURCE_INFO: Record<string, { label: string; description: string; icon: string }> = {
  remotive: {
    label: "Remotive",
    description: "Remote-first job board with global remote opportunities",
    icon: "🌍",
  },
  arbeitnow: {
    label: "Arbeitnow",
    description: "Job board with strong coverage of roles in Europe and worldwide",
    icon: "💼",
  },
  himalayas: {
    label: "Himalayas",
    description: "Job board with detailed company profiles and location data",
    icon: "🏔️",
  },
};

export function DiscoverPage() {
  const { data: sourcesData, loading, error, refetch } = useApi(() => discovery.sources(), []);
  const [runningSource, setRunningSource] = useState<string | null>(null);
  const [lastResult, setLastResult] = useState<{
    source: string;
    result: IngestionResult;
  } | null>(null);
  const [runError, setRunError] = useState<string | null>(null);

  if (loading) return <Spinner />;
  if (error) return <ErrorState message={error} onRetry={refetch} />;

  const sources = sourcesData?.sources || [];

  const runSource = async (source: string) => {
    setRunningSource(source);
    setRunError(null);
    setLastResult(null);
    try {
      const result = await discovery.run(source);
      setLastResult({ source, result });
    } catch (err: unknown) {
      setRunError(err instanceof Error ? err.message : "Discovery failed");
    } finally {
      setRunningSource(null);
    }
  };

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Discover</h1>
        <p className="text-sm text-gray-500 mt-1">
          Run discovery from registered sources to find new opportunities
        </p>
      </div>

      {/* Source adapters */}
      <SectionHeader title="Available Sources" count={sources.length} />

      {sources.length === 0 ? (
        <Card>
          <EmptyState
            icon="🔍"
            title="No discovery sources registered"
            description="Source adapters will appear here when registered."
          />
        </Card>
      ) : (
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
          {sources.map((source) => {
            const info = SOURCE_INFO[source] || {
              label: source,
              description: "Discovery source",
              icon: "📡",
            };
            const isRunning = runningSource === source;

            return (
              <Card key={source} className="p-5 flex flex-col">
                <div className="flex items-start gap-3 mb-3">
                  <span className="text-2xl">{info.icon}</span>
                  <div>
                    <h3 className="text-sm font-semibold text-gray-900">
                      {info.label}
                    </h3>
                    <p className="text-xs text-gray-500 mt-0.5">
                      {info.description}
                    </p>
                  </div>
                </div>
                <div className="mt-auto">
                  <Button
                    onClick={() => runSource(source)}
                    loading={isRunning}
                    disabled={runningSource !== null}
                    size="sm"
                    className="w-full"
                  >
                    {isRunning ? "Running..." : "Run Discovery"}
                  </Button>
                </div>
              </Card>
            );
          })}
        </div>
      )}

      {/* Run error */}
      {runError && (
        <Card className="p-4 border-red-200 bg-red-50">
          <div className="flex items-center gap-2">
            <span className="text-red-600 text-sm">⚠️</span>
            <span className="text-sm text-red-700">{runError}</span>
          </div>
        </Card>
      )}

      {/* Last result */}
      {lastResult && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-gray-900">
                Last Result: {SOURCE_INFO[lastResult.source]?.label || lastResult.source}
              </h3>
              <Badge variant={lastResult.result.errors > 0 ? "warning" : "success"}>
                {lastResult.result.errors > 0
                  ? `${lastResult.result.errors} errors`
                  : "Success"}
              </Badge>
            </div>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
              <div>
                <div className="text-gray-500">Received</div>
                <div className="font-semibold text-gray-900">
                  {lastResult.result.total_received}
                </div>
              </div>
              <div>
                <div className="text-gray-500">Normalized</div>
                <div className="font-semibold text-gray-900">
                  {lastResult.result.normalized}
                </div>
              </div>
              <div>
                <div className="text-gray-500">Created</div>
                <div className="font-semibold text-green-700">
                  {lastResult.result.created}
                </div>
              </div>
              <div>
                <div className="text-gray-500">Duplicates Skipped</div>
                <div className="font-semibold text-gray-600">
                  {lastResult.result.duplicates_skipped}
                </div>
              </div>
            </div>
            {lastResult.result.error_details.length > 0 && (
              <div className="mt-3 p-3 bg-gray-50 rounded-lg">
                <div className="text-xs font-medium text-gray-500 mb-1">
                  Error Details
                </div>
                {lastResult.result.error_details.map((err, i) => (
                  <div key={i} className="text-xs text-red-600">
                    {err}
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* How it works */}
      <Card className="p-5">
        <h3 className="text-sm font-semibold text-gray-900 mb-2">
          How Discovery Works
        </h3>
        <div className="text-xs text-gray-500 space-y-1">
          <p>
            <span className="font-medium text-gray-700">Source Adapter</span> → Fetches from public API
          </p>
          <p>
            <span className="font-medium text-gray-700">Normalizer</span> → Standardizes fields (title, company, location)
          </p>
          <p>
            <span className="font-medium text-gray-700">Deduplicator</span> → Skips opportunities already in the system
          </p>
          <p>
            <span className="font-medium text-gray-700">Ingestor</span> → Creates new Opportunities + Evidence records
          </p>
        </div>
      </Card>
    </div>
  );
}
