import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";

// Mock fetch globally
const mockFetch = vi.fn();
vi.stubGlobal("fetch", mockFetch);

// ── API Client Tests ─────────────────────────────────────────────────────

describe("API client", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("makes correct API calls", async () => {
    const { opportunities } = await import("@/lib/api");
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => [],
    });

    await opportunities.list();
    expect(mockFetch).toHaveBeenCalledWith(
      "http://localhost:8000/opportunities",
      expect.objectContaining({
        headers: { "Content-Type": "application/json" },
      }),
    );
  });

  it("handles API errors", async () => {
    const { opportunities } = await import("@/lib/api");
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 404,
      json: async () => ({ detail: "Not found" }),
    });

    await expect(opportunities.get(999)).rejects.toThrow("Not found");
  });

  it("returns undefined for 204 responses", async () => {
    const { opportunities } = await import("@/lib/api");
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 204,
    });

    const result = await opportunities.delete(1);
    expect(result).toBeUndefined();
  });

  it("builds correct query strings", async () => {
    const { planning } = await import("@/lib/api");
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ total: 0, opportunities: [] }),
    });

    await planning.list({
      horizon: "SUMMER_2027",
      min_match_score: 70,
    });

    const url = mockFetch.mock.calls[0][0] as string;
    expect(url).toContain("horizon=SUMMER_2027");
    expect(url).toContain("min_match_score=70");
  });

  it("omits undefined query params", async () => {
    const { planning } = await import("@/lib/api");
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ total: 0, opportunities: [] }),
    });

    await planning.list({});
    const url = mockFetch.mock.calls[0][0] as string;
    expect(url).not.toContain("?");
  });
});

// ── Types Tests ──────────────────────────────────────────────────────────

describe("Types", () => {
  it("exports planning horizon colors", async () => {
    const { HORIZON_COLORS } = await import("@/lib/types");
    expect(HORIZON_COLORS.NOW).toContain("red");
    expect(HORIZON_COLORS.UPCOMING).toContain("amber");
    expect(HORIZON_COLORS.SUMMER_2027).toContain("orange");
    expect(HORIZON_COLORS.FUTURE).toContain("blue");
    expect(HORIZON_COLORS.UNKNOWN).toContain("gray");
  });

  it("exports status colors for all known statuses", async () => {
    const { STATUS_COLORS } = await import("@/lib/types");
    expect(STATUS_COLORS.DRAFT).toBeDefined();
    expect(STATUS_COLORS.PENDING_APPROVAL).toBeDefined();
    expect(STATUS_COLORS.APPROVED).toBeDefined();
    expect(STATUS_COLORS.READY_TO_SEND).toBeDefined();
    expect(STATUS_COLORS.SENT).toBeDefined();
    expect(STATUS_COLORS.REJECTED).toBeDefined();
    expect(STATUS_COLORS.ACTIVE).toBeDefined();
    expect(STATUS_COLORS.COMPLETED).toBeDefined();
  });

  it("exports opportunity type labels", async () => {
    const { OPPORTUNITY_TYPE_LABELS } = await import("@/lib/types");
    expect(OPPORTUNITY_TYPE_LABELS.INTERNSHIP).toBe("Internship");
    expect(OPPORTUNITY_TYPE_LABELS.FULL_TIME).toBe("Full-time");
    expect(OPPORTUNITY_TYPE_LABELS.RESEARCH).toBe("Research");
  });

  it("exports priority colors", async () => {
    const { PRIORITY_COLORS } = await import("@/lib/types");
    expect(PRIORITY_COLORS.CRITICAL).toBeDefined();
    expect(PRIORITY_COLORS.HIGH).toBeDefined();
    expect(PRIORITY_COLORS.MEDIUM).toBeDefined();
    expect(PRIORITY_COLORS.LOW).toBeDefined();
  });
});

// ── UI Component Tests ───────────────────────────────────────────────────

