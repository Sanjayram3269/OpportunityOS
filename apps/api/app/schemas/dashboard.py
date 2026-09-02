"""Pydantic schemas for the Dashboard / Command Center."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class OverviewSection(BaseModel):
    total_opportunities: int = 0
    total_applications: int = 0
    open_actions: int = 0
    total_actions: int = 0
    total_campaigns: int = 0
    active_campaigns: int = 0
    high_match_opportunities: int = 0


class TodaySection(BaseModel):
    overdue_actions: int = 0
    due_today_actions: int = 0
    p0_actions: int = 0
    p1_actions: int = 0
    overdue_deadlines: int = 0
    deadlines_within_3_days: int = 0
    due_followups: int = 0


class PipelineSection(BaseModel):
    total: int = 0
    by_status: Dict[str, int] = {}
    active_count: int = 0
    terminal_count: int = 0
    interviews: int = 0
    offers: int = 0
    interview_rate: Optional[float] = None
    offer_rate: Optional[float] = None


class OpportunitySection(BaseModel):
    total: int = 0
    high_match: int = 0
    scored: int = 0
    average_match_score: Optional[float] = None
    match_distribution: Dict[str, int] = {}
    by_type: Dict[str, int] = {}
    by_horizon: Dict[str, int] = {}
    with_deadline: int = 0
    without_deadline: int = 0
    not_applied: int = 0


class Summer2027Section(BaseModel):
    total: int = 0
    high_match: int = 0
    not_applied: int = 0
    applications: int = 0
    application_status: Dict[str, int] = {}
    active_campaigns: int = 0


class ActiveCampaignInfo(BaseModel):
    id: int
    name: str
    type: Optional[str] = None
    opportunity_count: int = 0


class CampaignSection(BaseModel):
    total: int = 0
    by_status: Dict[str, int] = {}
    active_count: int = 0
    total_campaign_opportunities: int = 0
    active_campaigns: List[ActiveCampaignInfo] = []


class OutreachSection(BaseModel):
    total: int = 0
    by_status: Dict[str, int] = {}
    drafts: int = 0
    pending_approval: int = 0
    approved: int = 0
    ready_to_send: int = 0
    sent: int = 0
    approval_needed: int = 0


class FollowUpSection(BaseModel):
    total: int = 0
    by_status: Dict[str, int] = {}
    overdue: int = 0
    pending: int = 0
    completed: int = 0


class FunnelStage(BaseModel):
    stage: str
    count: int


class SourcePerformance(BaseModel):
    source: str
    opportunities: int


class CampaignPerformance(BaseModel):
    campaign: str
    opportunities: int


class AnalyticsSection(BaseModel):
    application_funnel: List[FunnelStage] = []
    application_rate: Optional[float] = None
    interview_rate: Optional[float] = None
    offer_rate: Optional[float] = None
    acceptance_rate: Optional[float] = None
    source_performance: List[SourcePerformance] = []
    campaign_performance: List[CampaignPerformance] = []


class CommandCenterResponse(BaseModel):
    overview: OverviewSection = OverviewSection()
    today: TodaySection = TodaySection()
    pipeline: PipelineSection = PipelineSection()
    opportunities: OpportunitySection = OpportunitySection()
    summer_2027: Summer2027Section = Summer2027Section()
    campaigns: CampaignSection = CampaignSection()
    outreach: OutreachSection = OutreachSection()
    followups: FollowUpSection = FollowUpSection()
    analytics: AnalyticsSection = AnalyticsSection()
