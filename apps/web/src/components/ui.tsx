// Reusable UI primitives for OpportunityOS.
// All built with Tailwind CSS 4 — no external component library.

"use client";

import React from "react";

// ── Badge ────────────────────────────────────────────────────────────────

export function Badge({
  children,
  className = "",
  variant = "default",
}: {
  children: React.ReactNode;
  className?: string;
  variant?: "default" | "success" | "warning" | "error" | "info" | "muted";
}) {
  const variants: Record<string, string> = {
    default: "bg-gray-100 text-gray-700",
    success: "bg-green-100 text-green-700",
    warning: "bg-amber-100 text-amber-800",
    error: "bg-red-100 text-red-700",
    info: "bg-blue-100 text-blue-700",
    muted: "bg-gray-50 text-gray-500",
  };

  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 text-xs font-medium rounded-full ${variants[variant]} ${className}`}
    >
      {children}
    </span>
  );
}

// ── Button ───────────────────────────────────────────────────────────────

export function Button({
  children,
  onClick,
  disabled = false,
  loading = false,
  variant = "primary",
  size = "md",
  className = "",
  type = "button",
  ...props
}: {
  children: React.ReactNode;
  onClick?: (e?: React.MouseEvent<HTMLButtonElement>) => void;
  disabled?: boolean;
  loading?: boolean;
  variant?: "primary" | "secondary" | "danger" | "ghost";
  size?: "sm" | "md" | "lg";
  className?: string;
  type?: "button" | "submit";
} & React.ButtonHTMLAttributes<HTMLButtonElement>) {
  const variants: Record<string, string> = {
    primary:
      "bg-blue-600 text-white hover:bg-blue-700 focus:ring-blue-500",
    secondary:
      "bg-white text-gray-700 border border-gray-300 hover:bg-gray-50 focus:ring-blue-500",
    danger:
      "bg-red-600 text-white hover:bg-red-700 focus:ring-red-500",
    ghost:
      "text-gray-600 hover:bg-gray-100 focus:ring-gray-400",
  };

  const sizes: Record<string, string> = {
    sm: "px-2.5 py-1.5 text-xs",
    md: "px-3.5 py-2 text-sm",
    lg: "px-5 py-2.5 text-base",
  };

  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled || loading}
      className={`inline-flex items-center justify-center gap-1.5 rounded-lg font-medium transition-all duration-150 focus:outline-none focus:ring-2 focus:ring-offset-1 disabled:opacity-50 disabled:cursor-not-allowed ${variants[variant]} ${sizes[size]} ${className}`}
      {...props}
    >
      {loading && (
        <svg
          className="animate-spin h-4 w-4"
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 24 24"
        >
          <circle
            className="opacity-25"
            cx="12"
            cy="12"
            r="10"
            stroke="currentColor"
            strokeWidth="4"
          />
          <path
            className="opacity-75"
            fill="currentColor"
            d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
          />
        </svg>
      )}
      {children}
    </button>
  );
}

// ── Card ─────────────────────────────────────────────────────────────────

export function Card({
  children,
  className = "",
  onClick,
}: {
  children: React.ReactNode;
  className?: string;
  onClick?: () => void;
}) {
  return (
    <div
      className={`bg-white rounded-xl border border-gray-200 shadow-sm ${className}`}
      onClick={onClick}
    >
      {children}
    </div>
  );
}

export function CardHeader({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={`px-5 py-4 border-b border-gray-100 ${className}`}>
      {children}
    </div>
  );
}

export function CardContent({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return <div className={`px-5 py-4 ${className}`}>{children}</div>;
}

// ── Empty State ──────────────────────────────────────────────────────────

export function EmptyState({
  icon,
  title,
  description,
  action,
}: {
  icon?: string;
  title: string;
  description?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      {icon && <div className="text-4xl mb-3">{icon}</div>}
      <h3 className="text-sm font-semibold text-gray-900">{title}</h3>
      {description && (
        <p className="mt-1 text-sm text-gray-500 max-w-sm">{description}</p>
      )}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

// ── Error State ──────────────────────────────────────────────────────────

export function ErrorState({
  message,
  onRetry,
}: {
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <div className="text-4xl mb-3">⚠️</div>
      <h3 className="text-sm font-semibold text-gray-900">
        Something went wrong
      </h3>
      <p className="mt-1 text-sm text-gray-500 max-w-sm">{message}</p>
      {onRetry && (
        <div className="mt-4">
          <Button onClick={onRetry} variant="secondary" size="sm">
            Try again
          </Button>
        </div>
      )}
    </div>
  );
}

// ── Loading Spinner ──────────────────────────────────────────────────────

export function Spinner({ size = "md" }: { size?: "sm" | "md" | "lg" }) {
  const sizes = { sm: "h-4 w-4", md: "h-8 w-8", lg: "h-12 w-12" };
  return (
    <div className="flex items-center justify-center py-8">
      <svg
        className={`animate-spin text-blue-600 ${sizes[size]}`}
        xmlns="http://www.w3.org/2000/svg"
        fill="none"
        viewBox="0 0 24 24"
      >
        <circle
          className="opacity-25"
          cx="12"
          cy="12"
          r="10"
          stroke="currentColor"
          strokeWidth="4"
        />
        <path
          className="opacity-75"
          fill="currentColor"
          d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
        />
      </svg>
    </div>
  );
}

// ── Input ────────────────────────────────────────────────────────────────

export function Input({
  label,
  value,
  onChange,
  placeholder,
  type = "text",
  className = "",
  ...props
}: {
  label?: string;
  value: string;
  onChange: (val: string) => void;
  placeholder?: string;
  type?: string;
  className?: string;
} & Omit<React.InputHTMLAttributes<HTMLInputElement>, "onChange" | "value">) {
  return (
    <div className={className}>
      {label && (
        <label htmlFor={props.id || undefined} className="block text-sm font-medium text-gray-700 mb-1">
          {label}
        </label>
      )}
      <input
        id={props.id || undefined}
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 placeholder-gray-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 transition-colors"
        {...props}
      />
    </div>
  );
}

// ── Select ───────────────────────────────────────────────────────────────

export function Select({
  label,
  value,
  onChange,
  options,
  placeholder = "All",
  className = "",
}: {
  label?: string;
  value: string;
  onChange: (val: string) => void;
  options: { label: string; value: string }[];
  placeholder?: string;
  className?: string;
}) {
  return (
    <div className={className}>
      {label && (
        <label className="block text-sm font-medium text-gray-700 mb-1">
          {label}
        </label>
      )}
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 transition-colors"
      >
        <option value="">{placeholder}</option>
        {options.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
    </div>
  );
}

// ── Score Badge ──────────────────────────────────────────────────────────

export function ScoreBadge({ score }: { score: number | null }) {
  if (score === null) return <span className="text-gray-400 text-xs">—</span>;

  let color = "text-gray-600 bg-gray-100";
  if (score >= 80) color = "text-green-700 bg-green-100";
  else if (score >= 60) color = "text-blue-700 bg-blue-100";
  else if (score >= 40) color = "text-amber-700 bg-amber-100";
  else color = "text-red-700 bg-red-100";

  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 text-xs font-semibold rounded-full ${color}`}
    >
      {score}
    </span>
  );
}

