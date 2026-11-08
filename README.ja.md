# Limes（リメス）

[English](README.md)

Limes は、走行中の道路の最高速度を公開データから推定し、GPS の走行速度と並べて表示する日本国内向けのドライブサポートアプリ（iOS／Android）です。規制速度があればその速度を、なければ法定速度（2026年9月1日改正後の 60km/h または 30km/h）を表示します。

推定値には必ず信頼度を添えます。実際の最高速度は現地の道路標識・道路標示に従ってください。

> 状況：開発初期（Phase 0：データ検証）

## リポジトリ構成

| パス | 内容 |
| --- | --- |
| `core/` | Rust ワークスペース：`limes-core`（速度判定・マップマッチ・データ更新）、UniFFI バインディング、`limes-cli` |
| `ios/` | iOS アプリ（Swift／SwiftUI、MapLibre Native） |
| `android/` | Android アプリ（Kotlin／Jetpack Compose、MapLibre Native） |
| `data-pipeline/` | Python パイプライン：JARTIC・OSM・国土地理院データの取り込み |
| `docs/` | 設計メモ、データ検証レポート |

## データ出典

- 「交通規制情報」（公益財団法人日本道路交通情報センター）（https://www.jartic.or.jp/service/opendata/）を加工して作成
- © OpenStreetMap contributors（ODbL）
- 国土地理院
