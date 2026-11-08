# core

Rust workspace.

| Crate | Role | State |
| --- | --- | --- |
| `limes-core` | Speed decision (stages 1-7 with confidence), JARTIC condition evaluation (period, time, weekday, vehicle; target and exclusion blocks), golden cases | In progress |
| `limes-cli` | Pipeline front end: `decide` (NDJSON evidence in, decisions out) and `golden` (validation gate) | In progress |
| `limes-ffi` | UniFFI bindings for Swift / Kotlin | Not started |

Map matching, the per-prefecture SQLite reader and update management come next.

```sh
cargo test
cargo run -p limes-cli -- golden
echo '{"osm_id":1,"highway":"residential"}' | cargo run -q -p limes-cli -- decide --at 0610-0800-2
```

The decision cases in `limes-core/tests/golden/decide.json` are the reference for the stage order and the legal basis noted in `limes-core/src/decide.rs`.
