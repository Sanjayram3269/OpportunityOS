// Server-only BFF configuration.
//
// SECURITY: this module must only ever be imported from server code (route
// handlers under src/app/api/**). It reads process.env directly — never a
// NEXT_PUBLIC_* variable — so no value here is inlined into a client
// bundle. There are deliberately NO fallback values: missing or weak
// configuration fails closed (routes return 503 with an actionable
// message) instead of degrading to an insecure default.

export interface BffServerConfig {
  /** Upstream FastAPI origin. Server-controlled; never taken from a request. */
  apiBaseUrl: string;
  /** FastAPI bearer token. "" when unset → proxy fails closed (503). */
  apiAuthToken: string;
  /** HMAC secret for session cookies. "" when unset or too weak → 503. */
  sessionSecret: string;
  /** Sign-in token users type at /login. "" when unset → login fails closed. */
  loginToken: string;
  sessionTtlSeconds: number;
  /** Upstream request timeout in ms (automation runs hit 3 external APIs). */
  upstreamTimeoutMs: number;
  /** Origins allowed to make state-changing (CSRF-relevant) requests. */
  allowedOrigins: string[];
  isProduction: boolean;
  /** Secure cookie attribute: on in production, off for plain-HTTP dev. */
  cookieSecure: boolean;
}

/** Minimum accepted SESSION_SECRET length ("strong server-side secret"). */
const MIN_SESSION_SECRET_LENGTH = 32;
const DEFAULT_SESSION_TTL_HOURS = 12;

function read(name: string): string {
  return (process.env[name] ?? "").trim();
}

function readInt(name: string, fallback: number): number {
  const raw = read(name);
  if (!raw) return fallback;
  const parsed = Number.parseInt(raw, 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

export function getServerConfig(): BffServerConfig {
  const isProduction = process.env.NODE_ENV === "production";

  const sessionSecret = read("SESSION_SECRET");
  const apiBaseUrl = (read("API_BASE_URL") || "http://localhost:8000").replace(/\/+$/, "");

  const allowedOrigins = read("BFF_ALLOWED_ORIGINS")
    .split(",")
    .map((o) => o.trim().replace(/\/+$/, ""))
    .filter(Boolean);
  // Development convenience only: local origins. Production MUST set
  // BFF_ALLOWED_ORIGINS explicitly — see configProblems().
  const origins =
    allowedOrigins.length > 0
      ? allowedOrigins
      : isProduction
        ? []
        : ["http://localhost:3000", "http://localhost:3001"];

  const ttlHours = readInt("SESSION_TTL_HOURS", DEFAULT_SESSION_TTL_HOURS);
  // Default 180s: a full automation run performs up to 3 external HTTP
  // fetches (30s timeout each) plus ingestion and scoring. A 30s cap here
  // cut the client off while the server keeps working (observed live).
  const upstreamTimeoutSeconds = readInt("BFF_UPSTREAM_TIMEOUT_SECONDS", 180);

  return {
    apiBaseUrl,
    apiAuthToken: read("API_AUTH_TOKEN"),
    sessionSecret:
      sessionSecret.length >= MIN_SESSION_SECRET_LENGTH ? sessionSecret : "",
    loginToken: read("BFF_LOGIN_TOKEN"),
    sessionTtlSeconds: ttlHours * 3600,
    upstreamTimeoutMs: upstreamTimeoutSeconds * 1000,
    allowedOrigins: origins,
    isProduction,
    cookieSecure: isProduction,
  };
}

/**
 * Configuration problems that must block sign-in. Returned as actionable
 * messages; never includes secret values.
 */
export function loginConfigProblems(cfg: BffServerConfig): string[] {
  const problems: string[] = [];
  if (!cfg.loginToken) {
    problems.push("BFF_LOGIN_TOKEN is not set");
  }
  if (!cfg.sessionSecret) {
    problems.push(
      `SESSION_SECRET is not set or is shorter than ${MIN_SESSION_SECRET_LENGTH} characters`,
    );
  }
  if (cfg.isProduction && cfg.allowedOrigins.length === 0) {
    problems.push("BFF_ALLOWED_ORIGINS is not set (required in production)");
  }
  return problems;
}

/**
 * Configuration problems that must block the API proxy. The proxy may run
 * without BFF_LOGIN_TOKEN (sessions can still be verified), but it always
 * needs the upstream token and the session secret.
 */
export function proxyConfigProblems(cfg: BffServerConfig): string[] {
  const problems: string[] = [];
  if (!cfg.apiAuthToken) {
    problems.push("API_AUTH_TOKEN is not set");
  }
  if (!cfg.sessionSecret) {
    problems.push(
      `SESSION_SECRET is not set or is shorter than ${MIN_SESSION_SECRET_LENGTH} characters`,
    );
  }
  return problems;
}
