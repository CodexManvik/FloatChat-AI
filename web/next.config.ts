import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  output: "standalone", // a small self-contained server for the Docker image
  poweredByHeader: false,
};

export default nextConfig;
