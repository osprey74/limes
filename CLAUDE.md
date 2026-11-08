# CLAUDE.md

Limes（リメス）：走行中の道路の最高速度（規制速度または法定速度）を公開データから推定し、GPS速度と並べて表示する日本国内向けアプリ（iOS／Android同時リリース）。

## 構成（モノレポ）

| パス | 内容 | 状態 |
| --- | --- | --- |
| `core/` | Rustワークスペース。`limes-core`（判定・マップマッチ・DB読込・更新管理）、`limes-ffi`（UniFFI）、`limes-cli`（パイプライン用判定） | 未着手 |
| `ios/` | Swift / SwiftUI、MapLibre Native、StoreKit 2 | 未着手 |
| `android/` | Kotlin / Jetpack Compose、MapLibre Native、Play Billing | 未着手 |
| `data-pipeline/` | Python（uv）。JARTIC取得・集計、のちにOSM・国土地理院データ結合 | Phase 0 |
| `docs/phase0/` | データ検証レポートと所見 | — |

## 設計上の決定（要点）

- 判定ロジックはRustの `limes-core` に一元化し、アプリ（UniFFI経由）とパイプライン（`limes-cli`）の両方から使う。Swift／Kotlin／Pythonで判定を再実装しない
- 判定は上から順に評価：規制速度 → 高速自動車国道 → 自動車専用道路 → 中央分離帯 → 中央線・車両通行帯の証拠 → 農道等 → 生活道路(30) → 不明。速度と信頼度（high/mid/low）を必ずセットで出す
- 信頼度lowで60を表示しない。道路幅員だけを根拠に60と判定しない
- 判定不能時は数値を出さず「不明」
- 速度超過の警告・表示は実装しない
- 走行中に速度マップを開くと確認ダイアログ（［走行画面に戻る］／［同乗者が操作する］）
- データは毎日 `opendata.json` で更新を検知し、自動ビルド → 検証ゲート → R2配信（manifest.json）→ アプリ起動時に差分取得
- 地図はMapLibre Native。速度線はパイプラインでベクタータイル化して重ねる

## データの注意点（Phase 0で判明）

- JARTIC CSVはcp932、170項目。列番号は仕様書の項目NO（1始まり）で `limes_pipeline/jartic.py` の `Col` に定義
- 北海道は中央線(15)が0件、道路種別コード・路線名は空欄。詳細は `docs/phase0/findings.md`
- バージョン「K_2.1注」の県はユニークキーに継続性がないため、差分ではなく毎月全件再生成
- 生データ（`data-pipeline/data/`、`*.csv`、`*.zip`）はコミットしない

## 出典表記（必須）

JARTIC由来のデータ・レポートには「出典：『交通規制情報』（公益財団法人日本道路交通情報センター）（https://www.jartic.or.jp/service/opendata/）を加工して作成」を入れる。OSMはODbL帰属表示、国土地理院は出典明記。

## コマンド

```sh
cd data-pipeline
uv sync
uv run pytest
uv run python scripts/fetch_jartic.py hokkaido --out-dir data/raw
uv run python scripts/inspect_jartic.py data/raw/typeD_hokkaido.csv --meta data/raw/typeD_hokkaido.meta.json --out ../docs/phase0/jartic-hokkaido-202609.md
```

## 規約

- ドキュメントは英日2言語（`README.md` / `README.ja.md`）。片方を更新したらもう片方も更新する
- コミットメッセージは英語、Conventional Commits 形式
