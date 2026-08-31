"use client";

import React, { useState } from "react";
import { useApi } from "@/lib/hooks";
import { discovery } from "@/lib/api";
import type {
  IngestionResult,
  SourceMetadataInfo,
  EnrichedDiscoveryResponse,
} from "@/lib/types";
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

const SOURCE_ICONS: Record<string, string> = {
  remotive: "🌍",
  arbeitnow: "💼",
  himalayas: "🏔️",
  linkedin: "🔗",
  handshake: "🎓",
  jobstep: "🤖",
};

export function DiscoverPage() {
  const {
    data: metadataData,
    loading: metaLoading,
    error: metaError,
    refetch: refetchMeta,
  } = useApi(() => discovery.sourcesMetadata(), []);

  const {
    data: healthData,
    loading: healthLoading,
  } = useApi(() => discovery.health(), []);

  const [runningSource, setRunningSource] = useState<string | null>(null);
  const [lastResult, setLastResult] = useState<{
    source: string;
    result: IngestionResult;
  } | null>(null);
  const [previewSource, setPreviewSource] = useState<string | null>(null);
  const [previewData, setPreviewData] =
    useState<EnrichedDiscoveryResponse | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);

  if (metaLoading) return <Spinner />;
  if (metaError) return <ErrorState message={metaError} onRetry={refetchMeta} />;

  const sources: SourceMetadataInfo[] = metadataData?.sources || [];
  const health = healthData?.status || "unknown";

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

  const previewSourceAction = async (source: string) => {
    setPreviewLoading(true);
    setPreviewSource(source);
    setPreviewData(null);
    try {
      const data = await discovery.preview(source);
      setPreviewData(data);
    } catch (err: unknown) {
      setRunError(err instanceof Error ? err.message : "Preview failed");
    } finally {
      setPreviewLoading(false);
    }
  };

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">
          Discovery Intelligence
        </h1>
        <p className="text-sm text-gray-500 mt-1">
          Multi-source opportunity discovery with intelligent classification
        </p>
      </div>

      {/* Health bar */}
      {healthData && (
        <Card className="p-4">
          <div className="flex items-center gap-4 flex-wrap">
            <div className="flex items-center gap-2">
              <div
                className={`w-2.5 h-2.5 rounded-full ${
                  health === "healthy"
                    ? "bg-green-500"
                    : health === "degraded"
                      ? "bg-amber-500"
                      : "bg-red-500"
                }`}
              />
              <span className="text-sm font-medium text-gray-700">
                System {health.charAt(0).toUpperCase() + health.slice(1)}
              </span>
            </div>
            <div className="flex gap-4 text-xs text-gray-500">
              <span>
                <span className="font-semibold text-gray-700">
                  {metadataData?.active_count || 0}
                </span>{" "}
                active sources
              </span>
              <span>
                <span className="font-semibold text-gray-700">
                  {metadataData?.total_count || 0}
                </span>{" "}
                total registered
              </span>
              <span>
                <span className="font-semibold text-gray-700">
                  {metadataData?.auth_required_count || 0}
                </span>{" "}
                require auth
              </span>
            </div>
          </div>
        </Card>
      )}

      {/* Active Sources */}
      <SectionHeader
        title="Active Sources"
        count={sources.filter((s) => s.adapter_available && !s.requires_auth).length}
      />

      <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
        {sources
          .filter((s) => s.adapter_available && !s.requires_auth)
          .map((source) => {
            const icon = SOURCE_ICONS[source.name] || "📡";
            const isRunning = runningSource === source.name;

            return (
              <Card key={source.name} className="p-5 flex flex-col">
                <div className="flex items-start gap-3 mb-3">
                  <span className="text-2xl">{icon}</span>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <h3 className="text-sm font-semibold text-gray-900">
                        {source.display_name}
                      </h3>
                      <Badge variant="success">Active</Badge>
                    </div>
                    <p className="text-xs text-gray-500 mt-0.5 line-clamp-2">
                      {source.description}
                    </p>
                  </div>
                </div>

                {/* Capabilities */}
                <div className="flex flex-wrap gap-1.5 mb-3">
                  {source.supports_remote && (
                    <Badge variant="info">Remote</Badge>
                  )}
                  {source.geographic_coverage.slice(0, 2).map((c) => (
                    <Badge key={c} variant="default">{c}</Badge>
                  ))}
                  {source.supports_deadline && (
                    <Badge variant="info">Deadlines</Badge>
                  )}
                  {source.supports_salary && (
                    <Badge variant="info">Salary</Badge>
                  )}
                </div>

                {/* Supported types */}
                {source.supported_types.length > 0 && (
                  <div className="text-[11px] text-gray-400 mb-3">
                    {source.supported_types.slice(0, 4).join(" · ")}
                    {source.supported_types.length > 4 &&
                      ` +${source.supported_types.length - 4} more`}
                  </div>
                )}

                {/* Rate limit */}
                {source.rate_limit_note && (
                  <div className="text-[10px] text-gray-400 mb-3 italic">
                    {source.rate_limit_note}
                  </div>
                )}

                {/* Actions */}
                <div className="mt-auto flex gap-2">
                  <Button
                    onClick={() => runSource(source.name)}
                    loading={isRunning}
                    disabled={runningSource !== null}
                    size="sm"
                    className="flex-1"
                  >
                    {isRunning ? "Running..." : "Run & Ingest"}
                  </Button>
                  <Button
                    onClick={() => previewSourceAction(source.name)}
                    disabled={previewLoading || runningSource !== null}
                    size="sm"
                    variant="secondary"
                    className="flex-1"
                  >
                    Preview
                  </Button>
                </div>
              </Card>
            );
          })}
      </div>

      {/* Auth-required sources (stubs) */}
      {sources.some((s) => s.requires_auth) && (
        <>
          <SectionHeader
            title="Planned Sources"
            count={sources.filter((s) => s.requires_auth).length}
          />
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
            {sources
              .filter((s) => s.requires_auth)
              .map((source) => {
                const icon = SOURCE_ICONS[source.name] || "🔗";
                return (
                  <Card
                    key={source.name}
                    className="p-5 flex flex-col opacity-70"
                  >
                    <div className="flex items-start gap-3 mb-3">
                      <span className="text-2xl">{icon}</span>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <h3 className="text-sm font-semibold text-gray-900">
                            {source.display_name}
                          </h3>
                          <Badge variant="default">Requires Auth</Badge>
                        </div>
                        <p className="text-xs text-gray-500 mt-0.5 line-clamp-2">
                          {source.description}
                        </p>
                      </div>
                    </div>

                    <div className="flex flex-wrap gap-1.5 mb-3">
                      {source.geographic_coverage.slice(0, 2).map((c) => (
                        <Badge key={c} variant="default">{c}</Badge>
                      ))}
                    </div>

                    <div className="mt-auto">
                      <div className="text-[10px] text-gray-400 italic">
                        Authorized integration required
                      </div>
                    </div>
                  </Card>
                );
              })}
          </div>
        </>
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

      {/* Last ingest result */}
      {lastResult && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-gray-900">
                Ingest Result:{" "}
                {sources.find((s) => s.name === lastResult.source)
                  ?.display_name || lastResult.source}
              </h3>
              <Badge
                variant={
                  lastResult.result.errors.length > 0 ? "warning" : "success"
                }
              >
                {lastResult.result.errors.length > 0
                  ? `${lastResult.result.errors.length} errors`
                  : "Success"}
              </Badge>
            </div>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
              <div>
                <div className="text-gray-500">Fetched</div>
                <div className="font-semibold text-gray-900">
                  {lastResult.result.raw_count}
                </div>
              </div>
              <div>
                <div className="text-gray-500">Ingested</div>
                <div className="font-semibold text-green-700">
                  {lastResult.result.ingested}
                </div>
              </div>
              <div>
                <div className="text-gray-500">Duplicates</div>
                <div className="font-semibold text-gray-600">
                  {lastResult.result.duplicates_skipped}
                </div>
              </div>
              <div>
                <div className="text-gray-500">New Companies</div>
                <div className="font-semibold text-blue-700">
                  {lastResult.result.companies_created}
                </div>
              </div>
            </div>
            {lastResult.result.errors.length > 0 && (
              <div className="mt-3 p-3 bg-gray-50 rounded-lg">
                <div className="text-xs font-medium text-gray-500 mb-1">
                  Errors
                </div>
                {lastResult.result.errors.map((err, i) => (
                  <div key={i} className="text-xs text-red-600">
                    {err}
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Preview result */}
      {previewSource && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-gray-900">
                Preview:{" "}
                {sources.find((s) => s.name === previewSource)?.display_name ||
                  previewSource}
              </h3>
              {previewLoading ? (
                <span className="text-xs text-gray-500">Loading...</span>
              ) : previewData ? (
                <div className="flex gap-2">
                  <Badge variant="info">
                    {previewData.enriched_count} opportunities
                  </Badge>
                  {previewData.remote_count > 0 && (
                    <Badge variant="success">
                      {previewData.remote_count} remote
                    </Badge>
                  )}
                </div>
              ) : null}
            </div>
          </CardHeader>
          <CardContent>
            {previewLoading ? (
              <Spinner />
            ) : previewData?.errors && previewData.errors.length > 0 ? (
              <div className="text-sm text-red-600">
                {previewData.errors.join("; ")}
              </div>
            ) : previewData ? (
              <div className="space-y-4">
                {/* Stats */}
                <div className="grid grid-cols-2 md:grid-cols-5 gap-3 text-sm">
                  <div className="p-2 bg-gray-50 rounded">
                    <div className="text-gray-500 text-xs">Total</div>
                    <div className="font-semibold">{previewData.raw_count}</div>
                  </div>
                  <div className="p-2 bg-gray-50 rounded">
                    <div className="text-gray-500 text-xs">Remote</div>
                    <div className="font-semibold text-green-700">
                      {previewData.remote_count}
                    </div>
                  </div>
                  <div className="p-2 bg-gray-50 rounded">
                    <div className="text-gray-500 text-xs">Countries</div>
                    <div className="font-semibold">
                      {previewData.countries.length}
                    </div>
                  </div>
                  <div className="p-2 bg-gray-50 rounded">
                    <div className="text-gray-500 text-xs">Categories</div>
                    <div className="font-semibold">
                      {previewData.categories.length}
                    </div>
                  </div>
                  <div className="p-2 bg-gray-50 rounded">
                    <div className="text-gray-500 text-xs">Skills Found</div>
                    <div className="font-semibold">
                      {previewData.all_skills.length}
                    </div>
                  </div>
                </div>

                {/* Top skills */}
                {previewData.all_skills.length > 0 && (
                  <div>
                    <div className="text-xs font-medium text-gray-500 mb-1">
                      Top Skills
                    </div>
                    <div className="flex flex-wrap gap-1">
                      {previewData.all_skills.slice(0, 15).map((skill) => (
                        <Badge key={skill} variant="default">
                          {skill}
                        </Badge>
                      ))}
                    </div>
                  </div>
                )}

                {/* Sample opportunities */}
                {previewData.opportunities.length > 0 && (
                  <div>
                    <div className="text-xs font-medium text-gray-500 mb-2">
                      Sample Opportunities (first 5)
                    </div>
                    <div className="space-y-2">
                      {previewData.opportunities.slice(0, 5).map((opp, i) => (
                        <div
                          key={i}
                          className="p-3 bg-gray-50 rounded-lg text-sm"
                        >
                          <div className="flex items-start justify-between gap-2">
                            <div>
                              <div className="font-medium text-gray-900">
                                {opp.normalized_title}
                              </div>
                              <div className="text-xs text-gray-500">
                                {opp.normalized_company_name}
                              </div>
                            </div>
                            <div className="flex gap-1 shrink-0">
                              <Badge variant="default">
                                {opp.opportunity_type}
                              </Badge>
                              {opp.is_remote && (
                                <Badge variant="success">Remote</Badge>
                              )}
                            </div>
                          </div>
                          {opp.city && (
                            <div className="text-xs text-gray-400 mt-1">
                              📍 {opp.city}
                              {opp.country ? `, ${opp.country}` : ""}
                            </div>
                          )}
                          {opp.extracted_skills.length > 0 && (
                            <div className="flex flex-wrap gap-1 mt-1.5">
                              {opp.extracted_skills.slice(0, 5).map((s) => (
                                <span
                                  key={s}
                                  className="text-[10px] px-1.5 py-0.5 bg-blue-50 text-blue-600 rounded"
                                >
                                  {s}
                                </span>
                              ))}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ) : null}
          </CardContent>
        </Card>
      )}

      {/* Pipeline info */}
      <Card className="p-5">
        <h3 className="text-sm font-semibold text-gray-900 mb-2">
          Discovery Pipeline
        </h3>
        <div className="text-xs text-gray-500 space-y-1">
          <p>
            <span className="font-medium text-gray-700">Source Adapter</span>{" "}
            → Fetches from public API (Remotive, Arbeitnow, Himalayas)
          </p>
          <p>
            <span className="font-medium text-gray-700">Normalizer</span>{" "}
            → Standardizes title, company, location, type
          </p>
          <p>
            <span className="font-medium text-gray-700">Location Intelligence</span>{" "}
            → Normalizes city/country, detects remote/worldwide/hybrid
          </p>
          <p>
            <span className="font-medium text-gray-700">Enrichment</span>{" "}
            → Extracts skills, classifies type, infers category
          </p>
          <p>
            <span className="font-medium text-gray-700">Deduplicator</span>{" "}
            → Skips opportunities already in the system
          </p>
          <p>
            <span className="font-medium text-gray-700">Company Resolver</span>{" "}
            → Matches or creates companies
          </p>
          <p>
            <span className="font-medium text-gray-700">Ingestor</span>{" "}
            → Creates Opportunities + Evidence records
          </p>
        </div>
      </Card>
    </div>
  );
}
