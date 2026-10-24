// End-to-end workflow tests (jsdom integration level).
//
// These drive the real page components (ProfilePage, OpportunitiesPage)
// through the real API client (src/lib/api.ts) against an in-memory
// mock backend served through a routed `fetch` stub. They cover the flows
// the unit tests do not: first-profile creation (including a simulated
// reload and duplicate prevention), session-expiry UX for the BFF's
// 401 / fail-closed 503 responses, and an authenticated workflow
// from profile setup to viewing matched opportunities.
//
// The mock backend stands in for the Next.js BFF (/api/bff/*): requests
// are same-origin and cookie-authenticated. The browser client never
// sends an Authorization header — these tests assert that.
//
// All data is synthetic. No real personal data is ever used.

import { vi } from "vitest";

import React from "react";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { ProfilePage } from "@/app/profile/page";
import { OpportunitiesPage } from "@/components/OpportunitiesPage";
import type { Profile } from "@/lib/types";

// ── In-memory mock backend ────────────────────────────────────────────────

type Mode = "ok" | "401" | "503";

interface MockBackend {
  profiles: Profile[];
  createCalls: number;
  requests: { method: string; url: string; auth: string | undefined; credentials: string | undefined }[];
  mode: Mode;
}

function syntheticProfile(overrides: Partial<Profile> = {}): Profile {
  // Synthetic test identity only — never real personal data.
  return {
    id: 0,
    name: "E2E Workflow Tester",
    email: "e2e-workflow@example.com",
    phone: null,
    linkedin_url: null,
    github_url: null,
    portfolio_url: null,
    headline: "Python Engineer",
    bio: null,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    current_city: "Chennai",
    preferred_cities: null,
    geographic_preference: "Remote",
    degree: null,
    field_of_study: null,
    institution: null,
    graduation_year: null,
    skills_summary: "python, fastapi",
    preferred_role_types: null,
    minimum_compensation: null,
    availability_start: null,
    availability_end: null,
    work_arrangement: null,
    notable_achievements: null,
    ...overrides,
  };
}

function ok(data: unknown) {
  return { ok: true, status: 200, json: async () => data };
}

function fail(status: number, detail: string) {
  return { ok: false, status, json: async () => ({ detail }) };
}

const SYNTHETIC_OPPORTUNITIES = [
  {
    opportunity_id: 101,
    title: "Senior Python Engineer",
    company_name: "Synthetic Labs",
    opportunity_type: "FULL_TIME",
    status: "MATCHED",
    priority: "P1",
    deadline: null,
    match_score: 87,
    planning_horizon: "NOW",
    planning_priority: 1,
    planning_priority_reasons: [],
  },
  {
    opportunity_id: 102,
    title: "React Developer",
    company_name: "Fixture Corp",
    opportunity_type: "FULL_TIME",
    status: "DISCOVERED",
    priority: "P2",
    deadline: null,
    match_score: 54,
    planning_horizon: "UPCOMING",
    planning_priority: 2,
    planning_priority_reasons: [],
  },
];

function installMockBackend(): MockBackend {
  const backend: MockBackend = {
    profiles: [],
    createCalls: 0,
    requests: [],
    mode: "ok",
  };

  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input.toString();
    const method = (init?.method || "GET").toUpperCase();
    const pathname = new URL(url, "http://localhost").pathname;
    const auth = (init?.headers as Record<string, string> | undefined)?.Authorization;
    backend.requests.push({ method, url, auth, credentials: init?.credentials });

    // All API traffic must go through the same-origin BFF.
    if (!pathname.startsWith("/api/bff/")) {
      throw new Error(`Request bypassed the BFF: ${method} ${pathname}`);
    }
    const apiPath = pathname.slice("/api/bff".length);

    if (backend.mode === "401") {
      return fail(401, "Not signed in or session expired.");
    }
    if (backend.mode === "503") {
      return fail(503, "Authentication is not configured on this server. API_AUTH_TOKEN is not set. Set the server-side environment variables and restart.");
    }

    if (method === "GET" && apiPath === "/profiles") {
      return ok(backend.profiles);
    }
    if (method === "POST" && apiPath === "/profiles") {
      backend.createCalls += 1;
      const body = JSON.parse(String(init?.body));
      const created = syntheticProfile({ id: 1000 + backend.createCalls, ...body });
      backend.profiles.push(created);
      return ok(created);
    }
    if (method === "GET" && apiPath === "/opportunities/planning") {
      return ok({ total: SYNTHETIC_OPPORTUNITIES.length, opportunities: SYNTHETIC_OPPORTUNITIES });
    }
    throw new Error(`Unhandled mock route: ${method} ${apiPath}`);
  });

  vi.stubGlobal("fetch", fetchMock);
  return backend;
}

let backend: MockBackend;

