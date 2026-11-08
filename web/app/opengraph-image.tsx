import { ImageResponse } from "next/og";
import { CMOCEAN } from "@/lib/colors";

export const alt = "FloatChat: ask the Indian Ocean anything";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

/** The social preview card shown when the site is shared. */
export default function OpengraphImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          padding: 72,
          background: "#0d0e10",
          color: "#ecedee",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 18, fontSize: 34, fontWeight: 600 }}>
          <div style={{ width: 44, height: 44, borderRadius: 44, background: "linear-gradient(180deg, #ecedee22 50%, #ff5b1f 50%)", border: "1px solid #ecedee44" }} />
          FloatChat
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
          <div style={{ fontSize: 84, fontWeight: 600, letterSpacing: -3, lineHeight: 1.02 }}>Ask the Indian Ocean anything.</div>
          <div style={{ fontSize: 32, color: "#a5aab2" }}>
            A year of real Argo float data. Plain-English questions, live SQL and search, every step shown.
          </div>
        </div>
        <div style={{ display: "flex", height: 10, borderRadius: 10, background: `linear-gradient(90deg, ${CMOCEAN.thermal.slice(1).join(",")})` }} />
      </div>
    ),
    size,
  );
}
