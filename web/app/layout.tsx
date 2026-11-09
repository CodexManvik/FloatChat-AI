import type { Metadata, Viewport } from "next";
import { GeistMono } from "geist/font/mono";
import { GeistSans } from "geist/font/sans";
import { SiteHeader } from "@/components/site-header";
import { SITE_URL } from "@/lib/config";
import "./globals.css";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: { default: "FloatChat: ask the Indian Ocean", template: "%s · FloatChat" },
  description:
    "Ask questions about a year of real Argo ocean-float data in plain English. FloatChat writes the SQL or searches " +
    "the profiles, shows every step, and draws the charts.",
  openGraph: { title: "FloatChat", description: "Ask the Indian Ocean in plain English.", type: "website" },
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f3f4f2" },
    { media: "(prefers-color-scheme: dark)", color: "#0d0e10" },
  ],
};

// Applies a saved theme before first paint so there is no flash of the wrong theme
const themeScript = `try{var t=localStorage.getItem("theme");if(t==="light"||t==="dark")document.documentElement.dataset.theme=t}catch(e){}`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${GeistSans.variable} ${GeistMono.variable}`} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body className="min-h-[100dvh] flex flex-col">
        <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-3 focus:z-50 focus:rounded-full focus:bg-surface focus:px-4 focus:py-2">
          Skip to content
        </a>
        <SiteHeader />
        <main id="main" className="flex-1">
          {children}
        </main>
      </body>
    </html>
  );
}
