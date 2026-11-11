// Free-trial ledger for the Limes apps.
//
// The app sends a hash of a reinstall-stable device ID at its first data
// download; the first time a hash is seen starts its free trial. A reinstall
// gets the same start back, so the trial cannot be restarted.
//
//   POST /v1/trial  {"id": "<64 hex>", "platform": "android" | "ios"}
//   200             {"first_seen": "<ISO 8601>", "trial_ends": "<ISO 8601>"}
//
// Counts are read in the Cloudflare dashboard (D1 console), not served here.

export interface Env {
  DB: D1Database;
  TRIAL_DAYS: string;
}

// The subset of the D1 API used here, so tests can stand in for it.
export interface D1Database {
  prepare(query: string): D1PreparedStatement;
  batch(statements: D1PreparedStatement[]): Promise<{ results: unknown[] }[]>;
}
export interface D1PreparedStatement {
  bind(...values: unknown[]): D1PreparedStatement;
}

const ID = /^[0-9a-f]{64}$/;
const PLATFORMS = new Set(["android", "ios"]);
const DAY_MS = 24 * 60 * 60 * 1000;

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    return handle(request, env, new Date());
  },
};

export async function handle(request: Request, env: Env, now: Date): Promise<Response> {
  const url = new URL(request.url);
  if (url.pathname !== "/v1/trial") return json({ error: "not found" }, 404);
  if (request.method !== "POST") return json({ error: "method not allowed" }, 405);

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return json({ error: "body must be JSON" }, 400);
  }
  const { id, platform } = (body ?? {}) as { id?: unknown; platform?: unknown };
  if (typeof id !== "string" || !ID.test(id)) return json({ error: "id must be 64 lowercase hex" }, 400);
  if (typeof platform !== "string" || !PLATFORMS.has(platform)) {
    return json({ error: "platform must be android or ios" }, 400);
  }

  // Insert only when new, then read back whichever start is stored.
  const [, read] = await env.DB.batch([
    env.DB.prepare("INSERT INTO installs (id, platform, first_seen) VALUES (?1, ?2, ?3) ON CONFLICT (id) DO NOTHING")
      .bind(id, platform, now.toISOString()),
    env.DB.prepare("SELECT first_seen FROM installs WHERE id = ?1").bind(id),
  ]);
  const firstSeen = (read.results[0] as { first_seen: string }).first_seen;
  const days = Number(env.TRIAL_DAYS) || 14;
  const trialEnds = new Date(Date.parse(firstSeen) + days * DAY_MS).toISOString();
  return json({ first_seen: firstSeen, trial_ends: trialEnds }, 200);
}

function json(value: unknown, status: number): Response {
  return new Response(JSON.stringify(value), {
    status,
    headers: { "content-type": "application/json; charset=utf-8" },
  });
}
