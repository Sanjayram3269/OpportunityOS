"use client";

// Redirects unauthenticated visitors to /login and returns them after
// sign-in. Runs entirely client-side against the BFF session endpoint;
// it never touches the FastAPI token. Also used to gate the app shell so
// unauthenticated users don't see data-bearing UI.

import React, { useCallback, useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";

export function SessionGate({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [checked, setChecked] = useState(false);
  const [authed, setAuthed] = useState<boolean | null>(null);

  const check = useCallback(async () => {
    try {
      const res = await fetch("/api/auth/session", {
        credentials: "same-origin",
        cache: "no-store",
      });
      const body = (await res.json()) as { authenticated?: boolean };
      return Boolean(body.authenticated);
    } catch {
      // Fail closed: treat a failed session check as unauthenticated.
      return false;
    }
  }, []);

  useEffect(() => {
    if (pathname === "/login") return; // render path below handles it
    let cancelled = false;
    check().then((ok) => {
      if (cancelled) return;
      setAuthed(ok);
      setChecked(true);
      if (!ok) {
        router.replace("/login");
      }
    });
    return () => {
      cancelled = true;
    };
  }, [pathname, router, check]);

  // The API client broadcasts this event whenever any request gets a 401
  // (expired or revoked session) so we redirect without waiting for the
  // next mount.
  useEffect(() => {
    if (pathname === "/login") return;
    const onUnauthorized = () => {
      setAuthed(false);
      router.replace("/login");
    };
    window.addEventListener("bff:unauthorized", onUnauthorized);
    return () => window.removeEventListener("bff:unauthorized", onUnauthorized);
  }, [pathname, router]);

  // While checking (or on the login page) don't flash app UI.
  if (pathname === "/login") return <>{children}</>;
  if (!checked || !authed) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <p className="text-sm text-gray-500">Checking session…</p>
      </div>
    );
  }
  return <>{children}</>;
}

export async function signOut(): Promise<void> {
  try {
    await fetch("/api/auth/logout", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
    });
  } catch {
    // Even if the request fails, navigate to the login page; the cookie
    // will expire server-side via its Max-Age regardless.
  }
}
