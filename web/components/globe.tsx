"use client";

import { geoDistance, geoGraticule10, geoOrthographic, geoPath, type GeoPermissibleObjects } from "d3-geo";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { feature } from "topojson-client";
import type { GeometryCollection, Topology } from "topojson-specification";
import { CMOCEAN, sample } from "@/lib/colors";
import { formatDate, formatNumber } from "@/lib/format";
import type { FloatPoint } from "@/lib/types";

const CENTER: [number, number] = [76, -10]; // the Indian Ocean
const SWAY_DEG = 16;
const SWAY_PERIOD_MS = 18000;

type Hover = { float: FloatPoint; x: number; y: number } | null;

function tokens() {
  const css = getComputedStyle(document.documentElement);
  const v = (name: string) => css.getPropertyValue(name).trim();
  return { water: v("--water"), land: v("--land"), line: v("--line-strong"), graticule: v("--graticule"),
    accent: v("--accent"), surface: v("--surface") };
}

/** Temperature range for colouring: 5th to 95th percentile, so a few outliers don't flatten the scale. */
function tempDomain(floats: FloatPoint[]): [number, number] {
  const temps = floats.map((f) => f.surface_temperature).filter((t): t is number => t != null).sort((a, b) => a - b);
  if (!temps.length) return [0, 30];
  const at = (q: number) => temps[Math.min(temps.length - 1, Math.floor(q * temps.length))];
  return [Math.floor(at(0.05)), Math.ceil(at(0.95))];
}

