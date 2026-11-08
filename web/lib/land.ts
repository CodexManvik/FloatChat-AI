import type { FeatureCollection } from "geojson";
import { feature } from "topojson-client";
import type { GeometryCollection, Topology } from "topojson-specification";

let cached: Promise<FeatureCollection> | null = null;

/** Natural Earth land outlines (1:110m), loaded once on demand. */
export function loadLand(): Promise<FeatureCollection> {
  cached ??= import("world-atlas/land-110m.json").then((mod) => {
    const topo = (mod.default ?? mod) as unknown as Topology<{ land: GeometryCollection }>;
    return feature(topo, topo.objects.land) as unknown as FeatureCollection;
  });
  return cached;
}