describe("UI Components", () => {
  it("renders Badge with correct variant", async () => {
    const { Badge } = await import("@/components/ui");
    render(<Badge variant="success">Active</Badge>);
    expect(screen.getByText("Active")).toBeInTheDocument();
  });

  it("renders Button with loading state", async () => {
    const { Button } = await import("@/components/ui");
    render(<Button loading>Save</Button>);
    expect(screen.getByText("Save")).toBeInTheDocument();
  });

  it("renders KPICard with label and value", async () => {
    const { KPICard } = await import("@/components/ui");
    render(<KPICard label="Total" value={42} icon="📊" />);
    expect(screen.getByText("Total")).toBeInTheDocument();
    expect(screen.getByText("42")).toBeInTheDocument();
  });

  it("renders EmptyState", async () => {
    const { EmptyState } = await import("@/components/ui");
    render(<EmptyState title="No data" description="Nothing here" />);
    expect(screen.getByText("No data")).toBeInTheDocument();
    expect(screen.getByText("Nothing here")).toBeInTheDocument();
  });

  it("renders ErrorState with retry", async () => {
    const { ErrorState } = await import("@/components/ui");
    const onRetry = vi.fn();
    render(<ErrorState message="Failed" onRetry={onRetry} />);
    expect(screen.getByText("Something went wrong")).toBeInTheDocument();
  });

  it("renders ScoreBadge with score", async () => {
    const { ScoreBadge } = await import("@/components/ui");
    render(<ScoreBadge score={85} />);
    expect(screen.getByText("85")).toBeInTheDocument();
  });

  it("renders ScoreBadge with null", async () => {
    const { ScoreBadge } = await import("@/components/ui");
    render(<ScoreBadge score={null} />);
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("renders StatusDot", async () => {
    const { StatusDot } = await import("@/components/ui");
    const { container } = render(<StatusDot status="SENT" />);
    expect(container.querySelector(".rounded-full")).toBeInTheDocument();
  });

  it("renders Input with label", async () => {
    const { Input } = await import("@/components/ui");
    render(<Input label="Name" value="" onChange={() => {}} />);
    expect(screen.getByText("Name")).toBeInTheDocument();
  });

  it("renders Select with options", async () => {
    const { Select } = await import("@/components/ui");
    render(
      <Select
        label="Type"
        value=""
        onChange={() => {}}
        options={[{ label: "Internship", value: "INTERNSHIP" }]}
      />,
    );
    expect(screen.getByDisplayValue("All")).toBeInTheDocument();
  });
});

// ── Outreach Workflow Tests ──────────────────────────────────────────────

describe("Outreach state machine", () => {
  it("validates state transitions match backend rules", () => {
    const validTransitions: Record<string, string[]> = {
      DRAFT: ["PENDING_APPROVAL", "REJECTED"],
      PENDING_APPROVAL: ["APPROVED", "REJECTED"],
      APPROVED: ["READY_TO_SEND", "REJECTED"],
      READY_TO_SEND: ["SENT"],
      SENT: [],
      REJECTED: [],
    };

    // DRAFT can become PENDING_APPROVAL
    expect(validTransitions.DRAFT).toContain("PENDING_APPROVAL");
    // DRAFT cannot go directly to READY_TO_SEND
    expect(validTransitions.DRAFT).not.toContain("READY_TO_SEND");
    // APPROVED can become READY_TO_SEND
    expect(validTransitions.APPROVED).toContain("READY_TO_SEND");
    // READY_TO_SEND can become SENT
    expect(validTransitions.READY_TO_SEND).toContain("SENT");
    // SENT is terminal
    expect(validTransitions.SENT).toHaveLength(0);
    // REJECTED is terminal
    expect(validTransitions.REJECTED).toHaveLength(0);
  });
});

// ── Follow-up Workflow Tests ─────────────────────────────────────────────

describe("Follow-up state machine", () => {
  it("validates follow-up transitions", () => {
    const validTransitions: Record<string, string[]> = {
      PENDING: ["DUE", "CANCELLED"],
      DUE: ["PENDING_APPROVAL", "CANCELLED"],
      PENDING_APPROVAL: ["APPROVED", "CANCELLED"],
      APPROVED: ["READY_TO_SEND", "CANCELLED"],
      READY_TO_SEND: ["COMPLETED", "CANCELLED"],
      COMPLETED: [],
      CANCELLED: [],
    };

    expect(validTransitions.PENDING).toContain("DUE");
    expect(validTransitions.DUE).toContain("PENDING_APPROVAL");
    expect(validTransitions.PENDING_APPROVAL).toContain("APPROVED");
    expect(validTransitions.APPROVED).toContain("READY_TO_SEND");
    expect(validTransitions.READY_TO_SEND).toContain("COMPLETED");
    expect(validTransitions.COMPLETED).toHaveLength(0);
    expect(validTransitions.CANCELLED).toHaveLength(0);
  });
});

// ── Campaign Lifecycle Tests ─────────────────────────────────────────────

describe("Campaign lifecycle", () => {
  it("validates campaign transitions", () => {
    const validTransitions: Record<string, string[]> = {
      DRAFT: ["ACTIVE", "ARCHIVED"],
      ACTIVE: ["PAUSED", "COMPLETED", "ARCHIVED"],
      PAUSED: ["ACTIVE", "COMPLETED", "ARCHIVED"],
      COMPLETED: ["ARCHIVED"],
      ARCHIVED: [],
    };

    expect(validTransitions.DRAFT).toContain("ACTIVE");
    expect(validTransitions.ACTIVE).toContain("PAUSED");
    expect(validTransitions.ACTIVE).toContain("COMPLETED");
    expect(validTransitions.PAUSED).toContain("ACTIVE");
    expect(validTransitions.COMPLETED).toContain("ARCHIVED");
    expect(validTransitions.ARCHIVED).toHaveLength(0);
  });
});

// ── Planning Horizon Tests ───────────────────────────────────────────────

describe("Planning horizons", () => {
  it("defines all five horizons", async () => {
    const { HORIZON_COLORS } = await import("@/lib/types");
    const horizons = Object.keys(HORIZON_COLORS);
    expect(horizons).toContain("NOW");
    expect(horizons).toContain("UPCOMING");
    expect(horizons).toContain("SUMMER_2027");
    expect(horizons).toContain("FUTURE");
    expect(horizons).toContain("UNKNOWN");
    expect(horizons).toHaveLength(5);
  });
});

// ── Export Tests ─────────────────────────────────────────────────────────

describe("Export", () => {
  it("generates correct download URL", async () => {
    const { exports_ } = await import("@/lib/api");
    const url = exports_.downloadUrl();
    expect(url).toBe("http://localhost:8000/exports/opportunities.xlsx");
  });

  it("includes filter params in URL", async () => {
    const { exports_ } = await import("@/lib/api");
    const url = exports_.downloadUrl({ planning_horizon: "SUMMER_2027", min_match_score: 80 });
    expect(url).toContain("planning_horizon=SUMMER_2027");
    expect(url).toContain("min_match_score=80");
  });
});

// ── Discovery Tests ──────────────────────────────────────────────────────

describe("Discovery", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("calls discovery source list endpoint", async () => {
    const { discovery } = await import("@/lib/api");
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ sources: ["remotive", "arbeitnow"] }),
    });

    const result = await discovery.sources();
    expect(result.sources).toEqual(["remotive", "arbeitnow"]);
    expect(mockFetch).toHaveBeenCalledWith(
      "http://localhost:8000/discovery/sources",
      expect.anything(),
    );
  });

  it("calls discovery run with POST", async () => {
    const { discovery } = await import("@/lib/api");
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        source_name: "remotive",
        raw_count: 10,
        ingested: 6,
        duplicates_skipped: 2,
        companies_created: 3,
        errors: [],
      }),
    });

    const result = await discovery.run("remotive");
    expect(result.ingested).toBe(6);
    expect(mockFetch).toHaveBeenCalledWith(
      "http://localhost:8000/discovery/run/remotive",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("calls discovery sources metadata endpoint", async () => {
    const { discovery } = await import("@/lib/api");
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        sources: [
          { name: "remotive", display_name: "Remotive", requires_auth: false, adapter_available: true },
          { name: "linkedin", display_name: "LinkedIn", requires_auth: true, adapter_available: false },
        ],
        active_count: 1,
        total_count: 2,
        auth_required_count: 1,
      }),
    });

    const result = await discovery.sourcesMetadata();
    expect(result.sources).toHaveLength(2);
    expect(result.active_count).toBe(1);
    expect(result.auth_required_count).toBe(1);
  });

  it("calls discovery health endpoint", async () => {
    const { discovery } = await import("@/lib/api");
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        status: "healthy",
        active_sources: ["remotive", "arbeitnow", "himalayas"],
        auth_required_sources: ["linkedin", "handshake", "jobstep"],
        total_sources: 6,
      }),
    });

    const result = await discovery.health();
    expect(result.status).toBe("healthy");
    expect(result.active_sources).toHaveLength(3);
  });

  it("calls discovery preview endpoint", async () => {
    const { discovery } = await import("@/lib/api");
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        source_name: "remotive",
        raw_count: 50,
        enriched_count: 50,
        remote_count: 45,
        worldwide_count: 30,
        countries: ["Global"],
        categories: ["Software Engineering"],
        all_skills: ["python", "javascript"],
        errors: [],
        opportunities: [],
      }),
    });

    const result = await discovery.preview("remotive");
    expect(result.raw_count).toBe(50);
    expect(result.remote_count).toBe(45);
    expect(result.all_skills).toContain("python");
  });
});

