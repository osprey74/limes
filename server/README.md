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

## Counts

Read them in the Cloudflare dashboard (Storage & Databases → D1 → limes-trial → Console):

```sql
SELECT platform, COUNT(*) FROM installs GROUP BY platform;
```

## Limits

On the Workers Free plan: 100,000 requests and 100,000 D1 rows written per day, 5 GB stored. Each install makes one request and writes at most one row, so the daily limit is about 100,000 new installs. If a limit is hit, the app starts the trial from its own clock.
