"use client";

import React, { useState } from "react";
import { exports_ } from "@/lib/api";
import {
  Card,
  CardHeader,
  CardContent,
  Button,
  Select,
  Input,
} from "@/components/ui";
import type { ExportFilterParams } from "@/lib/types";

export function ExportPage() {
  const [filters, setFilters] = useState<ExportFilterParams>({});
  const [downloading, setDownloading] = useState(false);

  const handleExport = async () => {
    setDownloading(true);
    try {
      const url = exports_.downloadUrl(filters);
      const a = document.createElement("a");
      a.href = url;
      a.download = "opportunities.xlsx";
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    } finally {
      setDownloading(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Export</h1>
        <p className="text-sm text-gray-500 mt-1">
          Download your opportunity pipeline as an Excel workbook
        </p>
      </div>

      <Card>
        <CardHeader>
          <h3 className="text-sm font-semibold text-gray-900">
            Excel Export — OpportunityOS Workbook
          </h3>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-gray-600">
            The workbook contains multiple sheets with your full OpportunityOS
            data:
          </p>
          <ul className="text-sm text-gray-600 space-y-1 ml-4">
            <li>• <strong>Opportunities</strong> — all opportunities with match scores and planning data</li>
            <li>• <strong>Companies</strong> — company profiles</li>
            <li>• <strong>Leads</strong> — contact information</li>
            <li>• <strong>Outreach</strong> — email drafts and messages</li>
            <li>• <strong>FollowUps</strong> — scheduled follow-up actions</li>
            <li>• <strong>Campaigns</strong> — organized opportunity groups</li>
            <li>• <strong>Interactions</strong> — delivery and activity records</li>
            <li>• <strong>Evidence</strong> — discovery source data</li>
            <li>• <strong>Summary</strong> — aggregate statistics</li>
          </ul>

          <div className="border-t border-gray-100 pt-4">
            <h4 className="text-sm font-medium text-gray-700 mb-3">
              Optional Filters
            </h4>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <Select
                value={filters.planning_horizon || ""}
                onChange={(v) =>
                  setFilters((f) => ({ ...f, planning_horizon: v || undefined }))
                }
                options={[
                  { label: "Now", value: "NOW" },
                  { label: "Upcoming", value: "UPCOMING" },
                  { label: "Summer 2027", value: "SUMMER_2027" },
                  { label: "Future", value: "FUTURE" },
                  { label: "Unknown", value: "UNKNOWN" },
                ]}
                placeholder="All horizons"
              />
              <Input
                value={filters.min_match_score?.toString() || ""}
                onChange={(v) =>
                  setFilters((f) => ({
                    ...f,
                    min_match_score: v ? parseInt(v, 10) : undefined,
                  }))
                }
                placeholder="Min score"
                type="number"
                label="Min Match Score"
              />
              <Select
                value={filters.opportunity_type || ""}
                onChange={(v) =>
                  setFilters((f) => ({ ...f, opportunity_type: v || undefined }))
                }
                options={[
                  { label: "Internship", value: "INTERNSHIP" },
                  { label: "Full-time", value: "FULL_TIME" },
                  { label: "Research", value: "RESEARCH" },
                  { label: "Startup", value: "STARTUP" },
                  { label: "Hackathon", value: "HACKATHON" },
                  { label: "Freelance", value: "FREELANCE" },
                ]}
                placeholder="All types"
              />
              <Select
                value={filters.status || ""}
                onChange={(v) =>
                  setFilters((f) => ({ ...f, status: v || undefined }))
                }
                options={[
                  { label: "Discovered", value: "DISCOVERED" },
                  { label: "Matched", value: "MATCHED" },
                  { label: "Qualified", value: "QUALIFIED" },
                  { label: "Applied", value: "APPLIED" },
                ]}
                placeholder="All statuses"
              />
            </div>
          </div>

          <div className="flex justify-end pt-2">
            <Button
              onClick={handleExport}
              loading={downloading}
              size="lg"
            >
              📥 Download Excel
            </Button>
          </div>

          <p className="text-xs text-gray-400 text-right">
            PostgreSQL remains the source of truth. Excel is an export surface.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
