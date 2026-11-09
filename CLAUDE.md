# CLAUDE.md

Limes（リメス）：走行中の道路の最高速度（規制速度または法定速度）を公開データから推定し、GPS速度と並べて表示する日本国内向けアプリ（iOS／Android同時リリース）。

## 構成（モノレポ）

| パス | 内容 | 状態 |
| --- | --- | --- |
| `core/` | Rustワークスペース。`limes-core`（判定・マップマッチ・DB読込・更新管理）、`limes-ffi`（UniFFI）、`limes-cli`（パイプライン用判定） | Phase 1（判定・条件評価・DB・マップマッチ・UniFFI・更新管理まで） |
| `ios/` | Swift / SwiftUI、MapLibre Native、StoreKit 2 | 未着手 |
| `android/` | Kotlin / Jetpack Compose、MapLibre Native、Play Billing | 未着手 |
| `data-pipeline/` | Python（uv）。JARTIC取得・集計、のちにOSM・国土地理院データ結合 | Phase 0 |
| `docs/phase0/` | データ検証レポートと所見 | — |

## 設計上の決定（要点）

- 判定ロジックはRustの `limes-core` に一元化し、アプリ（UniFFI経由）とパイプライン（`limes-cli`）の両方から使う。Swift／Kotlin／Pythonで判定を再実装しない
- 判定は上から順に評価：規制速度 → 高速自動車国道 → 自動車専用道路 → 中央分離帯 → 中央線・車両通行帯の証拠 → 農道等 → 生活道路(30) → 不明。速度と信頼度（high/mid/low）を必ずセットで出す。実装は `core/limes-core/src/decide.rs`、期待値は `core/limes-core/tests/golden/decide.json`
- 高速自動車国道は本線車道・加減速車線のみ100（施行令第27条）。ランプ（OSM `motorway_link`）は60（第11条第1号イ）
- JARTICの規制条件は対象ブロック（NO.41-85）と除外ブロック（NO.86-130）の両方を評価する（`conditions.rs`）
- 信頼度lowで60を表示しない。道路幅員だけを根拠に60と判定しない（幅員区分では中央線の有無を予測できない。`docs/phase0/findings.md` 6.3）
- 中央線の証拠として、地理院航空写真からの自動検出を使う（60・mid）。証拠のない一般道路は安全側に倒して30（low）
- OSM `highway=track`（未舗装の農道・林道が中心）はデータベースから除外する（2026-11-09決定）。その上を走ると照合先がなく「不明」になる
- 判定不能時は数値を出さず「不明」
- 検証ゲート（`data-pipeline/limes_pipeline/gate.py`）の前回比閾値は±10%で運用を始め、数か月分の実際の変動を見て調整する（2026-11-09決定）
- 速度超過の警告・表示は実装しない
- 走行中に速度マップを開くと確認ダイアログ（［走行画面に戻る］／［同乗者が操作する］）
- データは毎日 `opendata.json` で更新を検知し、自動ビルド → 検証ゲート → R2配信（manifest.json）→ アプリ起動時に差分取得
- 地図はMapLibre Native。速度線はパイプラインでベクタータイル化して重ねる

## データの注意点（Phase 0で判明）

- JARTIC CSVはcp932、170項目。列番号は仕様書の項目NO（1始まり）で `limes_pipeline/jartic.py` の `Col` に定義
- JARTICの中央線(15)は全国的にほぼ空（22都道府県で0件）。路線名は全国0%、道路種別コードは6府県のみ。高速判別・道路名はOSMに頼る。詳細は `docs/phase0/findings.md`
- はみ出し禁止(17)の両側標示は中央線を兼ねる（警察庁「交通規制基準」第10 留意事項1）。片側・両側コード(136)が3または空欄の17は判定段5の証拠（high）とする。2・1は単独では使わない
- 対象車両が「その他」のみで規制条件(131)が空欄の規制（長野・岡山に多い）は全車両に適用する（`jartic.has_unclear_vehicle`）
- 「通年」「終日」「全車両」の書き方は都道府県ごとに異なる（0埋め、`0101`-`1231`、`0`-`0`、仕様外の曜日コード`9`）。判定は `jartic.py` の関数を使う
- 「K_2.1注」（29都道府県、CSVには記録されず一覧PDFのみに記載）はユニークキーに継続性がないため、差分ではなく毎月全件再生成
- 生データ（`data-pipeline/data/`、`*.csv`、`*.zip`）はコミットしない

## 出典表記（必須）

JARTIC由来のデータ・レポートには「出典：『交通規制情報』（公益財団法人日本道路交通情報センター）（<https://www.jartic.or.jp/service/opendata/>）を加工して作成」を入れる。OSMはODbL帰属表示、国土地理院は出典明記。

## コマンド

```sh
cd core
cargo test
cargo run -p limes-cli -- golden
```

```sh
cd data-pipeline
uv sync
uv run pytest
uv run python scripts/fetch_jartic.py hokkaido --out-dir data/raw
uv run python scripts/inspect_jartic.py data/raw/typeD_hokkaido.csv --meta data/raw/typeD_hokkaido.meta.json --out ../docs/phase0/jartic-hokkaido-202609.md
```

## 規約

- リポジトリ直下の `Limes — 法定速度推定アプリ Claude Code向けハンドオフ.md` は非公開の計画書（収益モデル・費用試算を含む）。gitignore 済みで、コミットしない。参照はしてよいが、その内容を公開ファイルへ転記しない
- ドキュメントは英日2言語（`README.md` / `README.ja.md`）。片方を更新したらもう片方も更新する
- コミットメッセージは英語、Conventional Commits 形式
