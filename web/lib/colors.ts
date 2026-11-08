// cmocean colormaps (Thyng et al. 2016), the oceanography community's perceptually uniform scales.
// Nine evenly spaced stops exported from the cmocean Python package.
export const CMOCEAN = {
  thermal: ["#042333", "#19337c", "#563b9c", "#83508f", "#b15f82", "#df7064", "#f99341", "#f9c641", "#e8fa5b"],
  haline: ["#2a186c", "#2034a2", "#0f5b90", "#297789", "#3c9387", "#50b07e", "#7acb67", "#c4dd65", "#fdef9a"],
  oxy: ["#400505", "#76050f", "#5c5b5b", "#7a7a79", "#9b9a9a", "#bebebd", "#e6e5e4", "#e9e032", "#ddaf19"],
  deep: ["#fdfecc", "#bbe6ac", "#78cea3", "#55aea3", "#488e9e", "#3f6e97", "#404c8b", "#3b315a", "#281a2c"],
} as const;

export type ColormapName = keyof typeof CMOCEAN;

function hexToRgb(hex: string): [number, number, number] {
  const n = parseInt(hex.slice(1), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

/** Colour at t in [0, 1] along a colormap (linear interpolation between stops). */
export function sample(name: ColormapName, t: number): string {
  const stops = CMOCEAN[name];
  const x = Math.min(1, Math.max(0, Number.isFinite(t) ? t : 0)) * (stops.length - 1);
  const i = Math.min(stops.length - 2, Math.floor(x));
  const f = x - i;
  const [a, b] = [hexToRgb(stops[i]), hexToRgb(stops[i + 1])];
  const mix = a.map((v, k) => Math.round(v + (b[k] - v) * f));
  return `rgb(${mix[0]}, ${mix[1]}, ${mix[2]})`;
}

/** A function mapping a value in [min, max] to a colour. */
export function scale(name: ColormapName, min: number, max: number) {
  return (value: number | null | undefined) => (value == null ? "var(--muted)" : sample(name, (value - min) / (max - min)));
}

/** Observable Plot colour options for a cmocean scale. */
export function plotScheme(name: ColormapName) {
  return { type: "linear" as const, range: [...CMOCEAN[name]], interpolate: "rgb" as const };
}
