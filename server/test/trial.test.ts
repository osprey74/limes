import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { DatabaseSync } from "node:sqlite";
import { test } from "node:test";

import { type D1Database, type D1PreparedStatement, type Env, handle } from "../src/index.ts";

// D1 stand-in over SQLite, enough for prepare/bind/batch.
class Statement implements D1PreparedStatement {
  sql: string;
  values: unknown[] = [];
  constructor(sql: string) {
    this.sql = sql;
  }
  bind(...values: unknown[]): D1PreparedStatement {
    this.values = values;
    return this;
  }
}

function fakeDb(): D1Database {
  const db = new DatabaseSync(":memory:");
  db.exec(readFileSync(new URL("../schema.sql", import.meta.url), "utf8"));
  return {
    prepare: (sql) => new Statement(sql),
    batch: async (statements) =>
      statements.map((s) => {
        const { sql, values } = s as Statement;
        const stmt = db.prepare(sql.replace(/\?(\d)/g, "?"));
        return { results: sql.startsWith("SELECT") ? stmt.all(...(values as never[])) : (stmt.run(...(values as never[])), []) };
      }),
  };
}

const ID = "a".repeat(64);

function post(body: unknown, path = "/v1/trial"): Request {
  return new Request(`https://trial.example${path}`, { method: "POST", body: JSON.stringify(body) });
}

test("first request starts the trial; a reinstall gets the same start back", async () => {
  const env: Env = { DB: fakeDb(), TRIAL_DAYS: "14" };
  const first = await handle(post({ id: ID, platform: "android" }), env, new Date("2026-11-11T00:00:00Z"));
  assert.equal(first.status, 200);
  assert.deepEqual(await first.json(), {
    first_seen: "2026-11-11T00:00:00.000Z",
    trial_ends: "2026-11-25T00:00:00.000Z",
  });

  const again = await handle(post({ id: ID, platform: "android" }), env, new Date("2026-12-01T00:00:00Z"));
  assert.deepEqual(await again.json(), {
    first_seen: "2026-11-11T00:00:00.000Z",
    trial_ends: "2026-11-25T00:00:00.000Z",
  });
});

test("bad requests are refused", async () => {
  const env: Env = { DB: fakeDb(), TRIAL_DAYS: "14" };
  const now = new Date();
  assert.equal((await handle(post({ id: "xyz", platform: "android" }), env, now)).status, 400);
  assert.equal((await handle(post({ id: ID.toUpperCase(), platform: "ios" }), env, now)).status, 400);
  assert.equal((await handle(post({ id: ID, platform: "web" }), env, now)).status, 400);
  assert.equal((await handle(post({ id: ID, platform: "ios" }, "/other"), env, now)).status, 404);
  const get = new Request("https://trial.example/v1/trial");
  assert.equal((await handle(get, env, now)).status, 405);
  const notJson = new Request("https://trial.example/v1/trial", { method: "POST", body: "{" });
  assert.equal((await handle(notJson, env, now)).status, 400);
});
