// Centralized API client for OpportunityOS backend.
// All fetch calls go through here for consistent error handling.

const BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

type GenerateActionsResponse = {
  generated: number;
  dry_run: boolean;
  actions: Array<{
    action_type: string;
    priority: string;
    entity_type: string;
    entity_id: number;
    title: string;
  }>;
};

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
  list: () => request<import("./types").Profile[]>("/profiles"),
  get: (id: number) => request<import("./types").Profile>(`/profiles/${id}`),
  create: (data: Record<string, unknown>) =>
    request<import("./types").Profile>("/profiles", { method: "POST", body: JSON.stringify(data) }),
  update: (id: number, data: Record<string, unknown>) =>
    request<import("./types").Profile>(`/profiles/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  delete: (id: number) =>
    request<void>(`/profiles/${id}`, { method: "DELETE" }),
};

// ── Companies ────────────────────────────────────────────────────────────

export const companies = {
  list: () => request<import("./types").Company[]>("/companies"),
  get: (id: number) => request<import("./types").Company>(`/companies/${id}`),
  create: (data: Record<string, unknown>) =>
    request<import("./types").Company>("/companies", { method: "POST", body: JSON.stringify(data) }),
  update: (id: number, data: Record<string, unknown>) =>
    request<import("./types").Company>(`/companies/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  delete: (id: number) =>
    request<void>(`/companies/${id}`, { method: "DELETE" }),
  getLeads: (id: number) =>
    request<import("./types").Lead[]>(`/companies/${id}/leads`),
  getOpportunities: (id: number) =>
    request<import("./types").Opportunity[]>(`/companies/${id}/opportunities`),
};

// ── Leads ────────────────────────────────────────────────────────────────

export const leads = {
  list: () => request<import("./types").Lead[]>("/leads"),
  get: (id: number) => request<import("./types").Lead>(`/leads/${id}`),
  create: (data: Record<string, unknown>) =>
    request<import("./types").Lead>("/leads", { method: "POST", body: JSON.stringify(data) }),
  update: (id: number, data: Record<string, unknown>) =>
    request<import("./types").Lead>(`/leads/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  delete: (id: number) =>
    request<void>(`/leads/${id}`, { method: "DELETE" }),
  getOpportunities: (id: number) =>
    request<import("./types").Opportunity[]>(`/leads/${id}/opportunities`),
};

// ── Opportunities ────────────────────────────────────────────────────────

export const opportunities = {
  list: () => request<import("./types").Opportunity[]>("/opportunities"),
  get: (id: number) => request<import("./types").Opportunity>(`/opportunities/${id}`),
  create: (data: Record<string, unknown>) =>
    request<import("./types").Opportunity>("/opportunities", { method: "POST", body: JSON.stringify(data) }),
  update: (id: number, data: Record<string, unknown>) =>
    request<import("./types").Opportunity>(`/opportunities/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  delete: (id: number) =>
    request<void>(`/opportunities/${id}`, { method: "DELETE" }),
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
      `/opportunities/planning${qs(params || {})}`,
    ),
  overview: () =>
    request<import("./types").PlanningOverview>("/opportunities/planning/overview"),
  enriched: (params?: {
    horizon?: string;
    min_match_score?: number;
    type?: string;
    status?: string;
    priority?: string;
    campaign_id?: number;
    limit?: number;
  }) =>
    request<{ total: number; opportunities: import("./types").EnrichedPlanningItem[] }>(
      `/opportunities/planning/enriched${qs(params || {})}`,
    ),
};

// ── Matching ─────────────────────────────────────────────────────────────

export const matching = {
  match: (profileId: number, opportunityId: number) =>
    request<import("./types").MatchResult>(
      `/matching/profiles/${profileId}/opportunities/${opportunityId}`,
    ),
  ranked: (profileId: number, limit?: number) =>
    request<import("./types").RankedOpportunitiesResponse>(
      `/matching/profiles/${profileId}/ranked${qs({ limit: limit || 20 })}`,
    ),
};

