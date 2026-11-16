# server — free-trial ledger

A Cloudflare Worker with a D1 database that remembers when each device started its free trial, so reinstalling the app does not start a new one.

The app sends, at its first data download, the SHA-256 of a reinstall-stable ID (Android: `ANDROID_ID`, which keeps its value across reinstalls of an app signed with the same key; iOS: an ID kept in the keychain). The first time a hash is seen starts its trial.

```text
POST /v1/trial   {"id": "<64 lowercase hex>", "platform": "android" | "ios"}
200              {"first_seen": "2026-11-11T00:00:00.000Z", "trial_ends": "2026-11-25T00:00:00.000Z"}
```

Only the hash, the platform and the first-seen time are stored (`schema.sql`). The trial length is `TRIAL_DAYS` in `wrangler.toml`.

## Commands

```sh
cd server
npm install
npm test                      # Node 24's test runner, D1 stood in by node:sqlite
npx wrangler deploy --dry-run # bundle without uploading
```

## Setup (once)

```sh
npx wrangler login
npx wrangler d1 create limes-trial          # put the printed database_id in wrangler.toml
npx wrangler d1 execute limes-trial --remote --file schema.sql
npx wrangler deploy                         # prints https://limes-trial.<account>.workers.dev
```

## Watch on the data release

The same Worker looks at the data release once a day (cron in `wrangler.toml`, 12:00 JST; `src/watch.ts`), because GitHub turns the scheduled runs of a public repository off after 60 days without repository activity and nothing inside GitHub then says so. It opens the issue "Data release: not running or not reachable" when

- the `data-release` workflow is not active,
- its last scheduled run is more than 3 days old, or
- `https://limes.osprey74.com/data/manifest.json` cannot be fetched (server down, certificate expired).

While that issue is open, nothing more is posted. To resume a workflow that was turned off: Actions → data-release → Enable workflow, or `gh workflow enable data-release.yml`.

It needs the secret `GITHUB_TOKEN`: a fine-grained personal access token for this repository only, with Issues (read and write) and Actions (read).

```sh
npx wrangler secret put GITHUB_TOKEN   # asks for the value
```

If the token is missing, has expired, or GitHub does not answer, the run fails and shows in the Worker's logs (Cloudflare dashboard → Workers & Pages → limes-trial → Logs); no issue is opened. If the token has an expiry date, replace it before then.

To run the watch once by hand: `npx wrangler dev --remote --test-scheduled`, then `curl "http://localhost:8787/__scheduled"`; the result (`ok`, or what it found) is printed by `wrangler dev`.

## Counts

Read them in the Cloudflare dashboard (Storage & Databases → D1 → limes-trial → Console):

```sql
SELECT platform, COUNT(*) FROM installs GROUP BY platform;
```

## Limits

On the Workers Free plan: 100,000 requests and 100,000 D1 rows written per day, 5 GB stored. Each install makes one request and writes at most one row, so the daily limit is about 100,000 new installs. If a limit is hit, the app starts the trial from its own clock.
