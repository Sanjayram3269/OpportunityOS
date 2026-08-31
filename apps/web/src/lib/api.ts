// Centralized API client for OpportunityOS backend.
// All fetch calls go through here for consistent error handling.

const BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const url = `${BASE_URL}${path}`;
  const res = await fetch(url, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });

  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch {
      // ignore
    }
    throw new ApiError(res.status, detail);
  }

  if (res.status === 204) {
    return undefined as T;
  }

  return res.json() as Promise<T>;
}

function qs(params: Record<string, string | number | boolean | null | undefined>): string {
  const entries = Object.entries(params).filter(
    ([, v]) => v !== null && v !== undefined && v !== "",
  );
  if (entries.length === 0) return "";
  return "?" + entries.map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`).join("&");
}

// ── Profiles ─────────────────────────────────────────────────────────────

export const profiles = {
  list: () => request<import("./types").Profile[]>("/api/profiles"),
  get: (id: number) => request<import("./types").Profile>(`/api/profiles/${id}`),
  create: (data: Record<string, unknown>) =>
    request<import("./types").Profile>("/api/profiles", { method: "POST", body: JSON.stringify(data) }),
  update: (id: number, data: Record<string, unknown>) =>
    request<import("./types").Profile>(`/api/profiles/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  delete: (id: number) =>
    request<void>(`/api/profiles/${id}`, { method: "DELETE" }),
};

// ── Companies ────────────────────────────────────────────────────────────

