import assert from "node:assert/strict";
import { test } from "node:test";

import { type Fetch, ISSUE_TITLE, type WatchEnv, watch } from "../src/watch.ts";

const env: WatchEnv = {
  GITHUB_TOKEN: "t",
  WATCH_REPO: "o/r",
  WATCH_WORKFLOW: "data-release.yml",
  WATCH_MANIFEST_URL: "https://data.example/manifest.json",
};
const now = new Date("2026-12-10T03:00:00Z");

interface World {
  state?: string;
  lastRun?: string | null;
  manifest?: number | "throws";
  openIssues?: { title: string; number: number }[];
  api?: number;
}

/** GitHub and the data server as `world` describes them; `posted` collects the issues opened. */
function fake(world: World, posted: { title: string; body: string }[] = []): Fetch {
  const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status });
  return async (url, init) => {
    if (url === env.WATCH_MANIFEST_URL) {
      if (world.manifest === "throws") throw new Error("certificate has expired");
      return new Response("{}", { status: world.manifest ?? 200 });
    }
    assert.equal((init?.headers as Record<string, string>).authorization, "Bearer t");
    if (world.api) return json({ message: "no" }, world.api);
    const path = url.replace("https://api.github.com/repos/o/r", "");
    if (path === "/actions/workflows/data-release.yml") return json({ state: world.state ?? "active" });
    if (path === "/actions/workflows/data-release.yml/runs?event=schedule&per_page=1") {
      const last = world.lastRun === undefined ? "2026-12-09T01:30:00Z" : world.lastRun;
      return json({ workflow_runs: last === null ? [] : [{ created_at: last }] });
    }
    if (path === "/issues?state=open&per_page=100") return json(world.openIssues ?? []);
    if (path === "/issues" && init?.method === "POST") {
      posted.push(JSON.parse(init.body as string));
      return json({ number: 7 }, 201);
    }
    throw new Error(`unexpected request: ${init?.method} ${url}`);
  };
}

test("all well: nothing is posted", async () => {
  const posted: { title: string; body: string }[] = [];
  assert.equal(await watch(env, now, fake({}, posted)), "ok");
  assert.equal(posted.length, 0);
});

test("a run that started late but within three days is fine", async () => {
  assert.equal(await watch(env, now, fake({ lastRun: "2026-12-07T03:00:01Z" })), "ok");
});

test("a workflow turned off opens one issue that says how to resume", async () => {
  const posted: { title: string; body: string }[] = [];
  const result = await watch(env, now, fake({ state: "disabled_inactivity", lastRun: "2026-12-01T01:30:00Z" }, posted));
  assert.match(result, /^opened #7/);
  assert.equal(posted.length, 1);
  assert.equal(posted[0].title, ISSUE_TITLE);
  assert.match(posted[0].body, /state: `disabled_inactivity`/);
  assert.match(posted[0].body, /2026-12-01T01:30:00Z, more than 3 days ago/);
  assert.match(posted[0].body, /gh workflow enable data-release\.yml/);
});

test("no scheduled run at all is reported", async () => {
  const posted: { title: string; body: string }[] = [];
  await watch(env, now, fake({ lastRun: null }, posted));
  assert.match(posted[0].body, /no scheduled run/);
});

test("a manifest that can't be fetched is reported, by status or by error", async () => {
  const posted: { title: string; body: string }[] = [];
  await watch(env, now, fake({ manifest: 404 }, posted));
  assert.match(posted[0].body, /manifest\.json could not be fetched \(status 404\)/);
  await watch(env, now, fake({ manifest: "throws" }, posted));
  assert.match(posted[1].body, /certificate has expired/);
});

test("while the issue is open, nothing more is posted", async () => {
  const posted: { title: string; body: string }[] = [];
  const world = { state: "disabled_inactivity", openIssues: [{ title: "other", number: 3 }, { title: ISSUE_TITLE, number: 5 }] };
  assert.match(await watch(env, now, fake(world, posted)), /^still wrong, #5 is open/);
  assert.equal(posted.length, 0);
});

test("GitHub not answering, or no token, fails the run instead of reporting", async () => {
  await assert.rejects(watch(env, now, fake({ api: 403 })), /GitHub answered 403/);
  await assert.rejects(watch({ ...env, GITHUB_TOKEN: undefined }, now, fake({})), /GITHUB_TOKEN is not set/);
});
