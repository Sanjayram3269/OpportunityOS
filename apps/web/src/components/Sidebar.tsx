"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV_ITEMS = [
  { href: "/", label: "Overview", icon: "📊" },
  { href: "/opportunities", label: "Opportunities", icon: "🎯" },
  { href: "/discover", label: "Discover", icon: "🔍" },
  { href: "/planning", label: "Planning", icon: "📅" },
  { href: "/outreach", label: "Outreach", icon: "✉️" },
  { href: "/follow-ups", label: "Follow-ups", icon: "🔔" },
  { href: "/campaigns", label: "Campaigns", icon: "📁" },
  { href: "/companies", label: "Companies", icon: "🏢" },
  { href: "/leads", label: "Leads", icon: "👤" },
  { href: "/export", label: "Export", icon: "📤" },
];

export function Sidebar({
  mobileOpen,
  onClose,
}: {
  mobileOpen?: boolean;
  onClose?: () => void;
}) {
  const pathname = usePathname();

  return (
    <>
      {/* Mobile overlay */}
      {mobileOpen && (
        <div
          className="fixed inset-0 bg-black/30 z-40 lg:hidden"
          onClick={onClose}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`fixed inset-y-0 left-0 z-50 w-60 bg-white border-r border-gray-200 transform transition-transform duration-200 ease-in-out
        ${mobileOpen ? "translate-x-0" : "-translate-x-full"}
        lg:translate-x-0 lg:static lg:z-auto`}
      >
        {/* Logo */}
        <div className="flex items-center gap-2.5 px-5 h-16 border-b border-gray-100">
          <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center">
            <span className="text-white text-sm font-bold">O</span>
          </div>
          <div>
            <div className="text-sm font-bold text-gray-900 leading-tight">
              OpportunityOS
            </div>
            <div className="text-[10px] text-gray-400 leading-tight">
              Opportunity Operating System
            </div>
          </div>
        </div>

        {/* Navigation */}
        <nav className="px-3 py-4 space-y-0.5 overflow-y-auto flex-1">
          {NAV_ITEMS.map((item) => {
            const isActive =
              item.href === "/"
                ? pathname === "/"
                : pathname.startsWith(item.href);

            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={onClose}
                className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors duration-100 ${
                  isActive
                    ? "bg-blue-50 text-blue-700"
                    : "text-gray-600 hover:bg-gray-50 hover:text-gray-900"
                }`}
              >
                <span className="text-base">{item.icon}</span>
                {item.label}
              </Link>
            );
          })}
        </nav>

        {/* Footer */}
        <div className="px-5 py-4 border-t border-gray-100">
          <div className="text-[10px] text-gray-400">
            v0.1.0 · PostgreSQL · FastAPI
          </div>
        </div>
      </aside>
    </>
  );
}
