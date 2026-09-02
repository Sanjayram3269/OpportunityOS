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

export interface EnhancedCampaignSummary extends CampaignSummary {
  applications_started: number;
  applications_submitted: number;
  interviews: number;
  offers: number;
  rejections: number;
  not_applied: number;
  application_status_breakdown: Record<string, number>;
  followups_overdue: number;
  planning_horizon_distribution: Record<string, number>;
}

export interface CampaignPlanningItem {
  opportunity_id: number;
  title: string;
  company_name: string | null;
  opportunity_type: string;
  status: string;
  priority: string;
  deadline: string | null;
  match_score: number | null;
  planning_horizon: string;
  application_status: string;
  other_campaigns: string[];
}

export interface CampaignActionSummary {
  total_actions: number;
  by_priority: Record<string, number>;
  by_type: Record<string, number>;
  overdue_actions: number;
}

export interface PlanningOverview {
  total_opportunities: number;
  total_applications: number;
  not_applied: number;
  average_match_score: number | null;
  horizon_distribution: Record<string, number>;
  type_distribution: Record<string, number>;
  application_status_distribution: Record<string, number>;
}

export interface EnrichedPlanningItem {
  opportunity_id: number;
  title: string;
  company_name: string | null;
  opportunity_type: string;
  status: string;
  priority: string;
  deadline: string | null;
  match_score: number | null;
  planning_horizon: string;
  application_status: string;
  outreach_status: string;
  followup_status: string;
  campaigns: string[];
  planning_explanation: string;
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
  source_name: string;
  raw_count: number;
  ingested: number;
  duplicates_skipped: number;
  companies_created: number;
  errors: string[];
}

export interface SourceListResponse {
  sources: string[];
}

export interface SourceMetadataInfo {
  name: string;
  display_name: string;
  source_type: string;
  description: string;
  requires_auth: boolean;
  enabled: boolean;
  geographic_coverage: string[];
  supported_types: string[];
  supports_remote: boolean;
  supports_deadline: boolean;
  supports_salary: boolean;
  rate_limit_note: string;
  source_url: string;
  adapter_available: boolean;
}

export interface SourceMetadataListResponse {
  sources: SourceMetadataInfo[];
  active_count: number;
  total_count: number;
  auth_required_count: number;
}

export interface DiscoveryHealthResponse {
  status: string;
  active_sources: string[];
  auth_required_sources: string[];
  total_sources: number;
}

export interface EnrichedOpportunityInfo {
  source_name: string;
  external_id: string | null;
  canonical_source_url: string | null;
  normalized_title: string;
  normalized_company_name: string;
  description: string | null;
  opportunity_type: string;
  normalized_location: string | null;
  is_remote: boolean;
  is_worldwide: boolean;
  city: string | null;
  country: string | null;
  category: string | null;
  extracted_skills: string[];
  deadline: string | null;
}

