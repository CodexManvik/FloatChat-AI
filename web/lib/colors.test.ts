import { describe, expect, it } from "vitest";
import { sample, scale } from "./colors";

describe("cmocean sampling", () => {
  it("returns the end stops and interpolates between them", () => {
    expect(sample("thermal", 0)).toBe("rgb(4, 35, 51)");
    expect(sample("thermal", 1)).toBe("rgb(232, 250, 91)");
    expect(sample("thermal", 1 / 16)).toBe("rgb(15, 43, 88)"); // halfway between the first two stops
  });

  it("clamps out-of-range and non-finite values", () => {
    expect(sample("haline", -3)).toBe(sample("haline", 0));
    expect(sample("haline", 9)).toBe(sample("haline", 1));
    expect(sample("haline", Number.NaN)).toBe(sample("haline", 0));
  });

  it("scales values and uses a neutral colour for missing data", () => {
    const temp = scale("thermal", 0, 30);
    expect(temp(30)).toBe(sample("thermal", 1));
    expect(temp(null)).toBe("var(--muted)");
  });
});
