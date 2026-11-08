import Link from "next/link";
import { REPO_URL } from "@/lib/config";
import { Logo } from "./logo";

export function SiteFooter() {
  return (
    <footer className="border-t border-line">
      <div className="mx-auto grid max-w-[1240px] gap-8 px-4 py-12 text-sm text-ink-2 sm:px-6 md:grid-cols-[1.4fr_1fr_1fr]">
        <div className="max-w-sm">
          <div className="flex items-center gap-2.5 font-semibold text-ink">
            <Logo size={20} />
            FloatChat
          </div>
          <p className="mt-3 leading-relaxed">
            Argo data are collected and made freely available by the International Argo Program and the national
            programs that contribute to it. Served here through the Ifremer ERDDAP.
          </p>
        </div>
        <nav aria-label="Product" className="grid content-start gap-2">
          <Link href="/chat" className="hover:text-ink">Ask a question</Link>
          <Link href="/floats" className="hover:text-ink">Browse floats</Link>
          <Link href="/#how-it-works" className="hover:text-ink">How it works</Link>
        </nav>
        <nav aria-label="Project" className="grid content-start gap-2">
          <a href={REPO_URL} className="hover:text-ink">Source on GitHub</a>
          <a href="https://argo.ucsd.edu" className="hover:text-ink">About Argo</a>
          <a href="https://erddap.ifremer.fr/erddap/" className="hover:text-ink">Ifremer ERDDAP</a>
        </nav>
      </div>
    </footer>
  );
}
