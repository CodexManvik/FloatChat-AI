import Link from "next/link";
import { GithubLogo } from "@phosphor-icons/react/dist/ssr";
import { REPO_URL } from "@/lib/config";
import { Logo } from "./logo";
import { MobileMenu, NavLinks } from "./nav-links";
import { ThemeToggle } from "./theme-toggle";

export function SiteHeader() {
  return (
    <header className="glass sticky top-0 z-40 border-b border-line">
      <div className="mx-auto flex h-16 max-w-[1240px] items-center gap-6 px-4 sm:px-6">
        <Link href="/" className="flex items-center gap-2.5 font-semibold tracking-tight" aria-label="FloatChat home">
          <Logo />
          <span>FloatChat</span>
        </Link>
        <NavLinks />
        <div className="ml-auto flex items-center gap-1">
          <a
            href={REPO_URL}
            className="grid size-9 place-items-center rounded-full text-ink-2 transition-colors hover:bg-surface-2 hover:text-ink"
            aria-label="Source code on GitHub"
          >
            <GithubLogo size={18} weight="regular" />
          </a>
          <ThemeToggle />
          <Link
            href="/chat"
            className="ml-2 hidden h-9 items-center rounded-full bg-accent px-4 text-sm font-medium text-accent-ink transition-transform active:scale-[0.98] sm:inline-flex"
          >
            Ask a question
          </Link>
          <MobileMenu />
        </div>
      </div>
    </header>
  );
}