export interface EnrichedDiscoveryResponse {
  source_name: string;
  raw_count: number;
  enriched_count: number;
  remote_count: number;
  worldwide_count: number;
  countries: string[];
  categories: string[];
  all_skills: string[];
  errors: string[];
  opportunities: EnrichedOpportunityInfo[];
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

// ── Application ──────────────────────────────────────────────────────────

export interface Application {
  id: number;
  opportunity_id: number;
  lead_id: number | null;
  status: string;
  application_url: string | null;
  notes: string | null;
  rejection_reason: string | null;
  applied_at: string | null;
  last_status_change_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ApplicationWith extends Application {
  opportunity: {
    id: number;
    title: string;
    type: string;
    status: string;
    match_score: number | null;
    deadline: string | null;
  } | null;
  company: {
    id: number;
    name: string;
  } | null;
}

export interface ApplicationTransitions {
  current_status: string;
  valid_transitions: string[];
  is_terminal: boolean;
}

// ── Action ──────────────────────────────────────────────────────────────

export interface ActionItem {
  id: number;
  action_type: string;
  priority: string;
  entity_type: string;
  entity_id: number;
  title: string;
  description: string | null;
  status: string;
  source: string | null;
  due_at: string | null;
  completed_at: string | null;
  created_at: string;
}

export interface ActionSummary {
  total_actions: number;
  open: number;
  in_progress: number;
  completed: number;
  dismissed: number;
  expired: number;
  by_priority: Record<string, number>;
  by_type: Record<string, number>;
}

export interface TriageResult {
  opportunity_id: number;
  match_score: number | null;
  planning_horizon: string;
  deadline_bucket: string;
  application_status: string;
  recommended_action: string;
  priority: string;
  explanation: string;
}

export interface ApplicationAnalytics {
  total: number;
  by_status: Record<string, number>;
  by_type: Record<string, number>;
  by_horizon: Record<string, number>;
  average_match_score: number | null;
  interview_rate: number | null;
  offer_rate: number | null;
  rejection_rate: number | null;
}

// ── Automation ──────────────────────────────────────────────────────────

export interface AutomationSourceResult {
  source_name: string;
  raw_count: number;
  ingested: number;
  duplicates_skipped: number;
  companies_created: number;
  success: boolean;
  errors: string[];
}

export interface AutomationRunResult {
  run_id: string;
  status: string;
  trigger: string;
  started_at: string;
  completed_at: string | null;
  duration_seconds: number | null;
  dry_run: boolean;
  sources_attempted: number;
  sources_succeeded: number;
  sources_failed: number;
  source_results: AutomationSourceResult[];
  opportunities_seen: number;
  opportunities_created: number;
  opportunities_deduplicated: number;
  opportunities_scored: number;
  high_match_count: number;
  summer_2027_count: number;
  now_count: number;
  upcoming_count: number;
  future_count: number;
  unknown_count: number;
  drafts_created: number;
  followups_marked_due: number;
  errors: string[];
}

export interface AutomationConfig {
  enabled: boolean;
  scheduler_active: boolean;
  scheduler_interval_minutes: number;
  discovery_enabled: boolean;
  matching_enabled: boolean;
  ai_insights_enabled: boolean;
  outreach_drafts_enabled: boolean;
  followup_processing_enabled: boolean;
  sources: string[];
  min_match_score: number;
  max_opportunities_per_run: number;
  max_drafts_per_run: number;
  dry_run_default: boolean;
}

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

// ── Dashboard / Command Center ───────────────────────────────────────

export interface OverviewSection {
  total_opportunities: number;
  total_applications: number;
  open_actions: number;
  total_actions: number;
  total_campaigns: number;
  active_campaigns: number;
  high_match_opportunities: number;
}

export interface TodaySection {
  overdue_actions: number;
  due_today_actions: number;
  p0_actions: number;
  p1_actions: number;
  overdue_deadlines: number;
  deadlines_within_3_days: number;
  due_followups: number;
}

export interface PipelineSection {
  total: number;
  by_status: Record<string, number>;
  active_count: number;
  terminal_count: number;
  interviews: number;
  offers: number;
  interview_rate: number | null;
  offer_rate: number | null;
}

export interface OpportunitySection {
  total: number;
  high_match: number;
  scored: number;
  average_match_score: number | null;
  match_distribution: Record<string, number>;
  by_type: Record<string, number>;
  by_horizon: Record<string, number>;
  with_deadline: number;
  without_deadline: number;
  not_applied: number;
}

export interface Summer2027Section {
  total: number;
  high_match: number;
  not_applied: number;
  applications: number;
  application_status: Record<string, number>;
  active_campaigns: number;
}

export interface CampaignDashboardInfo {
  id: number;
  name: string;
  type: string | null;
  opportunity_count: number;
}

export interface CampaignDashboardSection {
  total: number;
  by_status: Record<string, number>;
  active_count: number;
  total_campaign_opportunities: number;
  active_campaigns: CampaignDashboardInfo[];
}

export interface OutreachDashboardSection {
  total: number;
  by_status: Record<string, number>;
  drafts: number;
  pending_approval: number;
  approved: number;
  ready_to_send: number;
  sent: number;
  approval_needed: number;
}

export interface FollowUpDashboardSection {
  total: number;
  by_status: Record<string, number>;
  overdue: number;
  pending: number;
  completed: number;
}

export interface FunnelStage {
  stage: string;
  count: number;
}

export interface SourcePerformanceItem {
  source: string;
  opportunities: number;
}

export interface CampaignPerformanceItem {
  campaign: string;
  opportunities: number;
}

export interface AnalyticsSection {
  application_funnel: FunnelStage[];
  application_rate: number | null;
  interview_rate: number | null;
  offer_rate: number | null;
  acceptance_rate: number | null;
  source_performance: SourcePerformanceItem[];
  campaign_performance: CampaignPerformanceItem[];
}

export interface CommandCenterResponse {
  overview: OverviewSection;
  today: TodaySection;
  pipeline: PipelineSection;
  opportunities: OpportunitySection;
  summer_2027: Summer2027Section;
  campaigns: CampaignDashboardSection;
  outreach: OutreachDashboardSection;
  followups: FollowUpDashboardSection;
  analytics: AnalyticsSection;
}

// ── Application Timeline ─────────────────────────────────────────────

export interface TimelineEvent {
  id: number;
  event_type: string;
  from_status: string | null;
  to_status: string;
  label: string;
  metadata: string | null;
  occurred_at: string;
  created_at: string;
}

export interface TimelineResponse {
  application_id: number;
  current_status: string;
  events: TimelineEvent[];
  total: number;
}

// ── Analytics Deep Dive ──────────────────────────────────────────────

export interface OverviewAnalytics {
  total_opportunities: number;
  total_applications: number;
  active_applications: number;
  terminal_applications: number;
  interviews: number;
  offers: number;
  interview_rate: number | null;
  offer_rate: number | null;
}

export interface TrendPeriod {
  current: number;
  previous: number;
  change: number;
  change_pct: number | null;
}

export interface TrendsAnalytics {
  period_start: string;
  period_end: string;
  period_days: number;
  applications: TrendPeriod;
  interviews: TrendPeriod;
  offers: TrendPeriod;
}

export interface VelocityTransition {
  count: number;
  avg_days: number | null;
  median_days: number | null;
}

export interface VelocityAnalytics {
  transitions: Record<string, VelocityTransition>;
}

export interface ConversionStage {
  stage: string;
  count: number;
  at_or_beyond: number;
  conversion_rate: number | null;
}

export interface ConversionAnalytics {
  stages: ConversionStage[];
}

export interface SourceAnalyticsItem {
  company: string;
  opportunities: number;
  high_match: number;
  applications: number;
  interviews: number;
  offers: number;
  application_rate: number | null;
  interview_rate: number | null;
}

export interface SourceAnalyticsResponse {
  sources: SourceAnalyticsItem[];
}

export interface CampaignAnalyticsItem {
  campaign_id: number;
  campaign_name: string;
  status: string;
  opportunities: number;
  high_match: number;
  applications: number;
  interviews: number;
  offers: number;
  application_rate: number | null;
}

export interface CampaignAnalyticsResponse {
  campaigns: CampaignAnalyticsItem[];
}

export interface TypeAnalyticsItem {
  type: string;
  opportunities: number;
  applications: number;
  interviews: number;
  offers: number;
}

export interface TypeAnalyticsResponse {
  types: TypeAnalyticsItem[];
}

export interface MatchBucketItem {
  bucket: string;
  range: string;
  opportunities: number;
  applications: number;
  interviews: number;
  offers: number;
  application_rate: number | null;
}

export interface MatchAnalyticsResponse {
  buckets: MatchBucketItem[];
}

export interface Summer2027Analytics {
  total: number;
  high_match: number;
  not_applied: number;
  applications: number;
  interviews: number;
  offers: number;
  active_campaigns: number;
}

export interface AnalyticsDeepResponse {
  overview: OverviewAnalytics;
  trends: TrendsAnalytics;
  velocity: VelocityAnalytics;
  conversion: ConversionAnalytics;
  source_analytics: SourceAnalyticsResponse;
  campaign_analytics: CampaignAnalyticsResponse;
  type_analytics: TypeAnalyticsResponse;
  match_analytics: MatchAnalyticsResponse;
  summer_2027: Summer2027Analytics;
}

// ── Campaign Drill-Down ──────────────────────────────────────────────

export interface CampaignDrilldownOverview {
  total_opportunities: number;
  high_match: number;
  applications_started: number;
  applications_submitted: number;
  assessments: number;
  interviews: number;
  final_rounds: number;
  offers: number;
  accepted: number;
  rejected: number;
  withdrawn: number;
}

export interface CampaignDrilldownConversion {
  application_rate: number | null;
  assessment_rate: number | null;
  interview_rate: number | null;
  offer_rate: number | null;
  acceptance_rate: number | null;
}

export interface CampaignDrilldownActivity {
  open_actions: number;
  overdue_actions: number;
  outreach_pending_approval: number;
  outreach_ready_to_send: number;
  outreach_sent: number;
  followups_due: number;
}

export interface CampaignDrilldownPlanning {
  NOW: number;
  UPCOMING: number;
  SUMMER_2027: number;
  FUTURE: number;
  UNKNOWN: number;
}

export interface CampaignDrilldownResponse {
  campaign_id: number;
  campaign_name: string;
  campaign_status: string;
  overview: CampaignDrilldownOverview;
  conversion: CampaignDrilldownConversion;
  activity: CampaignDrilldownActivity;
  planning: CampaignDrilldownPlanning;
}

// ── Notifications / Attention ─────────────────────────────────────────

export interface NotificationItem {
  id: number;
  notification_type: string;
  title: string;
  message: string | null;
  severity: string;
  source_type: string;
  source_id: number;
  read_at: string | null;
  dismissed_at: string | null;
  due_at: string | null;
  created_at: string;
}

export interface UnreadCountResponse {
  unread_count: number;
}

export interface SyncResponse {
  created: number;
  timestamp: string;
}
