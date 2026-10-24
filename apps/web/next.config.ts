import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */
  experimental: {
    // Cap the static-generation worker pool. On low-memory machines (this
    // app is developed on a 16 GB box that often has <2 GB free) the default
    // pool of cpu_count-1 workers exhausts the V8 heap and crashes the build
    // (exit 134 / 0xC0000409 during "Collecting page data"). Two workers
    // build this 16-route app in a few seconds and never OOM.
    cpus: 2,
  },
};

export default nextConfig;
