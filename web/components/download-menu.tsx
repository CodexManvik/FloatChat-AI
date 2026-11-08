"use client";

import { DownloadSimple } from "@phosphor-icons/react";
import { useState } from "react";
import { downloadProfiles, type ExportFormat } from "@/lib/client-api";

const FORMATS: { format: ExportFormat; label: string }[] = [
  { format: "csv", label: "CSV" },
  { format: "netcdf", label: "NetCDF" },
  { format: "ascii", label: "ASCII" },
];

/** Download buttons for a set of profiles (CSV, NetCDF, ASCII). */
export function DownloadMenu({ profileIds, name, note }: { profileIds: number[]; name: string; note?: string }) {
  const [busy, setBusy] = useState<ExportFormat | null>(null);
  const [error, setError] = useState(false);
  if (!profileIds.length) return null;
  return (
    <div className="flex flex-wrap items-center gap-2 text-sm">
      <span className="inline-flex items-center gap-1.5 text-ink-2">
        <DownloadSimple size={15} aria-hidden /> Download {note ?? `${Math.min(profileIds.length, 50)} profiles`}
      </span>
      {FORMATS.map(({ format, label }) => (
        <button
          key={format}
          type="button"
          disabled={busy !== null}
          onClick={async () => {
            setBusy(format);
            setError(false);
            try {
              await downloadProfiles(profileIds, format, name);
            } catch {
              setError(true);
            } finally {
              setBusy(null);
            }
          }}
          className="rounded-full border border-line px-3 py-1 text-ink-2 transition-colors hover:border-line-strong hover:text-ink disabled:opacity-50"
        >
          {busy === format ? "Preparing" : label}
        </button>
      ))}
      {error && <span className="text-warn" role="alert">The download failed; try again.</span>}
    </div>
  );
}
