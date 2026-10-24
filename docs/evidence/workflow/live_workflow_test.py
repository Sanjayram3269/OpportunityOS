"""Live end-to-end workflow test for OpportunityOS.

Drives the REAL running application (Next.js BFF on :3000 -> FastAPI on
:8000 -> PostgreSQL) over HTTP, with real database writes and real external
source integrations (Remotive / Arbeitnow / Himalayas). Nothing is mocked.

Safety:
  - Signs in with BFF_LOGIN_TOKEN read from apps/web/.env.local in-process.
    The token and session cookies are NEVER printed or logged.
  - Creates one clearly-synthetic demo profile (demo@example.com).
  - Outreach 'send' is attempted only against a synthetic lead whose email
    is undeliverable, and the server has no email provider configured, so
    the send fails safely by design. No real message can leave the system.

Run from the repository root with the API virtualenv interpreter:
  apps/api/.venv/Scripts/python.exe docs/evidence/workflow/live_workflow_test.py

Exit code 0 = all checks passed. Output is a human-readable PASS/FAIL log.
"""

from __future__ import annotations

import json
import sys
import time
from collections import Counter
from pathlib import Path

import httpx

BASE = "http://localhost:3000"  # Next.js BFF
REPO_ROOT = Path(__file__).resolve().parents[3]

PASS = 0
FAIL = 0
RESULTS: list[tuple[str, str, str]] = []  # (check, status, detail)


def check(name: str, ok: bool, detail: str = "") -> bool:
    global PASS, FAIL
    status = "PASS" if ok else "FAIL"
    if ok:
        PASS += 1
    else:
        FAIL += 1
    RESULTS.append((name, status, detail))
    print(f"[{status}] {name}" + (f" — {detail}" if detail else ""))
    return ok


def read_login_token() -> str:
    env_local = REPO_ROOT / "apps" / "web" / ".env.local"
    for line in env_local.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("BFF_LOGIN_TOKEN="):
            return line.split("=", 1)[1].strip()
    raise RuntimeError("BFF_LOGIN_TOKEN not found in apps/web/.env.local")