// ── AI Insight ───────────────────────────────────────────────────────────

export const aiInsight = {
  get: (profileId: number, opportunityId: number) =>
    request<import("./types").OpportunityMatchInsightResponse>(
      `/matching/profiles/${profileId}/opportunities/${opportunityId}/insight`,
    ),
};

// ── Discovery ────────────────────────────────────────────────────────────

export const discovery = {
  sources: () =>
    request<import("./types").SourceListResponse>("/discovery/sources"),
  sourcesMetadata: () =>
    request<import("./types").SourceMetadataListResponse>("/discovery/sources/metadata"),
  sourceMetadata: (name: string) =>
    request<import("./types").SourceMetadataInfo>(`/discovery/sources/${name}/metadata`),
  health: () =>
    request<import("./types").DiscoveryHealthResponse>("/discovery/health"),
  run: (source: string) =>
    request<import("./types").IngestionResult>(`/discovery/run/${source}`, {
      method: "POST",
    }),
  preview: (source: string) =>
    request<import("./types").EnrichedDiscoveryResponse>(`/discovery/sources/${source}/preview`),
  ingestRaw: (items: unknown[]) =>
    request<import("./types").IngestionResult>("/discovery/run", {
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
      `/outreach/drafts${qs(params || {})}`,
    ),
  get: (id: number) =>
    request<import("./types").DraftResponse>(`/outreach/drafts/${id}`),
  create: (data: { profile_id: number; lead_id: number; opportunity_id: number; channel?: string }) =>
    request<import("./types").DraftResponse>("/outreach/drafts", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  update: (id: number, data: { subject?: string; body?: string }) =>
    request<import("./types").DraftResponse>(`/outreach/drafts/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),
  submit: (id: number) =>
    request<import("./types").DraftStateTransitionResponse>(
      `/outreach/drafts/${id}/submit`,
      { method: "POST" },
    ),
  approve: (id: number) =>
    request<import("./types").DraftStateTransitionResponse>(
      `/outreach/drafts/${id}/approve`,
      { method: "POST" },
    ),
  ready: (id: number) =>
    request<import("./types").DraftStateTransitionResponse>(
      `/outreach/drafts/${id}/ready`,
      { method: "POST" },
    ),
  send: (id: number) =>
    request<import("./types").SendDraftResponse>(
      `/outreach/drafts/${id}/send`,
      { method: "POST" },
    ),
  reject: (id: number) =>
    request<import("./types").DraftStateTransitionResponse>(
      `/outreach/drafts/${id}/reject`,
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
      `/follow-ups${qs(params || {})}`,
    ),
  get: (id: number) =>
    request<import("./types").FollowUp>(`/follow-ups/${id}`),
  create: (data: {
    lead_id: number;
    opportunity_id?: number;
    message_id?: number;
    scheduled_for: string;
    reason?: string;
  }) =>
    request<import("./types").FollowUp>("/follow-ups", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  update: (id: number, data: { scheduled_for?: string; reason?: string }) =>
    request<import("./types").FollowUp>(`/follow-ups/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),
  markDue: (id: number) =>
    request<import("./types").FollowUpStateTransitionResponse>(
      `/follow-ups/${id}/mark-due`,
      { method: "POST" },
    ),
  submit: (id: number) =>
    request<import("./types").FollowUpStateTransitionResponse>(
      `/follow-ups/${id}/submit`,
      { method: "POST" },
    ),
  approve: (id: number) =>
    request<import("./types").FollowUpStateTransitionResponse>(
      `/follow-ups/${id}/approve`,
      { method: "POST" },
    ),
  ready: (id: number) =>
    request<import("./types").FollowUpStateTransitionResponse>(
      `/follow-ups/${id}/ready`,
      { method: "POST" },
    ),
  complete: (id: number) =>
    request<import("./types").FollowUpStateTransitionResponse>(
      `/follow-ups/${id}/complete`,
      { method: "POST" },
    ),
  cancel: (id: number) =>
    request<import("./types").FollowUpStateTransitionResponse>(
      `/follow-ups/${id}/cancel`,
      { method: "POST" },
    ),
};

// ── Campaigns ────────────────────────────────────────────────────────────

export const campaigns = {
  list: (params?: { status?: string; type?: string; limit?: number }) =>
    request<import("./types").CampaignListResponse>(
      `/campaigns${qs(params || {})}`,
    ),
  get: (id: number) =>
    request<import("./types").Campaign>(`/campaigns/${id}`),
  create: (data: { name: string; type: string; description?: string }) =>
    request<import("./types").Campaign>("/campaigns", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  update: (id: number, data: Record<string, unknown>) =>
    request<import("./types").Campaign>(`/campaigns/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),
  activate: (id: number) =>
    request<import("./types").Campaign>(`/campaigns/${id}/activate`, { method: "POST" }),
  pause: (id: number) =>
    request<import("./types").Campaign>(`/campaigns/${id}/pause`, { method: "POST" }),
  complete: (id: number) =>
    request<import("./types").Campaign>(`/campaigns/${id}/complete`, { method: "POST" }),
  archive: (id: number) =>
    request<import("./types").Campaign>(`/campaigns/${id}/archive`, { method: "POST" }),
  addOpportunity: (campaignId: number, opportunityId: number) =>
    request<{ campaign_id: number; opportunity_id: number; message: string }>(
      `/campaigns/${campaignId}/opportunities/${opportunityId}`,
      { method: "POST" },
    ),
  removeOpportunity: (campaignId: number, opportunityId: number) =>
    request<{ campaign_id: number; opportunity_id: number; message: string }>(
      `/campaigns/${campaignId}/opportunities/${opportunityId}`,
      { method: "DELETE" },
    ),
  listOpportunities: (id: number) =>
    request<{ campaign_id: number; total: number; opportunities: import("./types").CampaignOpportunityItem[] }>(
      `/campaigns/${id}/opportunities`,
    ),
  summary: (id: number) =>
    request<import("./types").CampaignSummary>(`/campaigns/${id}/summary`),
  enhancedSummary: (id: number) =>
    request<import("./types").EnhancedCampaignSummary>(`/campaigns/${id}/enhanced-summary`),
  planning: (id: number, params?: { horizon?: string; min_match_score?: number }) =>
    request<{ campaign_id: number; campaign_name: string; total: number; opportunities: import("./types").CampaignPlanningItem[] }>(
      `/campaigns/${id}/planning${qs(params || {})}`,
    ),
  actionSummary: (id: number) =>
    request<import("./types").CampaignActionSummary>(`/campaigns/${id}/action-summary`),
};

// ── Export ───────────────────────────────────────────────────────────────

export const exports_ = {
  downloadUrl: (params?: import("./types").ExportFilterParams) => {
    const base = `${BASE_URL}/exports/opportunities.xlsx`;
    const q = qs(params || {});
    return q ? `${base}${q}` : base;
  },
};

// ── Automation ─────────────────────────────────────────────────────────

export const automation = {
  status: () =>
    request<import("./types").AutomationConfig>("/automation/status"),
  config: () =>
    request<import("./types").AutomationConfig>("/automation/config"),
  run: (params?: { dry_run?: boolean; source?: string }) =>
    request<import("./types").AutomationRunResult>("/automation/run", {
      method: "POST",
      body: JSON.stringify(params || {}),
    }),
  runs: (params?: { status?: string; trigger?: string; limit?: number; offset?: number }) =>
    request<import("./types").AutomationRunHistoryResponse>(
      `/automation/runs${qs(params || {})}`,
    ),
};

// ── Applications ────────────────────────────────────────────────────────

export const applications = {
  list: (params?: { status?: string; opportunity_id?: number; limit?: number }) =>
    request<import("./types").Application[]>(`/applications${qs(params || {})}`),
  get: (id: number) =>
    request<import("./types").ApplicationWith>(`/applications/${id}`),
  create: (data: { opportunity_id: number; lead_id?: number; application_url?: string; notes?: string }) =>
    request<import("./types").Application>("/applications", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  transitions: (id: number) =>
    request<import("./types").ApplicationTransitions>(`/applications/${id}/transitions`),
  transition: (id: number, action: string) =>
    request<import("./types").Application>(`/applications/${id}/${action}`, { method: "POST" }),
  analytics: () =>
    request<import("./types").ApplicationAnalytics>("/applications/analytics/summary"),
};

// ── Actions ─────────────────────────────────────────────────────────────

export const actions = {
  list: (params?: { status?: string; action_type?: string; priority?: string; limit?: number }) =>
    request<import("./types").ActionItem[]>(`/actions${qs(params || {})}`),
  get: (id: number) =>
    request<import("./types").ActionItem>(`/actions/${id}`),
  summary: () =>
    request<import("./types").ActionSummary>("/actions/summary"),
  generate: (dryRun?: boolean) => {
    const params = dryRun ? "?dry_run=true" : "";
    return request<GenerateActionsResponse>(`/actions/generate${params}`,
      { method: "POST" },
    );
  },
  complete: (id: number) =>
    request<import("./types").ActionItem>(`/actions/${id}/complete`, { method: "POST" }),
  dismiss: (id: number) =>
    request<import("./types").ActionItem>(`/actions/${id}/dismiss`, { method: "POST" }),
  start: (id: number) =>
    request<import("./types").ActionItem>(`/actions/${id}/start`, { method: "POST" }),
};

// ── Triage ──────────────────────────────────────────────────────────────

export const triage = {
  get: (opportunityId: number) =>
    request<import("./types").TriageResult>(`/opportunities/${opportunityId}/triage`),
};

// ── Dashboard / Command Center ────────────────────────────────────────

type CmdCenterResponse = import("./types").CommandCenterResponse;

export const dashboard = {
  overview: () => request<CmdCenterResponse>(`/dashboard/overview`),
};

// ── Timeline ────────────────────────────────────────────────────────────

type TimelineResp = import("./types").TimelineResponse;

export const timeline = {
  get: (applicationId: number) =>
    request<TimelineResp>(`/applications/${applicationId}/timeline`),
};

// ── Analytics Deep Dive ────────────────────────────────────────────────

type AnalyticsDeepResp = import("./types").AnalyticsDeepResponse;

type CampaignDrilldownResp = import("./types").CampaignDrilldownResponse;

export const analyticsDeep = {
  overview: (params?: { start_date?: string; end_date?: string }) => {
    const qs = new URLSearchParams();
    if (params?.start_date) qs.set("start_date", params.start_date);
    if (params?.end_date) qs.set("end_date", params.end_date);
    const query = qs.toString();
    return request<AnalyticsDeepResp>(`/analytics/overview${query ? "?" + query : ""}`);
  },
  campaignDrilldown: (campaignId: number) =>
    request<CampaignDrilldownResp>(`/analytics/campaigns/${campaignId}`),
};

// ── Notifications / Attention ───────────────────────────────────────

type NotificationItem = import("./types").NotificationItem;
type UnreadCountResponse = import("./types").UnreadCountResponse;
type SyncResponse = import("./types").SyncResponse;

export const notifications = {
  list: (params?: {
    unread_only?: boolean;
    notification_type?: string;
    severity?: string;
    limit?: number;
  }) =>
    request<NotificationItem[]>(`/notifications${qs(params || {})}`),
  unreadCount: () =>
    request<UnreadCountResponse>("/notifications/unread-count"),
  markRead: (id: number) =>
    request<{ id: number; read_at: string | null }>(
      `/notifications/${id}/read`,
      { method: "POST" },
    ),
  markAllRead: () =>
    request<{ marked_read: number }>("/notifications/read-all", {
      method: "POST",
    }),
  sync: () =>
    request<SyncResponse>("/notifications/sync", { method: "POST" }),
};

export { ApiError };