// ── Section Header ───────────────────────────────────────────────────────

export function SectionHeader({
  title,
  count,
  action,
}: {
  title: string;
  count?: number;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex items-center justify-between mb-4">
      <div className="flex items-center gap-2">
        <h2 className="text-lg font-semibold text-gray-900">{title}</h2>
        {count !== undefined && (
          <span className="text-sm text-gray-500">({count})</span>
        )}
      </div>
      {action}
    </div>
  );
}

// ── KPI Card ─────────────────────────────────────────────────────────────

export function KPICard({
  label,
  value,
  icon,
  color = "blue",
}: {
  label: string;
  value: string | number;
  icon?: string;
  color?: string;
}) {
  const colors: Record<string, string> = {
    blue: "bg-blue-50 text-blue-600",
    green: "bg-green-50 text-green-600",
    amber: "bg-amber-50 text-amber-600",
    red: "bg-red-50 text-red-600",
    purple: "bg-purple-50 text-purple-600",
    orange: "bg-orange-50 text-orange-600",
    gray: "bg-gray-50 text-gray-600",
  };

  return (
    <Card className="p-5">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm font-medium text-gray-500">{label}</p>
          <p className="mt-1.5 text-2xl font-bold text-gray-900">{value}</p>
        </div>
        {icon && (
          <div
            className={`flex items-center justify-center w-10 h-10 rounded-lg ${colors[color]}`}
          >
            <span className="text-lg">{icon}</span>
          </div>
        )}
      </div>
    </Card>
  );
}

// ── Status Dot ───────────────────────────────────────────────────────────

export function StatusDot({ status }: { status: string }) {
  const colors: Record<string, string> = {
    DRAFT: "bg-gray-400",
    PENDING: "bg-amber-400",
    DUE: "bg-orange-400",
    PENDING_APPROVAL: "bg-amber-400",
    APPROVED: "bg-green-400",
    READY_TO_SEND: "bg-blue-500",
    SENT: "bg-emerald-500",
    COMPLETED: "bg-green-500",
    REJECTED: "bg-red-400",
    CANCELLED: "bg-gray-400",
    ACTIVE: "bg-green-500",
    PAUSED: "bg-amber-400",
    ARCHIVED: "bg-gray-400",
  };

  return (
    <span
      className={`inline-block w-2 h-2 rounded-full ${colors[status] || "bg-gray-300"}`}
    />
  );
}