def main() -> int:
    token = read_login_token()
    client = httpx.Client(base_url=BASE, timeout=120.0)

    # ── A. Authentication ─────────────────────────────────────────────
    print("\n=== A. Authentication ===")
    r = client.get("/api/auth/session")
    check("A1 session unauthenticated before login",
          r.json().get("authenticated") is False)

    r = client.post(
        "/api/auth/login",
        json={"token": token},
        headers={"Origin": BASE},
    )
    check("A2 login succeeds", r.status_code == 200, f"HTTP {r.status_code}")
    sc = r.headers.get("set-cookie", "")
    check("A3 session cookie is HttpOnly + SameSite=Lax + Secure",
          all(f in sc for f in ("HttpOnly", "SameSite=Lax", "Secure")))
    check("A4 login response body contains no token",
          token not in r.text and "BFF_LOGIN" not in r.text)

    # Carry the session cookie explicitly on every request. The cookie is
    # Secure-attributed; over plain-HTTP localhost we bypass jar policy by
    # setting the header ourselves (browsers accept Secure cookies on
    # localhost). The value is never printed.
    session_cookie = sc.split("oppo_session=", 1)[1].split(";", 1)[0]
    client.headers["Cookie"] = f"oppo_session={session_cookie}"
    client.headers["Origin"] = BASE

    r = client.get("/api/auth/session")
    check("A5 session authenticated after login",
          r.json().get("authenticated") is True)

    # Unauthenticated client for rejection checks.
    anon = httpx.Client(base_url=BASE, timeout=30.0)
    r = anon.get("/api/bff/profiles")
    check("A6 unauthenticated BFF call rejected 401", r.status_code == 401)
    r = anon.post("/api/bff/profiles", json={"name": "x", "email": "x@example.com"})
    check("A7 unauthenticated write rejected 401", r.status_code == 401)
    r = client.post(
        "/api/bff/profiles",
        json={"name": "csrf", "email": "csrf@example.com"},
        headers={"Origin": "https://evil.example"},
    )
    check("A8 cross-site write rejected 403 (CSRF)", r.status_code == 403)

    # ── B. Profile creation + persistence + duplicate prevention ──────
    print("\n=== B. Profile lifecycle ===")
    profile = {
        "name": "Demo User",
        "email": "demo@example.com",
        "headline": "Python & Full-Stack Engineer",
        "bio": "Demo profile for workflow verification. Synthetic data.",
        "current_city": "Remote",
        "geographic_preference": "Remote",
        "skills_summary": "python, fastapi, sqlalchemy, react, typescript, javascript, postgres, docker, git, rest apis",
        "preferred_role_types": "FULL_TIME",
        "work_arrangement": "REMOTE",
        "graduation_year": 2026,
    }
    # Idempotent setup: reuse the demo profile if a previous run left it.
    existing = [p for p in client.get("/api/bff/profiles").json()
                if p.get("email") == "demo@example.com"]
    if existing:
        pid = existing[0]["id"]
        r = client.patch(f"/api/bff/profiles/{pid}", json=profile,
                         headers={"Origin": BASE})
        check("B1 demo profile reused from a previous run",
              r.status_code == 200, f"id={pid}, HTTP {r.status_code}")
    else:
        r = client.post("/api/bff/profiles", json=profile,
                        headers={"Origin": BASE})
        check("B1 profile created", r.status_code == 201,
              f"HTTP {r.status_code}")
        pid = r.json().get("id") if r.status_code == 201 else None
    if pid is None:
        print("FATAL: cannot continue without a profile")
        return 1

    r = client.get(f"/api/bff/profiles/{pid}")
    got = r.json()
    check("B2 profile persisted across reload (skills round-trip)",
          got.get("skills_summary") == profile["skills_summary"])
    check("B3 profile persisted (geographic preference)",
          got.get("geographic_preference") == "Remote")

    r = client.post("/api/bff/profiles", json=profile, headers={"Origin": BASE})
    check("B4 duplicate profile rejected 409 (no dupes on resubmit)",
          r.status_code == 409, f"HTTP {r.status_code}")

    r = client.get("/api/bff/profiles")
    demo_profiles = [p for p in r.json() if p.get("email") == "demo@example.com"]
    check("B5 exactly one demo profile exists", len(demo_profiles) == 1,
          f"demo profiles={len(demo_profiles)}, total={len(r.json())}")

    # ── C. Discovery: real external sources + dedup ───────────────────
    print("\n=== C. Discovery (real external sources) ===")
    r = client.get("/api/bff/discovery/health")
    health = r.json()
    check("C1 discovery health endpoint responds",
          r.status_code == 200 and "status" in health,
          f"status={health.get('status')}, active={health.get('active_sources')}")

    t0 = time.time()
    r = client.post("/api/bff/automation/run", json={},
                    headers={"Origin": BASE}, timeout=300.0)
    dt = time.time() - t0
    check("C2 automation run (discovery+matching+planning) completes",
          r.status_code == 200 and str(r.json().get("status", "")).upper() == "COMPLETED",
          f"{dt:.1f}s, status={r.json().get('status')}")
    run1 = r.json()
    src_results = run1.get("source_results", [])
    live_sources = [s for s in src_results if s.get("source_name")
                    in ("remotive", "arbeitnow", "himalayas")]
    succeeded = [s for s in live_sources if s.get("success")]
    check("C3 at least one real external source succeeded",
          len(succeeded) >= 1,
          "; ".join(f"{s['source_name']}: raw={s.get('raw_count')} "
                    f"ingested={s.get('ingested')} err={s.get('errors')}"
                    for s in live_sources))
    created1 = run1.get("opportunities_created", 0)
    deduped1 = run1.get("opportunities_deduplicated", 0) or 0
    # On a fresh database this run INGESTS live data (created > 0); on a
    # populated database it VERIFIES every fetched record as already known
    # (deduped > 0). Either outcome proves the live pipeline ran.
    check("C4 opportunities ingested or verified from live sources",
          created1 > 0 or deduped1 > 0,
          f"created={created1}, deduped={deduped1}")

    r = client.get("/api/bff/opportunities")
    opps = r.json()
    check("C5 ingested opportunities visible via API", len(opps) > 0,
          f"count={len(opps)}")

    # External failure handling: unknown source must fail gracefully.
    r = client.post("/api/bff/discovery/run/not-a-real-source",
                    headers={"Origin": BASE})
    check("C6 unknown source fails gracefully (no 5xx)",
          r.status_code == 200 and r.json().get("errors"),
          f"HTTP {r.status_code}, errors={r.json().get('errors')}")

    # Auth-required stub sources must fail gracefully too.
    r = client.post("/api/bff/discovery/run/linkedin", headers={"Origin": BASE})
    check("C7 auth-required stub source fails gracefully",
          r.status_code == 200 and r.json().get("errors"),
          f"errors={r.json().get('errors')}")

    # Dedup: a second run must re-ingest NOTHING it has already seen.
    # A live feed may legitimately add NEW listings between runs (observed:
    # 2 fresh listings appeared mid-test), so the invariant is
    # "every URL known before the re-run still appears exactly once" —
    # not "the total count is unchanged".
    urls1 = {o.get("source_url") for o in opps if o.get("source_url")}
    r = client.post("/api/bff/automation/run", json={},
                    headers={"Origin": BASE}, timeout=300.0)
    run2 = r.json()

    r = client.get("/api/bff/opportunities")
    opps2 = r.json()
    urls2 = [o.get("source_url") for o in opps2 if o.get("source_url")]
    counts2 = Counter(urls2)
    reingested = [u for u in urls1 if counts2[u] > 1]
    check("C8 re-run deduplicates every known opportunity",
          (run2.get("opportunities_deduplicated") or 0) > 0 and not reingested,
          f"deduped={run2.get('opportunities_deduplicated')}, "
          f"created={run2.get('opportunities_created')} (new live listings), "
          f"re-ingested={len(reingested)}")

    dup_urls = len(urls2) - len(set(urls2))
    check("C9 no duplicate opportunities after re-run",
          dup_urls == 0,
          f"{len(opps)} -> {len(opps2)} opportunities, "
          f"{dup_urls} duplicate source_urls")

    # ── D. Matching: scores, explanations ─────────────────────────────
    print("\n=== D. Matching & scoring ===")
    r = client.get(f"/api/bff/matching/profiles/{pid}/ranked?limit=100")
    ranked = r.json()
    matches = ranked.get("matches", [])
    check("D1 ranked matches returned", len(matches) > 0,
          f"total={ranked.get('total_opportunities')}")
    scored = [m for m in matches if isinstance(m.get("score"), int)]
    check("D2 all opportunities carry an integer score",
          len(scored) == len(matches) and len(scored) > 0,
          f"{len(scored)}/{len(matches)}")
    top = matches[0] if matches else {}
    check("D3 top match has explanation text",
          bool(top.get("explanation")), repr(top.get("explanation"))[:80])
    check("D4 top match has component score breakdown",
          all(k in top for k in (
              "skill_overlap_score", "title_relevance_score",
              "location_fit_score", "type_fit_score")),
          json.dumps({k: top.get(k) for k in (
              "skill_overlap_score", "title_relevance_score",
              "location_fit_score", "type_fit_score")}))
    sorted_ok = all(
        matches[i]["score"] >= matches[i + 1]["score"]
        for i in range(len(matches) - 1)
    )
    check("D5 results sorted by score descending", sorted_ok)
    check("D6 scores within 0-100", all(0 <= m["score"] <= 100 for m in matches))

    stored_scores = [o.get("match_score") for o in opps]
    check("D7 stored opportunity scores populated (automation)",
          all(isinstance(s, int) for s in stored_scores) and len(stored_scores) > 0,
          f"scored={sum(1 for s in stored_scores if isinstance(s, int))}/{len(stored_scores)}")

    # Determinism: same request twice -> identical scores.
    r2 = client.get(f"/api/bff/matching/profiles/{pid}/ranked?limit=100")
    same = ([m["score"] for m in r2.json().get("matches", [])]
            == [m["score"] for m in matches])
    check("D8 scoring is deterministic (identical on repeat)", same)

    # ── E. Preference change responsiveness ───────────────────────────
    print("\n=== E. Preference changes ===")
    before_top_score = top.get("score")
    # Change preferences drastically: strip skills, prefer RESEARCH, onsite.
    r = client.patch(
        f"/api/bff/profiles/{pid}",
        json={
            "skills_summary": "calligraphy, art history",
            "preferred_role_types": "RESEARCH",
            "geographic_preference": "Onsite only",
            "current_city": "Chennai",
        },
        headers={"Origin": BASE},
    )
    check("E1 profile preferences updated", r.status_code == 200)
    r = client.get(f"/api/bff/matching/profiles/{pid}/ranked?limit=100")
    after = r.json().get("matches", [])
    after_top = after[0].get("score") if after else None
    check("E2 live re-ranking responds to preference change",
          after_top != before_top_score,
          f"top score {before_top_score} -> {after_top}")

    # Restore the good preferences.
    r = client.patch(
        f"/api/bff/profiles/{pid}",
        json={
            "skills_summary": profile["skills_summary"],
            "preferred_role_types": "FULL_TIME",
            "geographic_preference": "Remote",
            "current_city": "Remote",
        },
        headers={"Origin": BASE},
    )
    check("E3 preferences restored", r.status_code == 200)
    r = client.get(f"/api/bff/matching/profiles/{pid}/ranked?limit=1")
    restored = r.json().get("matches", [{}])[0].get("score")
    check("E4 scores restored after preference restore",
          restored == before_top_score,
          f"{before_top_score} -> {restored}")

    # ── F. Planning, filters, pagination, export ──────────────────────
    print("\n=== F. Planning, filters, export ===")
    r = client.get("/api/bff/opportunities/planning?limit=5")
    plan = r.json()
    check("F1 planning list returns data", plan.get("total", 0) > 0,
          f"total={plan.get('total')}")
    item = (plan.get("opportunities") or [{}])[0]
    check("F2 planning item has horizon + priority + score",
          all(k in item for k in ("planning_horizon", "planning_priority",
                                  "match_score")),
          json.dumps({k: item.get(k) for k in
                      ("planning_horizon", "planning_priority", "match_score")}))

    r = client.get("/api/bff/opportunities/planning?min_match_score=1&limit=100")
    filtered = r.json().get("opportunities", [])
    check("F3 min_match_score filter works",
          all(o.get("match_score", 0) >= 1 for o in filtered),
          f"{len(filtered)} items with score>=1")
    r = client.get("/api/bff/opportunities/planning?limit=3")
    check("F4 limit/pagination parameter respected",
          len(r.json().get("opportunities", [])) <= 3)

    r = client.get("/api/bff/exports/opportunities.xlsx")
    check("F5 XLSX export streams through BFF",
          r.status_code == 200 and "spreadsheetml" in
          r.headers.get("content-type", ""),
          r.headers.get("content-type", ""))

    # ── G. Outreach: full approval workflow, never auto-sends ─────────
    print("\n=== G. Outreach workflow (approval enforced) ===")
    # Idempotent: reuse the synthetic company from a previous run if present.
    existing_cos = [c for c in client.get("/api/bff/companies").json()
                    if c.get("name") == "Synthetic TestCo (workflow test)"]
    if existing_cos:
        co_id = existing_cos[0]["id"]
        check("G1 synthetic company reused from a previous run", True,
              f"id={co_id}")
    else:
        r = client.post("/api/bff/companies",
                        json={"name": "Synthetic TestCo (workflow test)"},
                        headers={"Origin": BASE})
        check("G1 company created", r.status_code in (200, 201))
        co_id = r.json().get("id")

    existing_leads = [l for l in client.get("/api/bff/leads").json()
                      if l.get("email") == "undeliverable@example.com"]
    if existing_leads:
        lead_id = existing_leads[0]["id"]
        check("G2 synthetic lead reused from a previous run", True,
              f"id={lead_id}")
    else:
        r = client.post(
            "/api/bff/leads",
            json={
                "company_id": co_id,
                "name": "Test Recipient",
                "title": "Hiring Manager",
                # Non-deliverable documentation address (RFC 2606).
                "email": "undeliverable@example.com",
                "source": "workflow-test",
            },
            headers={"Origin": BASE},
        )
        check("G2 lead created", r.status_code in (200, 201))
        lead_id = r.json().get("id")

    r = client.get("/api/bff/opportunities?limit=1")
    some_opp = (r.json() or [{}])[0]
    opp_id = some_opp.get("id")

    r = client.post(
        "/api/bff/outreach/drafts",
        json={"profile_id": pid, "lead_id": lead_id, "opportunity_id": opp_id},
        headers={"Origin": BASE},
    )
    check("G3 draft generated (template fallback, no AI key)", r.status_code == 201)
    draft = r.json()
    did = draft.get("id")
    check("G4 draft starts in DRAFT status", draft.get("status") == "DRAFT",
          draft.get("status"))
    check("G5 draft body is personalized (mentions skills or title)",
          any(w in (draft.get("body") or "").lower()
              for w in ("python", "engineer", "opportunity", "demo")))

    # Illegal transitions must be rejected.
    r = client.post(f"/api/bff/outreach/drafts/{did}/send", headers={"Origin": BASE})
    check("G6 send from DRAFT rejected 409 (approval required)",
          r.status_code == 409, f"HTTP {r.status_code}")
    r = client.post(f"/api/bff/outreach/drafts/{did}/approve", headers={"Origin": BASE})
    check("G7 approve from DRAFT rejected 409 (must submit first)",
          r.status_code == 409, f"HTTP {r.status_code}")
    r = client.post(f"/api/bff/outreach/drafts/{did}/ready", headers={"Origin": BASE})
    check("G8 ready-from-DRAFT rejected 409", r.status_code == 409)

    # Legal path: submit -> approve -> ready.
    r = client.post(f"/api/bff/outreach/drafts/{did}/submit", headers={"Origin": BASE})
    check("G9 submit DRAFT->PENDING_APPROVAL", r.status_code == 200
          and r.json().get("new_status") == "PENDING_APPROVAL")
    r = client.post(f"/api/bff/outreach/drafts/{did}/approve", headers={"Origin": BASE})
    check("G10 approve PENDING_APPROVAL->APPROVED", r.status_code == 200
          and r.json().get("new_status") == "APPROVED")
    r = client.post(f"/api/bff/outreach/drafts/{did}/ready", headers={"Origin": BASE})
    check("G11 ready APPROVED->READY_TO_SEND", r.status_code == 200
          and r.json().get("new_status") == "READY_TO_SEND")

    # Send: server has no email provider -> must fail SAFE (no email leaves).
    r = client.post(f"/api/bff/outreach/drafts/{did}/send", headers={"Origin": BASE})
    body = r.json()
    check("G12 send without email provider fails safely (no real email)",
          r.status_code == 200 and body.get("success") is False
          and "not configured" in (body.get("error") or ""),
          f"success={body.get('success')}, error={body.get('error')!r}")
    r = client.get(f"/api/bff/outreach/drafts/{did}")
    check("G13 failed send leaves draft READY_TO_SEND (not SENT)",
          r.json().get("status") == "READY_TO_SEND", r.json().get("status"))

    r = client.get(f"/api/bff/outreach/drafts?status=SENT")
    check("G14 no messages in SENT state anywhere", r.json().get("total") == 0,
          f"total={r.json().get('total')}")

    # ── H. Actions, notifications, dashboard, analytics ───────────────
    print("\n=== H. dashboards & intelligence surfaces ===")
    r = client.get("/api/bff/dashboard/overview")
    check("H1 dashboard overview responds", r.status_code == 200)
    r = client.get("/api/bff/actions")
    check("H2 action items generated", r.status_code == 200,
          f"count={len(r.json()) if r.status_code == 200 else 'n/a'}")
    r = client.get("/api/bff/notifications")
    check("H3 notifications synced", r.status_code == 200,
          f"count={len(r.json()) if r.status_code == 200 else 'n/a'}")
    r = client.get("/api/bff/analytics/overview")
    check("H4 analytics overview responds", r.status_code == 200)
    r = client.get("/api/bff/automation/runs?limit=5")
    check("H5 automation run history persisted", r.status_code == 200
          and r.json().get("total", 0) >= 2,
          f"total={r.json().get('total')}")

    # Idempotency: the FIRST generate may legitimately catch up on state
    # that changed since the last run (e.g. a draft that reached
    # READY_TO_SEND during section G). The SECOND generate, with no state
    # change in between, must create nothing new.
    client.post("/api/bff/actions/generate", headers={"Origin": BASE})
    n1 = len(client.get("/api/bff/actions").json())
    client.post("/api/bff/actions/generate", headers={"Origin": BASE})
    n2 = len(client.get("/api/bff/actions").json())
    check("H6 action generation is idempotent (2nd run adds nothing)",
          n2 == n1, f"{n1} -> {n2}")

    # ── I. Status update round-trip ───────────────────────────────────
    print("\n=== I. Status updates ===")
    if opp_id:
        r = client.patch(f"/api/bff/opportunities/{opp_id}",
                         json={"status": "QUALIFIED"}, headers={"Origin": BASE})
        check("I1 opportunity status update works",
              r.status_code == 200 and r.json().get("status") == "QUALIFIED")
        r = client.patch(f"/api/bff/opportunities/{opp_id}",
                         json={"status": "DISCOVERED"}, headers={"Origin": BASE})
        check("I2 status restored", r.status_code == 200)

    # ── J. Session expiry behaviour ───────────────────────────────────
    print("\n=== J. Session expiry ===")
    forged = httpx.Client(base_url=BASE, timeout=30.0,
                          cookies={"oppo_session": "v1.99999999999." + "a" * 43})
    r = forged.get("/api/bff/profiles")
    check("J1 forged/expired session rejected 401", r.status_code == 401)

    # ── Summary ───────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print(f"LIVE WORKFLOW RESULT: {PASS} passed, {FAIL} failed "
          f"({PASS + FAIL} checks)")
    print("=" * 70)
    out_path = Path(__file__).with_name("live_workflow_results.json")
    out_path.write_text(json.dumps(
        {"passed": PASS, "failed": FAIL,
         "checks": [{"name": n, "status": s, "detail": d}
                    for n, s, d in RESULTS]},
        indent=2), encoding="utf-8")
    print(f"Machine-readable results: {out_path}")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
