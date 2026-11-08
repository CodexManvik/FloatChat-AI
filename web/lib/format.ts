const integer = new Intl.NumberFormat("en-US");

export function formatInt(n: number | null | undefined): string {
  return n == null ? "n/a" : integer.format(Math.round(n));
}

export function formatNumber(n: number | null | undefined, digits = 2): string {
  return n == null || !Number.isFinite(n) ? "n/a" : n.toFixed(digits);
}

/** "8 Nov 2026" from an ISO-ish timestamp ("2026-11-08T04:50:20.000"). */
export function formatDate(value: string | null | undefined): string {
  if (!value) return "n/a";
  const d = new Date(value.endsWith("Z") || value.includes("+") ? value : `${value}Z`);
  return d.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
}

export function formatPosition(lat: number, lon: number): string {
  return `${Math.abs(lat).toFixed(2)}°${lat >= 0 ? "N" : "S"}, ${Math.abs(lon).toFixed(2)}°${lon >= 0 ? "E" : "W"}`;
}

export function formatMs(ms: number | null | undefined): string {
  if (ms == null) return "";
  return ms < 1000 ? `${Math.round(ms)} ms` : `${(ms / 1000).toFixed(1)} s`;
}

export function parseDate(value: string): Date {
  return new Date(value.endsWith("Z") || value.includes("+") ? value : `${value}Z`);
}
