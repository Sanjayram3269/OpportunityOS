"use client";

import React, { useState } from "react";
import { useApi } from "@/lib/hooks";
import { companies as companiesApi } from "@/lib/api";
import type { Company } from "@/lib/types";
import {
  Card,
  EmptyState,
  ErrorState,
  Spinner,
  Badge,
  Button,
  Input,
  SectionHeader,
} from "@/components/ui";

export function CompaniesPage() {
  const { data, loading, error, refetch } = useApi(() => companiesApi.list(), []);
  const [search, setSearch] = useState("");
  const [selectedId, setSelectedId] = useState<number | null>(null);

  if (loading) return <Spinner />;
  if (error) return <ErrorState message={error} onRetry={refetch} />;

  const allCompanies = data || [];
  const filtered = search
    ? allCompanies.filter(
        (c) =>
          c.name.toLowerCase().includes(search.toLowerCase()) ||
          (c.domain || "").toLowerCase().includes(search.toLowerCase()),
      )
    : allCompanies;

  const selected = selectedId !== null ? allCompanies.find((c) => c.id === selectedId) : null;

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Companies</h1>
        <p className="text-sm text-gray-500 mt-1">
          {allCompanies.length} companies
        </p>
      </div>

      <Card className="p-4">
        <Input
          value={search}
          onChange={setSearch}
          placeholder="Search companies..."
          className="w-64"
        />
      </Card>

      {filtered.length === 0 ? (
        <Card>
          <EmptyState
            icon="🏢"
            title="No companies found"
            description={
              search
                ? "Try a different search term."
                : "Companies will appear after discovery or manual creation."
            }
          />
        </Card>
      ) : (
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filtered.map((company) => (
            <Card
              key={company.id}
              className="p-4 cursor-pointer hover:border-blue-300 transition-colors"
              onClick={() =>
                setSelectedId(selectedId === company.id ? null : company.id)
              }
            >
              <div className="flex items-start justify-between mb-2">
                <div className="min-w-0">
                  <h3 className="text-sm font-semibold text-gray-900 truncate">
                    {company.name}
                  </h3>
                  {company.domain && (
                    <div className="text-xs text-gray-500 mt-0.5">
                      {company.domain}
                    </div>
                  )}
                </div>
              </div>
              <div className="flex flex-wrap gap-1.5 text-xs text-gray-500">
                {company.industry && <Badge>{company.industry}</Badge>}
                {company.company_size && <Badge variant="muted">{company.company_size}</Badge>}
                {company.location && <Badge variant="muted">{company.location}</Badge>}
              </div>
              {company.description && (
                <p className="mt-2 text-xs text-gray-500 line-clamp-2">
                  {company.description}
                </p>
              )}
              <div className="mt-3 flex gap-2">
                {company.website && (
                  <a
                    href={company.website}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs text-blue-600 hover:text-blue-800"
                    onClick={(e) => e.stopPropagation()}
                  >
                    Website →
                  </a>
                )}
                {company.linkedin_url && (
                  <a
                    href={company.linkedin_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs text-blue-600 hover:text-blue-800"
                    onClick={(e) => e.stopPropagation()}
                  >
                    LinkedIn →
                  </a>
                )}
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
