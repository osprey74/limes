# Limes

[日本語](README.ja.md)

Limes is a driving companion app for Japan (iOS / Android) that estimates the maximum speed of the road you are driving on — the posted limit where one exists, otherwise the statutory limit (60 or 30 km/h after the 2026-09-01 amendment) — from public data, and shows it next to your GPS speed.

Estimates always come with a confidence level. Actual road signs and markings take precedence.

> Status: early development (Phase 0 — data validation).

## Repository layout

| Path | Contents |
| --- | --- |
| `core/` | Rust workspace: `limes-core` (speed decision, map matching, data updates), UniFFI bindings, `limes-cli` |
| `ios/` | iOS app (Swift / SwiftUI, MapLibre Native) |
| `android/` | Android app (Kotlin / Jetpack Compose, MapLibre Native) |
| `data-pipeline/` | Python pipeline: JARTIC / OSM / GSI data ingestion |
| `docs/` | Design notes and data validation reports |

## Data sources

- Traffic regulation data: 「交通規制情報」（公益財団法人日本道路交通情報センター）（https://www.jartic.or.jp/service/opendata/）, processed by this project
- © OpenStreetMap contributors (ODbL)
- Geospatial Information Authority of Japan (国土地理院)