export const companies = {
  list: () => request<import("./types").Company[]>("/api/companies"),
  get: (id: number) => request<import("./types").Company>(`/api/companies/${id}`),
  create: (data: Record<string, unknown>) =>
    request<import("./types").Company>("/api/companies", { method: "POST", body: JSON.stringify(data) }),
  update: (id: number, data: Record<string, unknown>) =>
    request<import("./types").Company>(`/api/companies/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  delete: (id: number) =>
    request<void>(`/api/companies/${id}`, { method: "DELETE" }),
  getLeads: (id: number) =>
    request<import("./types").Lead[]>(`/api/companies/${id}/leads`),
  getOpportunities: (id: number) =>
    request<import("./types").Opportunity[]>(`/api/companies/${id}/opportunities`),
};

// ── Leads ────────────────────────────────────────────────────────────────

export const leads = {
  list: () => request<import("./types").Lead[]>("/api/leads"),
  get: (id: number) => request<import("./types").Lead>(`/api/leads/${id}`),
  create: (data: Record<string, unknown>) =>
    request<import("./types").Lead>("/api/leads", { method: "POST", body: JSON.stringify(data) }),
  update: (id: number, data: Record<string, unknown>) =>
    request<import("./types").Lead>(`/api/leads/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  delete: (id: number) =>
    request<void>(`/api/leads/${id}`, { method: "DELETE" }),
  getOpportunities: (id: number) =>
    request<import("./types").Opportunity[]>(`/api/leads/${id}/opportunities`),
};

// ── Opportunities ────────────────────────────────────────────────────────

export const opportunities = {
  list: () => request<import("./types").Opportunity[]>("/api/opportunities"),
  get: (id: number) => request<import("./types").Opportunity>(`/api/opportunities/${id}`),
  create: (data: Record<string, unknown>) =>
    request<import("./types").Opportunity>("/api/opportunities", { method: "POST", body: JSON.stringify(data) }),
  update: (id: number, data: Record<string, unknown>) =>
    request<import("./types").Opportunity>(`/api/opportunities/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  delete: (id: number) =>
    request<void>(`/api/opportunities/${id}`, { method: "DELETE" }),
};

// ── Planning ─────────────────────────────────────────────────────────────

export const planning = {
  list: (params?: {
    horizon?: string;
    min_match_score?: number;
    type?: string;
    status?: string;
    priority?: string;
    limit?: number;
  }) =>
    request<import("./types").PlanningListResponse>(
      `/api/opportunities/planning${qs(params || {})}`,
    ),
};

// ── Matching ─────────────────────────────────────────────────────────────

export const matching = {
  match: (profileId: number, opportunityId: number) =>
    request<import("./types").MatchResult>(
      `/api/matching/profiles/${profileId}/opportunities/${opportunityId}`,
    ),
  ranked: (profileId: number, limit?: number) =>
    request<import("./types").RankedOpportunitiesResponse>(
      `/api/matching/profiles/${profileId}/ranked${qs({ limit: limit || 20 })}`,
    ),
};

// ── AI Insight ───────────────────────────────────────────────────────────

export const aiInsight = {
  get: (profileId: number, opportunityId: number) =>
    request<import("./types").OpportunityMatchInsightResponse>(
      `/api/matching/profiles/${profileId}/opportunities/${opportunityId}/insight`,
    ),
};

// ── Discovery ────────────────────────────────────────────────────────────

export const discovery = {
  sources: () =>
    request<import("./types").SourceListResponse>("/api/discovery/sources"),
  run: (source: string) =>
    request<import("./types").IngestionResult>(`/api/discovery/run/${source}`, {
      method: "POST",
    }),
  ingestRaw: (items: unknown[]) =>
    request<import("./types").IngestionResult>("/api/discovery/run", {
      method: "POST",
      body: JSON.stringify(items),
    }),
};

// ── Outreach / Drafts ────────────────────────────────────────────────────

export const outreach = {
  list: (params?: {
    lead_id?: number;
    opportunity_id?: number;
    status?: string;
    channel?: string;
    limit?: number;
  }) =>
    request<import("./types").DraftListResponse>(
      `/api/outreach/drafts${qs(params || {})}`,
    ),
  get: (id: number) =>
    request<import("./types").DraftResponse>(`/api/outreach/drafts/${id}`),
  create: (data: { profile_id: number; lead_id: number; opportunity_id: number; channel?: string }) =>
    request<import("./types").DraftResponse>("/api/outreach/drafts", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  update: (id: number, data: { subject?: string; body?: string }) =>
    request<import("./types").DraftResponse>(`/api/outreach/drafts/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),
  submit: (id: number) =>
    request<import("./types").DraftStateTransitionResponse>(
      `/api/outreach/drafts/${id}/submit`,
      { method: "POST" },
    ),
  approve: (id: number) =>
    request<import("./types").DraftStateTransitionResponse>(
      `/api/outreach/drafts/${id}/approve`,
      { method: "POST" },
    ),
  ready: (id: number) =>
    request<import("./types").DraftStateTransitionResponse>(
      `/api/outreach/drafts/${id}/ready`,
      { method: "POST" },
    ),
  send: (id: number) =>
    request<import("./types").SendDraftResponse>(
      `/api/outreach/drafts/${id}/send`,
      { method: "POST" },
    ),
  reject: (id: number) =>
    request<import("./types").DraftStateTransitionResponse>(
      `/api/outreach/drafts/${id}/reject`,
      { method: "POST" },
    ),
};

// ── Follow-ups ───────────────────────────────────────────────────────────

export const followups = {
  list: (params?: {
    lead_id?: number;
    opportunity_id?: number;
    status?: string;
    limit?: number;
  }) =>
    request<import("./types").FollowUpListResponse>(
      `/api/follow-ups${qs(params || {})}`,
    ),
  get: (id: number) =>
    request<import("./types").FollowUp>(`/api/follow-ups/${id}`),
  create: (data: {
    lead_id: number;
    opportunity_id?: number;
    message_id?: number;
    scheduled_for: string;
    reason?: string;
  }) =>
    request<import("./types").FollowUp>("/api/follow-ups", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  update: (id: number, data: { scheduled_for?: string; reason?: string }) =>
    request<import("./types").FollowUp>(`/api/follow-ups/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),
  markDue: (id: number) =>
    request<import("./types").FollowUpStateTransitionResponse>(
      `/api/follow-ups/${id}/mark-due`,
      { method: "POST" },
    ),
  submit: (id: number) =>
    request<import("./types").FollowUpStateTransitionResponse>(
      `/api/follow-ups/${id}/submit`,
      { method: "POST" },
    ),
  approve: (id: number) =>
    request<import("./types").FollowUpStateTransitionResponse>(
      `/api/follow-ups/${id}/approve`,
      { method: "POST" },
    ),
  ready: (id: number) =>
    request<import("./types").FollowUpStateTransitionResponse>(
      `/api/follow-ups/${id}/ready`,
      { method: "POST" },
    ),
  complete: (id: number) =>
    request<import("./types").FollowUpStateTransitionResponse>(
      `/api/follow-ups/${id}/complete`,
      { method: "POST" },
    ),
  cancel: (id: number) =>
    request<import("./types").FollowUpStateTransitionResponse>(
      `/api/follow-ups/${id}/cancel`,
      { method: "POST" },
    ),
};

// ── Campaigns ────────────────────────────────────────────────────────────

export const campaigns = {
  list: (params?: { status?: string; type?: string; limit?: number }) =>
    request<import("./types").CampaignListResponse>(
      `/api/campaigns${qs(params || {})}`,
    ),
  get: (id: number) =>
    request<import("./types").Campaign>(`/api/campaigns/${id}`),
  create: (data: { name: string; type: string; description?: string }) =>
    request<import("./types").Campaign>("/api/campaigns", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  update: (id: number, data: Record<string, unknown>) =>
    request<import("./types").Campaign>(`/api/campaigns/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),
  activate: (id: number) =>
    request<import("./types").Campaign>(`/api/campaigns/${id}/activate`, { method: "POST" }),
  pause: (id: number) =>
    request<import("./types").Campaign>(`/api/campaigns/${id}/pause`, { method: "POST" }),
  complete: (id: number) =>
    request<import("./types").Campaign>(`/api/campaigns/${id}/complete`, { method: "POST" }),
  archive: (id: number) =>
    request<import("./types").Campaign>(`/api/campaigns/${id}/archive`, { method: "POST" }),
  addOpportunity: (campaignId: number, opportunityId: number) =>
    request<{ campaign_id: number; opportunity_id: number; message: string }>(
      `/api/campaigns/${campaignId}/opportunities/${opportunityId}`,
      { method: "POST" },
    ),
  removeOpportunity: (campaignId: number, opportunityId: number) =>
    request<{ campaign_id: number; opportunity_id: number; message: string }>(
      `/api/campaigns/${campaignId}/opportunities/${opportunityId}`,
      { method: "DELETE" },
    ),
  listOpportunities: (id: number) =>
    request<{ campaign_id: number; total: number; opportunities: import("./types").CampaignOpportunityItem[] }>(
      `/api/campaigns/${id}/opportunities`,
    ),
  summary: (id: number) =>
    request<import("./types").CampaignSummary>(`/api/campaigns/${id}/summary`),
};

// ── Export ───────────────────────────────────────────────────────────────

export const exports_ = {
  downloadUrl: (params?: import("./types").ExportFilterParams) => {
    const base = `${BASE_URL}/api/exports/opportunities.xlsx`;
    const q = qs(params || {});
    return q ? `${base}${q}` : base;
  },
};

export { ApiError };
