"use client";

import { useEffect, useRef } from "react";

/**
 * Renders an Observable Plot chart and re-renders it when its container width changes.
 * `render(width)` must return the element from Plot.plot (or null to render nothing).
 */
export function PlotFigure({
  render,
  className = "",
  label,
}: {
  render: (width: number) => (HTMLElement | SVGSVGElement) | null;
  className?: string;
  label: string;
}) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current!;
    let lastWidth = 0;
    const draw = () => {
      const width = Math.floor(el.getBoundingClientRect().width);
      if (!width || width === lastWidth) return;
      lastWidth = width;
      const chart = render(width);
      el.replaceChildren(...(chart ? [chart] : []));
    };
    draw();
    const observer = new ResizeObserver(draw);
    observer.observe(el);
    return () => observer.disconnect();
  }, [render]);

  return <div ref={ref} role="figure" aria-label={label} className={`plot-frame w-full ${className}`} />;
}