export function Globe({ floats }: { floats: FloatPoint[] }) {
  const router = useRouter();
  const wrap = useRef<HTMLDivElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const [hover, setHover] = useState<Hover>(null);
  const domain = useMemo(() => tempDomain(floats), [floats]);

  useEffect(() => {
    const el = canvas.current!;
    const box = wrap.current!;
    const ctx = el.getContext("2d")!;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const projection = geoOrthographic().clipAngle(90).precision(0.5);
    const path = geoPath(projection, ctx);
    const graticule = geoGraticule10();
    let land: GeoPermissibleObjects | null = null;
    let colors = tokens();
    let size = 0;
    let dpr = 1;
    let base: [number, number] = [...CENTER];
    let lastInteraction = -Infinity;
    let dragging: { x: number; y: number; base: [number, number] } | null = null;
    let visible = true;
    let frame = 0;
    let hovered: FloatPoint | null = null;
    // Skip the near-black start of the thermal scale so cold floats stay visible on dark water
    const dotColor = floats.map((f) =>
      f.surface_temperature == null
        ? colors.line
        : sample("thermal", 0.14 + 0.86 * ((f.surface_temperature - domain[0]) / (domain[1] - domain[0]))),
    );

    import("world-atlas/land-110m.json").then((mod) => {
      const topo = (mod.default ?? mod) as unknown as Topology<{ land: GeometryCollection }>;
      land = feature(topo, topo.objects.land) as unknown as GeoPermissibleObjects;
    });

    function resize() {
      const rect = box.getBoundingClientRect();
      size = Math.max(200, Math.min(rect.width, 640));
      dpr = Math.min(2, window.devicePixelRatio || 1);
      el.width = size * dpr;
      el.height = size * dpr;
      el.style.width = `${size}px`;
      el.style.height = `${size}px`;
      projection.translate([(size * dpr) / 2, (size * dpr) / 2]).scale((size * dpr) / 2 - 4 * dpr);
    }

    function rotation(now: number): [number, number] {
      if (reduce || dragging) return base;
      // After someone drags, ease the gentle sway back in over three seconds
      const ease = Math.min(1, Math.max(0, (now - lastInteraction - 1500) / 3000));
      return [base[0] + Math.sin((now / SWAY_PERIOD_MS) * Math.PI * 2) * SWAY_DEG * ease, base[1]];
    }

    function draw(now: number) {
      const [lon, lat] = rotation(now);
      projection.rotate([-lon, -lat, 0]);
      const w = size * dpr;
      ctx.clearRect(0, 0, w, w);
      ctx.beginPath();
      path({ type: "Sphere" });
      ctx.fillStyle = colors.water;
      ctx.fill();
      ctx.beginPath();
      path(graticule);
      ctx.strokeStyle = colors.graticule;
      ctx.lineWidth = dpr;
      ctx.stroke();
      if (land) {
        ctx.beginPath();
        path(land);
        ctx.fillStyle = colors.land;
        ctx.fill();
      }
      const center: [number, number] = [lon, lat];
      const r = 2.4 * dpr;
      floats.forEach((f, i) => {
        if (geoDistance([f.lon, f.lat], center) > Math.PI / 2 - 0.02) return;
        const p = projection([f.lon, f.lat]);
        if (!p) return;
        ctx.beginPath();
        ctx.arc(p[0], p[1], f === hovered ? r * 1.9 : r, 0, Math.PI * 2);
        ctx.fillStyle = dotColor[i];
        ctx.fill();
        ctx.lineWidth = 0.75 * dpr;
        ctx.strokeStyle = colors.line;
        ctx.stroke();
        if (f === hovered) {
          ctx.lineWidth = 2 * dpr;
          ctx.strokeStyle = colors.accent;
          ctx.stroke();
        }
      });
      ctx.beginPath();
      path({ type: "Sphere" });
      ctx.strokeStyle = colors.line;
      ctx.lineWidth = dpr;
      ctx.stroke();
    }

    function loop(now: number) {
      if (visible) draw(now);
      frame = requestAnimationFrame(loop);
    }

    function nearest(clientX: number, clientY: number): Hover {
      const rect = el.getBoundingClientRect();
      const x = (clientX - rect.left) * dpr;
      const y = (clientY - rect.top) * dpr;
      const [lon, lat] = rotation(performance.now());
      let best: { f: FloatPoint; d: number; p: [number, number] } | null = null;
      for (const f of floats) {
        if (geoDistance([f.lon, f.lat], [lon, lat]) > Math.PI / 2 - 0.02) continue;
        const p = projection([f.lon, f.lat]);
        if (!p) continue;
        const d = Math.hypot(p[0] - x, p[1] - y);
        if (d < 12 * dpr && (!best || d < best.d)) best = { f, d, p: p as [number, number] };
      }
      return best ? { float: best.f, x: best.p[0] / dpr, y: best.p[1] / dpr } : null;
    }

    function onDown(e: PointerEvent) {
      dragging = { x: e.clientX, y: e.clientY, base: [...rotation(performance.now())] };
      base = dragging.base;
      el.setPointerCapture(e.pointerId);
    }
    function onMove(e: PointerEvent) {
      if (dragging) {
        const k = 180 / size;
        base = [dragging.base[0] - (e.clientX - dragging.x) * k * 0.6,
          Math.max(-60, Math.min(60, dragging.base[1] + (e.clientY - dragging.y) * k * 0.6))];
        lastInteraction = performance.now();
        hovered = null;
        setHover(null);
        return;
      }
      const hit = nearest(e.clientX, e.clientY);
      hovered = hit?.float ?? null;
      el.style.cursor = hit ? "pointer" : "grab";
      setHover(hit);
    }
    function onUp(e: PointerEvent) {
      const moved = dragging && Math.hypot(e.clientX - dragging.x, e.clientY - dragging.y) > 4;
      dragging = null;
      lastInteraction = performance.now();
      if (!moved) {
        const hit = nearest(e.clientX, e.clientY);
        if (hit) router.push(`/floats/${hit.float.float_id}`);
      }
    }
    function onLeave() {
      hovered = null;
      setHover(null);
    }

    resize();
    const resizeObserver = new ResizeObserver(resize);
    resizeObserver.observe(box);
    const io = new IntersectionObserver(([entry]) => (visible = entry.isIntersecting));
    io.observe(el);
    const themeObserver = new MutationObserver(() => (colors = tokens()));
    themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const onScheme = () => (colors = tokens());
    media.addEventListener("change", onScheme);
    el.addEventListener("pointerdown", onDown);
    el.addEventListener("pointermove", onMove);
    el.addEventListener("pointerup", onUp);
    el.addEventListener("pointerleave", onLeave);
    frame = requestAnimationFrame(loop);

    return () => {
      cancelAnimationFrame(frame);
      resizeObserver.disconnect();
      io.disconnect();
      themeObserver.disconnect();
      media.removeEventListener("change", onScheme);
      el.removeEventListener("pointerdown", onDown);
      el.removeEventListener("pointermove", onMove);
      el.removeEventListener("pointerup", onUp);
      el.removeEventListener("pointerleave", onLeave);
    };
  }, [floats, domain, router]);

  return (
    <figure className="relative mx-auto w-full max-w-[640px]">
      <div ref={wrap} className="relative aspect-square w-full touch-none select-none">
        <canvas
          ref={canvas}
          role="img"
          aria-label={`Globe of the Indian Ocean showing ${floats.length} Argo floats coloured by surface temperature. Drag to turn it; select a float to open its page.`}
          className="absolute inset-0 m-auto cursor-grab"
        />
        {hover && (
          <div
            className="pointer-events-none absolute z-10 w-max -translate-x-1/2 -translate-y-[calc(100%+14px)] rounded-xl border border-line bg-surface px-3 py-2 text-xs shadow-card"
            style={{ left: hover.x, top: hover.y }}
          >
            <div className="font-medium text-ink">Float {hover.float.float_id}</div>
            <div className="tabular mt-0.5 text-ink-2">
              {hover.float.region}
              <br />
              {formatNumber(hover.float.surface_temperature, 1)} °C at the surface, {formatDate(hover.float.last_profile)}
            </div>
          </div>
        )}
      </div>
      <figcaption className="mt-3 flex flex-wrap items-center justify-center gap-x-3 gap-y-1 whitespace-nowrap text-xs text-ink-2">
        <span className="tabular font-mono">{domain[0]} °C</span>
        <span
          className="h-1.5 w-24 rounded-full sm:w-40"
          style={{ background: `linear-gradient(90deg, ${CMOCEAN.thermal.slice(1).join(",")})` }}
          aria-hidden
        />
        <span className="tabular font-mono">{domain[1]} °C</span>
        <span className="text-muted">surface temperature</span>
      </figcaption>
    </figure>
  );
}
