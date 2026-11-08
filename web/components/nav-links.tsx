"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/chat", label: "Ask" },
  { href: "/floats", label: "Floats" },
  { href: "/#how-it-works", label: "How it works" },
];

export function NavLinks() {
  const pathname = usePathname();
  return (
    <nav aria-label="Main" className="hidden items-center gap-1 text-sm md:flex">
      {LINKS.map((link) => {
        const active = link.href !== "/#how-it-works" && pathname.startsWith(link.href);
        return (
          <Link
            key={link.href}
            href={link.href}
            aria-current={active ? "page" : undefined}
            className={`rounded-full px-3 py-1.5 transition-colors ${
              active ? "bg-surface-2 text-ink" : "text-ink-2 hover:text-ink"
            }`}
          >
            {link.label}
          </Link>
        );
      })}
    </nav>
  );
}