beforeEach(() => {
  backend = installMockBackend();
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

// ── 1. First-profile creation, reload, duplicate prevention ───────────────

describe("First-profile creation workflow", () => {
  it("shows the one-time create form when no profile exists", async () => {
    render(<ProfilePage />);
    // Step 1: the prompt (render alone never creates anything).
    expect(await screen.findByText(/single-user app/i)).toBeTruthy();
    expect(backend.createCalls).toBe(0);
    // Step 2: the form appears only after an explicit click.
    fireEvent.click(screen.getByText("Create profile"));
    expect(await screen.findByPlaceholderText("Full name")).toBeTruthy();
    expect(backend.createCalls).toBe(0);
  });

  it("creates exactly one profile on submit and lands in view mode", async () => {
    render(<ProfilePage />);
    fireEvent.click(await screen.findByText("Create profile"));
    const nameInput = await screen.findByPlaceholderText("Full name");
    fireEvent.change(nameInput, { target: { value: "E2E Workflow Tester" } });
    fireEvent.change(screen.getByPlaceholderText("Email address"), {
      target: { value: "e2e-workflow@example.com" },
    });

    fireEvent.submit(screen.getByPlaceholderText("Full name").closest("form")!);

    // Success → view mode showing the saved profile.
    expect(await screen.findByText("E2E Workflow Tester")).toBeTruthy();
    expect(screen.getByText("Edit Profile")).toBeTruthy();
    expect(backend.createCalls).toBe(1);
    expect(backend.profiles).toHaveLength(1);
  });

  it("does not create duplicates on rerenders", async () => {
    const { rerender } = render(<ProfilePage />);
    fireEvent.click(await screen.findByText("Create profile"));
    const nameInput = await screen.findByPlaceholderText("Full name");
    fireEvent.change(nameInput, { target: { value: "E2E Workflow Tester" } });
    fireEvent.change(screen.getByPlaceholderText("Email address"), {
      target: { value: "e2e-workflow@example.com" },
    });
    fireEvent.submit(screen.getByPlaceholderText("Full name").closest("form")!);
    await screen.findByText("E2E Workflow Tester");

    // Several rerenders (as a parent re-rendering would cause).
    rerender(<ProfilePage />);
    rerender(<ProfilePage />);
    rerender(<ProfilePage />);

    expect(backend.createCalls).toBe(1);
  });

  it("shows the existing profile after a reload and never re-creates", async () => {
    // Session 1: create.
    const first = render(<ProfilePage />);
    fireEvent.click(await screen.findByText("Create profile"));
    const nameInput = await screen.findByPlaceholderText("Full name");
    fireEvent.change(nameInput, { target: { value: "E2E Workflow Tester" } });
    fireEvent.change(screen.getByPlaceholderText("Email address"), {
      target: { value: "e2e-workflow@example.com" },
    });
    fireEvent.submit(screen.getByPlaceholderText("Full name").closest("form")!);
    await screen.findByText("E2E Workflow Tester");
    first.unmount();

    // Session 2 ("reload"): a fresh mount reads the stored profile.
    render(<ProfilePage />);
    expect(await screen.findByText("E2E Workflow Tester")).toBeTruthy();
    expect(screen.queryByText("Create profile")).toBeNull(); // no create form
    expect(backend.createCalls).toBe(1); // still exactly one, ever
    expect(backend.profiles).toHaveLength(1);
  });
});

// ── 2. Session-expiry / fail-closed UX ──────────────────────────────

describe("Session-expiry and fail-closed UX", () => {
  it("surfaces an actionable message when the session is missing/expired (401)", async () => {
    backend.mode = "401";
    render(<ProfilePage />);
    expect(
      await screen.findByText(/not signed in, or your session has expired/i),
    ).toBeTruthy();
    expect(backend.createCalls).toBe(0);
  });

  it("surfaces an actionable message when the BFF is fail-closed (503)", async () => {
    backend.mode = "503";
    render(<ProfilePage />);
    expect(await screen.findByText(/Set API_AUTH_TOKEN on the server/)).toBeTruthy();
  });
});

// ── 3. Authenticated workflow: profile setup → matched opportunities ──────

describe("Authenticated workflow: profile → matched opportunities", () => {
  it("routes every request through the BFF with cookies and never an Authorization header", async () => {
    backend.profiles.push(syntheticProfile({ id: 1 }));
    render(<ProfilePage />);
    await screen.findByText("E2E Workflow Tester");
    expect(backend.requests.length).toBeGreaterThan(0);
    for (const req of backend.requests) {
      // Same-origin BFF with cookie credentials; no bearer token in the
      // browser — that is the entire point of the architecture.
      expect(req.url.startsWith("/api/bff/")).toBe(true);
      expect(req.auth).toBeUndefined();
      expect(req.credentials).toBe("same-origin");
    }
  });

  it("flows from a saved profile to viewing matched opportunities", async () => {
    // Backend starts with a completed profile (post-setup state).
    backend.profiles.push(syntheticProfile({ id: 1 }));

    // Step 1: the profile page shows the saved profile.
    const first = render(<ProfilePage />);
    expect(await screen.findByText("E2E Workflow Tester")).toBeTruthy();
    expect(screen.getByText("Python Engineer")).toBeTruthy();
    first.unmount();

    // Step 2: the opportunities page shows ranked matches from the backend.
    render(<OpportunitiesPage />);
    expect(await screen.findByText("Senior Python Engineer")).toBeTruthy();
    expect(screen.getByText("React Developer")).toBeTruthy();
    // Match scores are rendered for the ranked list (ScoreBadge appears in
    // both the Score and Match columns, hence getAllByText).
    expect(screen.getAllByText("87").length).toBeGreaterThan(0);
    expect(screen.getAllByText("54").length).toBeGreaterThan(0);
  });
});
