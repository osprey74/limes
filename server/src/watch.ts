// Daily watch on the data release, run from outside GitHub.
//
// GitHub turns the scheduled runs of a public repository off after 60 days
// without repository activity, and nothing inside GitHub then says so. Once a
// day this looks at the workflow from here and opens an issue when
//
//   - the workflow is not active,
//   - its last scheduled run is more than LATE_DAYS old, or
//   - the published manifest.json cannot be fetched (server down, certificate expired).
//
// One open issue at a time: while it is open, nothing more is posted. To
// resume a workflow that was turned off: Actions -> data-release -> Enable
// workflow, or `gh workflow enable data-release.yml`.

export interface WatchEnv {
  /** Fine-grained token for the repository: Issues read & write, Actions read. */
  GITHUB_TOKEN?: string;
  /** owner/name */
  WATCH_REPO: string;
  /** The workflow's file name. */
  WATCH_WORKFLOW: string;
  /** The manifest.json the apps read. */
  WATCH_MANIFEST_URL: string;
}

export type Fetch = (url: string, init?: RequestInit) => Promise<Response>;

export const ISSUE_TITLE = "Data release: not running or not reachable";
/** The schedule is daily and starts hours late on some days. */
const LATE_DAYS = 3;
const DAY_MS = 24 * 60 * 60 * 1000;
const API = "https://api.github.com";
const AGENT = "limes-watch (+https://github.com/osprey74/limes)";

/** What is wrong, one line each; empty when all is well. Throws when GitHub can't be asked. */
export async function problems(env: WatchEnv, now: Date, fetch: Fetch): Promise<string[]> {
  const found: string[] = [];
  const workflow = `${API}/repos/${env.WATCH_REPO}/actions/workflows/${env.WATCH_WORKFLOW}`;

  const { state } = (await github(fetch, env, workflow)) as { state: string };
  if (state !== "active") {
    found.push(`The workflow \`${env.WATCH_WORKFLOW}\` is not active (state: \`${state}\`). Scheduled runs are off.`);
  }

  const { workflow_runs: runs } = (await github(fetch, env, `${workflow}/runs?event=schedule&per_page=1`)) as {
    workflow_runs: { created_at: string }[];
  };
  const last = runs[0]?.created_at;
  if (last === undefined) {
    found.push("The workflow has no scheduled run.");
  } else if (now.getTime() - Date.parse(last) > LATE_DAYS * DAY_MS) {
    found.push(`The last scheduled run started at ${last}, more than ${LATE_DAYS} days ago.`);
  }

  const manifest = await reach(fetch, env.WATCH_MANIFEST_URL);
  if (manifest !== null) found.push(`${env.WATCH_MANIFEST_URL} could not be fetched (${manifest}).`);
  return found;
}

/** Looks, and opens the issue when something is wrong and none is open. Returns what it did. */
export async function watch(env: WatchEnv, now: Date, fetch: Fetch): Promise<string> {
  if (!env.GITHUB_TOKEN) throw new Error("GITHUB_TOKEN is not set");
  const found = await problems(env, now, fetch);
  if (found.length === 0) return "ok";

  const issues = `${API}/repos/${env.WATCH_REPO}/issues`;
  const open = (await github(fetch, env, `${issues}?state=open&per_page=100`)) as { title: string; number: number }[];
  const already = open.find((issue) => issue.title === ISSUE_TITLE);
  if (already) return `still wrong, #${already.number} is open: ${found.join(" ")}`;

  const body = [
    `Checked at ${now.toISOString()} by the watch in \`server/\`:`,
    "",
    ...found.map((line) => `- ${line}`),
    "",
    `If the workflow was turned off: Actions → data-release → Enable workflow, or \`gh workflow enable ${env.WATCH_WORKFLOW}\`. ` +
      "The next run picks up the current release.",
    "",
    "Nothing more is posted while this issue is open. Close it once the release runs again.",
  ].join("\n");
  const created = (await github(fetch, env, issues, { title: ISSUE_TITLE, body })) as { number: number };
  return `opened #${created.number}: ${found.join(" ")}`;
}

/** A GitHub API call: GET, or POST when there is a body. */
async function github(fetch: Fetch, env: WatchEnv, url: string, body?: unknown): Promise<unknown> {
  const headers: Record<string, string> = {
    accept: "application/vnd.github+json",
    "user-agent": AGENT,
    "x-github-api-version": "2022-11-28",
  };
  if (env.GITHUB_TOKEN) headers.authorization = `Bearer ${env.GITHUB_TOKEN}`;
  const response = await fetch(url, {
    method: body === undefined ? "GET" : "POST",
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) throw new Error(`GitHub answered ${response.status} for ${new URL(url).pathname}`);
  return response.json();
}

/** null when the URL answers 200 (at the second try at the latest), otherwise why not. */
async function reach(fetch: Fetch, url: string): Promise<string | null> {
  let why = "";
  for (let attempt = 0; attempt < 2; attempt++) {
    try {
      const response = await fetch(url, { headers: { "user-agent": AGENT } });
      if (response.status === 200) return null;
      why = `status ${response.status}`;
    } catch (error) {
      why = error instanceof Error ? error.message : "no answer";
    }
  }
  return why;
}
