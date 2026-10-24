"use client";

// Sign-in page. The user types the server-side sign-in token
// (BFF_LOGIN_TOKEN); it is exchanged for an HttpOnly session cookie and
// never stored, logged, or echoed back. This page never sees the FastAPI
// bearer token at all.

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { Button, Card, CardContent, CardHeader, Input } from "@/components/ui";

export default function LoginPage() {
  const router = useRouter();
  const [token, setToken] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token) {
      setError("Enter your sign-in token.");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token }),
      });
      if (!res.ok) {
        let detail = `HTTP ${res.status}`;
        try {
          const body = await res.json();
          detail = body.detail || detail;
        } catch {
          // ignore
        }
        setError(detail);
        return;
      }
      setToken("");
      router.push("/");
      router.refresh();
    } catch {
      setError("Could not reach the server. Is it running?");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 p-4">
      <Card className="w-full max-w-md">
        <CardHeader>
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 bg-blue-600 rounded-lg flex items-center justify-center">
              <span className="text-white text-sm font-bold">O</span>
            </div>
            <div>
              <h1 className="text-base font-bold text-gray-900 leading-tight">
                OpportunityOS
              </h1>
              <p className="text-xs text-gray-500 leading-tight">
                Sign in to continue
              </p>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <Input
              label="Sign-in token"
              type="password"
              value={token}
              onChange={(v) => setToken(v)}
              placeholder="Paste your sign-in token"
              autoComplete="off"
              data-testid="login-token-input"
            />
            {error && (
              <p
                role="alert"
                className="text-sm text-red-600 bg-red-50 border border-red-100 rounded-lg px-3 py-2"
              >
                {error}
              </p>
            )}
            <Button type="submit" loading={submitting} className="w-full">
              Sign in
            </Button>
            <p className="text-xs text-gray-400">
              The token is stored server-side (BFF_LOGIN_TOKEN) and is never
              saved in this browser.
            </p>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
