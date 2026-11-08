"use client";

import { List, X } from "@phosphor-icons/react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

const LINKS = [
  { href: "/chat", label: "Ask" },
  { href: "/floats", label: "Floats" },
  { href: "/compare", label: "Compare" },
  { href: "/#how-it-works", label: "How it works" },
];

function isActive(pathname: string, href: string) {
  return !href.startsWith("/#") && pathname.startsWith(href);
}

export function NavLinks() {
  const pathname = usePathname();
  return (
    <nav aria-label="Main" className="hidden items-center gap-1 text-sm md:flex">
      {LINKS.map((link) => {
        const active = isActive(pathname, link.href);
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

/** Small-screen navigation: a menu button that opens the links under the header. */
export function MobileMenu() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- close the menu after navigating
    setOpen(false);
  }, [pathname]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  return (
    <div className="md:hidden">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-controls="mobile-menu"
        aria-label={open ? "Close menu" : "Open menu"}
        className="grid size-9 place-items-center rounded-full text-ink-2 hover:bg-surface-2 hover:text-ink"
      >
        {open ? <X size={18} /> : <List size={18} />}
      </button>
      {open && (
        <nav
          id="mobile-menu"
          aria-label="Main"
          className="absolute inset-x-0 top-16 border-b border-line bg-bg px-4 pb-5 pt-2 shadow-card"
        >
          <ul className="grid gap-1">
            {LINKS.map((link) => (
              <li key={link.href}>
                <Link
                  href={link.href}
                  onClick={() => setOpen(false)}
                  aria-current={isActive(pathname, link.href) ? "page" : undefined}
                  className="block rounded-xl px-3 py-3 text-base text-ink hover:bg-surface-2"
                >
                  {link.label}
                </Link>
              </li>
            ))}
          </ul>
          <Link
            href="/chat"
            onClick={() => setOpen(false)}
            className="mt-3 flex h-11 items-center justify-center rounded-full bg-accent text-sm font-medium text-accent-ink"
          >
            Ask a question
          </Link>
        </nav>
      )}
    </div>
  );
}