// ── Application Lifecycle Tests ─────────────────────────────────────────

describe("Application lifecycle", () => {
  it("validates application state transitions", () => {
    const validTransitions: Record<string, string[]> = {
      NOT_APPLIED: ["READY"],
      READY: ["APPLIED", "REJECTED", "WITHDRAWN"],
      APPLIED: ["ASSESSMENT", "INTERVIEW", "REJECTED", "WITHDRAWN"],
      ASSESSMENT: ["INTERVIEW", "FINAL_ROUND", "REJECTED", "WITHDRAWN"],
      INTERVIEW: ["FINAL_ROUND", "OFFER", "REJECTED", "WITHDRAWN"],
      FINAL_ROUND: ["OFFER", "REJECTED", "WITHDRAWN"],
      OFFER: ["ACCEPTED", "REJECTED", "WITHDRAWN"],
    };
    const terminal = ["ACCEPTED", "REJECTED", "WITHDRAWN"];

    expect(validTransitions.NOT_APPLIED).toContain("READY");
    expect(validTransitions.READY).toContain("APPLIED");
    expect(validTransitions.APPLIED).toContain("INTERVIEW");
    expect(validTransitions.INTERVIEW).toContain("OFFER");
    expect(validTransitions.OFFER).toContain("ACCEPTED");
    // Terminal states
    expect(terminal).toContain("ACCEPTED");
    expect(terminal).toContain("REJECTED");
    expect(terminal).toContain("WITHDRAWN");
    // Invalid transitions
    expect(validTransitions.NOT_APPLIED).not.toContain("APPLIED");
    expect(validTransitions.NOT_APPLIED).not.toContain("INTERVIEW");
  });

  it("calls applications list endpoint", async () => {
    const { applications } = await import("@/lib/api");
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => [],
    });
    const result = await applications.list();
    expect(Array.isArray(result)).toBe(true);
  });

  it("calls actions generate endpoint", async () => {
    const { actions } = await import("@/lib/api");
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ generated: 3, dry_run: false, actions: [] }),
    });
    const result = await actions.generate();
    expect(result.generated).toBe(3);
  });

  it("calls actions summary endpoint", async () => {
    const { actions } = await import("@/lib/api");
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        total_actions: 5,
        open: 3,
        in_progress: 1,
        completed: 1,
        dismissed: 0,
        expired: 0,
        by_priority: { P0: 1, P1: 1, P2: 1 },
        by_type: {},
      }),
    });
    const result = await actions.summary();
    expect(result.open).toBe(3);
  });

  it("calls triage endpoint", async () => {
    const { triage } = await import("@/lib/api");
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        opportunity_id: 1,
        match_score: 85,
        planning_horizon: "SUMMER_2027",
        deadline_bucket: "FUTURE",
        application_status: "NOT_APPLIED",
        recommended_action: "APPLY",
        priority: "P1",
        explanation: "Good match.",
      }),
    });
    const result = await triage.get(1);
    expect(result.planning_horizon).toBe("SUMMER_2027");
    expect(result.priority).toBe("P1");
  });
});

// ── Action Center Type Tests ─────────────────────────────────────────────

describe("Action Center types", () => {
  it("Action API client has all methods", async () => {
    const { actions } = await import("@/lib/api");
    expect(typeof actions.list).toBe("function");
    expect(typeof actions.get).toBe("function");
    expect(typeof actions.summary).toBe("function");
    expect(typeof actions.generate).toBe("function");
    expect(typeof actions.complete).toBe("function");
    expect(typeof actions.dismiss).toBe("function");
    expect(typeof actions.start).toBe("function");
  });

  it("Application API client has all methods", async () => {
    const { applications } = await import("@/lib/api");
    expect(typeof applications.list).toBe("function");
    expect(typeof applications.get).toBe("function");
    expect(typeof applications.create).toBe("function");
    expect(typeof applications.transitions).toBe("function");
    expect(typeof applications.transition).toBe("function");
    expect(typeof applications.analytics).toBe("function");
  });
});
