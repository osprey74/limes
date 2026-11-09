# core

Rust workspace.

| Crate | Role | State |
| --- | --- | --- |
| `limes-core` | Speed decision (stages 1-7 with confidence), JARTIC condition evaluation (period, time, weekday, vehicle; target and exclusion blocks), prefecture SQLite (R*Tree) writer/reader, map matching, data updates (manifest, sha256, zstd, atomic switch with one rollback), golden cases | In progress |
| `limes-cli` | Pipeline front end: `decide`, `golden` (validation gate), `build-db` (evidence NDJSON to SQLite), `locate` (map-match test), `package` (`.sqlite.zst` and `manifest.json`), `tiles` (speed-line vector tiles, PMTiles) | In progress |
| `limes-ffi` | UniFFI bindings for Swift / Kotlin: `Engine.openDatabase`, `locate`, `closeDatabase`; updates: `openStore`, `planUpdates`, `installUpdate`, `rollBack`, `removePrefecture` | In progress |

The app fetches `manifest.json` and the `.sqlite.zst` files itself; `limes-core::update` verifies and installs them (see the module comment for the store layout and install order).

```sh
cargo test
cargo run -p limes-cli -- golden
cargo run --release -p limes-cli -- tiles --db pref.sqlite --out pref.pmtiles
echo '{"osm_id":1,"highway":"residential"}' | cargo run -q -p limes-cli -- decide --at 0610-0800-2

# Swift / Kotlin bindings
cargo build --release -p limes-ffi
cargo run --release -p limes-ffi --bin uniffi-bindgen -- generate --library target/release/limes_ffi.dll --language swift --out-dir target/bindings/swift
cargo run --release -p limes-ffi --bin uniffi-bindgen -- generate --library target/release/limes_ffi.dll --language kotlin --out-dir target/bindings/kotlin
```

(`limes_ffi.dll` on Windows, `liblimes_ffi.dylib` on macOS, `liblimes_ffi.so` on Linux.)

The decision cases in `limes-core/tests/golden/decide.json` are the reference for the stage order and the legal basis noted in `limes-core/src/decide.rs`.
