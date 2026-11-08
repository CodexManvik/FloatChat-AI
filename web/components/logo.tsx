/** The mark: a float at the sea surface (a circle cut by the waterline). */
export function Logo({ size = 22 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="12" cy="12" r="10.5" fill="none" stroke="currentColor" strokeOpacity="0.25" />
      <path d="M1.5 12a10.5 10.5 0 0 0 21 0z" fill="var(--accent)" />
      <circle cx="12" cy="7.5" r="2" fill="currentColor" />
    </svg>
  );
}
