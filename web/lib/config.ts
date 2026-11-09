/** The API as the visitor's browser reaches it (inlined at build time). */
export const API_URL = (process.env.NEXT_PUBLIC_API_URL || "https://floatchat-ai-svjw.onrender.com").replace(/\/$/, "");

/**
 * The API as the Next.js server reaches it. Usually the same; in Docker Compose the server talks to the
 * `backend` container while browsers use localhost.
 */
export const SERVER_API_URL = (process.env.API_URL_INTERNAL || API_URL).replace(/\/$/, "");

/** The public address of this site, used for absolute links such as the social preview image. */
export const SITE_URL = (process.env.NEXT_PUBLIC_SITE_URL || "https://float-chat-ai-teal.vercel.app").replace(/\/$/, "");

export const REPO_URL = "https://github.com/CodexManvik/FloatChat-AI";
export const BENCHMARK_URL = "https://raw.githubusercontent.com/CodexManvik/FloatChat-AI/main/eval/latest.json";
export const BENCHMARK_TABLE_URL = `${REPO_URL}/blob/main/eval/latest.md`;
