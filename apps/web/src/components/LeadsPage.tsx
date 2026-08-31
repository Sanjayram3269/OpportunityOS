"use client";

import React, { useState } from "react";
import { useApi } from "@/lib/hooks";
import { leads as leadsApi } from "@/lib/api";
import type { Lead } from "@/lib/types";
import {
  Card,
  EmptyState,
  ErrorState,
  Spinner,
  Badge,
  Input,
  StatusDot,
} from "@/components/ui";
import { STATUS_COLORS } from "@/lib/types";

export function LeadsPage() {
  const { data, loading, error, refetch } = useApi(() => leadsApi.list(), []);
  const [search, setSearch] = useState("");

  if (loading) return <Spinner />;
  if (error) return <ErrorState message={error} onRetry={refetch} />;

  const allLeads = data || [];
  const filtered = search
    ? allLeads.filter(
        (l) =>
          l.name.toLowerCase().includes(search.toLowerCase()) ||
          (l.email || "").toLowerCase().includes(search.toLowerCase()),
      )
    : allLeads;

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Leads</h1>
        <p className="text-sm text-gray-500 mt-1">
          {allLeads.length} contacts
        </p>
      </div>

      <Card className="p-4">
        <Input
          value={search}
          onChange={setSearch}
          placeholder="Search leads..."
          className="w-64"
        />
      </Card>

      {filtered.length === 0 ? (
        <Card>
          <EmptyState
            icon="👤"
            title="No leads yet"
            description={
              search
                ? "Try a different search."
                : "Leads will appear after discovery or manual creation."
            }
          />
        </Card>
      ) : (
        <Card>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  <th className="px-4 py-3">Name</th>
                  <th className="px-4 py-3">Title</th>
                  <th className="px-4 py-3">Email</th>
                  <th className="px-4 py-3">Location</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Source</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {filtered.map((lead) => (
                  <tr key={lead.id} className="table-row-hover">
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <StatusDot status={lead.status} />
                        <span className="font-medium text-gray-900">
                          {lead.name}
                        </span>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-gray-600">
                      {lead.title || "—"}
                    </td>
                    <td className="px-4 py-3">
                      {lead.email ? (
                        <a
                          href={`mailto:${lead.email}`}
                          className="text-blue-600 hover:text-blue-800"
                        >
                          {lead.email}
                        </a>
                      ) : (
                        <span className="text-gray-400">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-gray-600">
                      {lead.location || "—"}
                    </td>
                    <td className="px-4 py-3">
                      <Badge
                        className={
                          STATUS_COLORS[lead.status] || "bg-gray-100 text-gray-600"
                        }
                      >
                        {lead.status}
                      </Badge>
                    </td>
                    <td className="px-4 py-3 text-gray-500">
                      {lead.source || "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}
