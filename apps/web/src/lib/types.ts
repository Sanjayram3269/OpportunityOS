// TypeScript types matching the OpportunityOS FastAPI backend schemas.
// These are derived from the Pydantic models — not invented.

// ── Profile ──────────────────────────────────────────────────────────────

export interface Profile {
  id: number;
  name: string;
  email: string;
  phone: string | null;
  linkedin_url: string | null;
  github_url: string | null;
  portfolio_url: string | null;
  headline: string | null;
  bio: string | null;
  created_at: string;
  updated_at: string;
}

// ── Company ──────────────────────────────────────────────────────────────

export interface Company {
  id: number;
  name: string;
  domain: string | null;
  website: string | null;
  linkedin_url: string | null;
  industry: string | null;
  company_size: string | null;
  location: string | null;
  description: string | null;
  created_at: string;
  updated_at: string;
}

// ── Lead ─────────────────────────────────────────────────────────────────

export interface Lead {
  id: number;
  company_id: number | null;
  name: string;
  title: string | null;
  email: string | null;
  linkedin_url: string | null;
  website_url: string | null;
  location: string | null;
  source: string | null;
  notes: string | null;
  status: string;
  created_at: string;
  updated_at: string;
}

// ── Opportunity ──────────────────────────────────────────────────────────

export interface Opportunity {
  id: number;
  company_id: number;
  lead_id: number | null;
  type: string;
  title: string;
  description: string | null;
  source_url: string | null;
  status: string;
  priority: string;
  match_score: number | null;
  potential_value: string | null;
  deadline: string | null;
  created_at: string;
  updated_at: string;
}

// ── Opportunity Evidence ─────────────────────────────────────────────────

export interface OpportunityEvidence {
  id: number;
  opportunity_id: number;
  source: string | null;
  evidence_type: string | null;
  content: string | null;
  external_id: string | null;
  source_url: string | null;
  captured_at: string;
}

// ── Message / Draft ──────────────────────────────────────────────────────

export interface DraftResponse {
  id: number;
  lead_id: number;
  opportunity_id: number | null;
  channel: string;
  direction: string;
  subject: string | null;
  body: string;
  status: string;
  ai_generated: boolean;
  ai_model: string | null;
  personalization_score: number | null;
  personalization_points: string[];
  created_at: string;
}

export interface DraftListResponse {
  total: number;
  drafts: DraftResponse[];
}

export interface DraftStateTransitionResponse {
  id: number;
  previous_status: string;
  new_status: string;
  message: string;
}

export interface SendDraftResponse {
  id: number;
  previous_status: string;
  new_status: string;
  success: boolean;
  provider: string;
  message_id: string | null;
  error: string | null;
}

// ── FollowUp ─────────────────────────────────────────────────────────────

export interface FollowUp {
  id: number;
  lead_id: number;
  opportunity_id: number | null;
  message_id: number | null;
  scheduled_for: string;
  status: string;
  reason: string | null;
  completed_at: string | null;
  created_at: string;
}

export interface FollowUpListResponse {
  total: number;
  follow_ups: FollowUp[];
}

export interface FollowUpStateTransitionResponse {
  id: number;
  previous_status: string;
  new_status: string;
  message: string;
}

// ── Campaign ─────────────────────────────────────────────────────────────

export interface Campaign {
  id: number;
  name: string;
  type: string;
  description: string | null;
  target_description: string | null;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface CampaignListResponse {
  total: number;
  campaigns: Campaign[];
}

export interface CampaignSummary {
  campaign_id: number;
  campaign_name: string;
  total_opportunities: number;
  average_match_score: number | null;
  high_match_count: number;
  drafts_count: number;
  pending_approval_count: number;
  approved_count: number;
  sent_count: number;
  followups_pending: number;
  followups_completed: number;
  followups_cancelled: number;
}

export interface CampaignOpportunityItem {
  id: number;
  title: string;
  type: string;
  status: string;
  match_score: number | null;
  deadline: string | null;
}

// ── Planning ─────────────────────────────────────────────────────────────

export interface PlanningHorizonInfo {
  opportunity_id: number;
  title: string;
  company_name: string | null;
  opportunity_type: string;
  status: string;
  priority: string;
  deadline: string | null;
  match_score: number | null;
  planning_horizon: string;
  planning_priority: number;
  planning_priority_reasons: string[];
}

export interface PlanningListResponse {
  total: number;
  opportunities: PlanningHorizonInfo[];
}

// ── Matching ─────────────────────────────────────────────────────────────

export interface MatchResult {
  opportunity_id: number;
  title: string;
  company_name: string | null;
  opportunity_type: string;
  location: string | null;
  source_url: string | null;
  score: number;
  matched_skills: string[];
  missing_skills: string[];
  matched_signals: string[];
  concerns: string[];
  explanation: string;
  skill_overlap_score: number;
  title_relevance_score: number;
  experience_relevance_score: number;
  project_relevance_score: number;
  location_fit_score: number;
  type_fit_score: number;
}

export interface RankedOpportunitiesResponse {
  profile_id: number;
  total_opportunities: number;
  matches: MatchResult[];
}

// ── AI Insight ───────────────────────────────────────────────────────────

export interface AIInsight {
  available: boolean;
  provider: string;
  model: string;
  error: string | null;
  match_explanation: string;
  strengths: string[];
  gaps: string[];
  recommendations: string[];
  outreach_angles: string[];
  application_advice: string;
}

export interface OpportunityMatchInsightResponse extends MatchResult {
  ai_insight: AIInsight;
}

// ── Discovery ────────────────────────────────────────────────────────────

export interface IngestionResult {
  total_received: number;
  normalized: number;
  duplicates_skipped: number;
  created: number;
  errors: number;
  error_details: string[];
}

export interface SourceListResponse {
  sources: string[];
}

// ── Export ───────────────────────────────────────────────────────────────

export type ExportFilterParams = {
  planning_horizon?: string;
  min_match_score?: number;
  opportunity_type?: string;
  status?: string;
  priority?: string;
  campaign_id?: number;
  company_id?: number;
  location?: string;
};

// ── Utility ──────────────────────────────────────────────────────────────

export type PlanningHorizon = "NOW" | "UPCOMING" | "SUMMER_2027" | "FUTURE" | "UNKNOWN";

export const HORIZON_COLORS: Record<PlanningHorizon, string> = {
  NOW: "bg-red-100 text-red-800",
  UPCOMING: "bg-amber-100 text-amber-800",
  SUMMER_2027: "bg-orange-100 text-orange-800",
  FUTURE: "bg-blue-100 text-blue-800",
  UNKNOWN: "bg-gray-100 text-gray-600",
};

export const STATUS_COLORS: Record<string, string> = {
  DISCOVERED: "bg-slate-100 text-slate-700",
  MATCHED: "bg-blue-100 text-blue-700",
  QUALIFIED: "bg-indigo-100 text-indigo-700",
  APPLIED: "bg-purple-100 text-purple-700",
  INTERVIEWING: "bg-amber-100 text-amber-800",
  ACCEPTED: "bg-green-100 text-green-700",
  REJECTED: "bg-red-100 text-red-700",
  WITHDRAWN: "bg-gray-100 text-gray-600",
  DRAFT: "bg-slate-100 text-slate-700",
  PENDING_APPROVAL: "bg-amber-100 text-amber-800",
  APPROVED: "bg-green-100 text-green-700",
  READY_TO_SEND: "bg-blue-100 text-blue-700",
  SENT: "bg-emerald-100 text-emerald-700",
  PENDING: "bg-amber-100 text-amber-800",
  DUE: "bg-orange-100 text-orange-800",
  COMPLETED: "bg-green-100 text-green-700",
  CANCELLED: "bg-gray-100 text-gray-600",
  ACTIVE: "bg-green-100 text-green-700",
  PAUSED: "bg-amber-100 text-amber-800",
  ARCHIVED: "bg-gray-100 text-gray-600",
};

export const PRIORITY_COLORS: Record<string, string> = {
  CRITICAL: "bg-red-100 text-red-800",
  HIGH: "bg-orange-100 text-orange-800",
  MEDIUM: "bg-amber-100 text-amber-800",
  LOW: "bg-gray-100 text-gray-600",
};

export const OPPORTUNITY_TYPE_LABELS: Record<string, string> = {
  INTERNSHIP: "Internship",
  FULL_TIME: "Full-time",
  PART_TIME: "Part-time",
  CONTRACT: "Contract",
  FREELANCE: "Freelance",
  RESEARCH: "Research",
  HACKATHON: "Hackathon",
  STARTUP: "Startup",
  REFERRAL: "Referral",
  OTHER: "Other",
};
