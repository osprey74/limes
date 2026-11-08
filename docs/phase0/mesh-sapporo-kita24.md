# Phase 0 試験区域の判定試算

- 区域：経度 141.32812–141.36108、緯度 43.08093–43.10499（ズーム16タイル x 58496–58501、y 24055–24060）
- OSM 道路：728 way、259.8 km（`highway=service` 137 way は対象外）
- JARTIC（2026年09月）：区域にかかる 112 68 件、114 1 件、20 29 件、17 0 件
- 照合条件：JARTIC 線の ±12 m に way 長の 50% 以上が入れば一致、地理院中心線は ±8 m で最も重なるもの

## 判定段ごとの延長

| 判定段 | way 数 | 延長 km | 割合 |
| --- | ---: | ---: | ---: |
| 1 規制速度 | 141 | 103.5 | 39.9% |
| 2 高速自動車国道 | 1 | 0.2 | 0.1% |
| 4 中央分離帯 | 8 | 4.9 | 1.9% |
| 5 中央線・通行帯 | 42 | 37.9 | 14.6% |
| 7 生活道路 | 523 | 108.6 | 41.8% |
| 8 不明 | 13 | 4.7 | 1.8% |

## 判定結果 × 地理院の幅員区分（延長 km）

| 判定（信頼度） | 3m未満 | 3m-5.5m未満 | 5.5m-13m未満 | 13m-19.5m未満 | 19.5m以上 | 計 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 100（high） | 0.0 | 0.2 | 0.0 | 0.0 | 0.0 | 0.2 |
| 30（high） | 0.0 | 11.6 | 9.3 | 0.0 | 0.0 | 20.9 |
| 30（low） | 10.0 | 69.1 | 18.7 | 0.0 | 0.0 | 97.7 |
| 30（mid） | 0.9 | 6.9 | 3.1 | 0.0 | 0.0 | 10.8 |
| 40（high） | 0.0 | 4.2 | 3.8 | 0.0 | 0.0 | 8.0 |
| 50（high） | 0.0 | 0.0 | 14.2 | 2.4 | 21.4 | 38.0 |
| 60（high） | 0.0 | 0.7 | 4.0 | 0.0 | 0.2 | 4.9 |
| 60（mid） | 0.0 | 3.7 | 31.7 | 0.0 | 2.5 | 37.9 |
| 80（high） | 0.0 | 2.3 | 4.5 | 0.0 | 29.9 | 36.6 |
| 不明 | 0.0 | 0.0 | 3.1 | 0.0 | 1.6 | 4.7 |

## 要確認 A：30（low）だが地理院幅員 5.5m 以上（43 way、18.7 km）

中央線がある可能性があり、60 の取りこぼし候補。路面画像で中央線の有無を確認する。

| OSM way | 名称 | highway | 長さ m | 地理院幅員 | 判定 | 根拠 |
| --- | --- | --- | ---: | --- | --- | --- |
| [104655319](https://www.openstreetmap.org/way/104655319) | — | residential | 1817 | 5.5m-13m未満 | 30（low） | OSM highway=residential |
| [154482330](https://www.openstreetmap.org/way/154482330) | — | residential | 1283 | 5.5m-13m未満 | 30（low） | OSM highway=residential |
| [104646003](https://www.openstreetmap.org/way/104646003) | — | residential | 1146 | 5.5m-13m未満 | 30（low） | OSM highway=residential |
| [222078863](https://www.openstreetmap.org/way/222078863) | — | residential | 964 | 5.5m-13m未満 | 30（low） | OSM highway=residential |
| [60356340](https://www.openstreetmap.org/way/60356340) | — | residential | 945 | 5.5m-13m未満 | 30（low） | OSM highway=residential |
| [104650450](https://www.openstreetmap.org/way/104650450) | — | residential | 915 | 5.5m-13m未満 | 30（low） | OSM highway=residential |
| [104650458](https://www.openstreetmap.org/way/104650458) | — | residential | 914 | 5.5m-13m未満 | 30（low） | OSM highway=residential |
| [104655318](https://www.openstreetmap.org/way/104655318) | — | residential | 908 | 5.5m-13m未満 | 30（low） | OSM highway=residential |
| [104655310](https://www.openstreetmap.org/way/104655310) | — | residential | 647 | 5.5m-13m未満 | 30（low） | OSM highway=residential |
| [104650453](https://www.openstreetmap.org/way/104650453) | — | residential | 645 | 5.5m-13m未満 | 30（low） | OSM highway=residential |
| [78488749](https://www.openstreetmap.org/way/78488749) | — | residential | 614 | 5.5m-13m未満 | 30（low） | OSM highway=residential |
| [60263990](https://www.openstreetmap.org/way/60263990) | — | residential | 571 | 5.5m-13m未満 | 30（low） | OSM highway=residential |
| [154477560](https://www.openstreetmap.org/way/154477560) | — | residential | 497 | 5.5m-13m未満 | 30（low） | OSM highway=residential |
| [60263989](https://www.openstreetmap.org/way/60263989) | — | residential | 488 | 5.5m-13m未満 | 30（low） | OSM highway=residential |
| [104655311](https://www.openstreetmap.org/way/104655311) | — | residential | 469 | 5.5m-13m未満 | 30（low） | OSM highway=residential |

## 要確認 B：不明（13 way、4.7 km）

幹線系（trunk〜tertiary）で JARTIC にも OSM の車線情報にも証拠がない道路。

| OSM way | 名称 | highway | 長さ m | 地理院幅員 | 判定 | 根拠 |
| --- | --- | --- | ---: | --- | --- | --- |
| [154482773](https://www.openstreetmap.org/way/154482773) | — | tertiary | 1286 | 19.5m以上 | 不明 | OSM highway=tertiary で証拠なし |
| [1123811345](https://www.openstreetmap.org/way/1123811345) | 新琴似2条通 | tertiary | 1051 | 5.5m-13m未満 | 不明 | OSM highway=tertiary で証拠なし |
| [222078270](https://www.openstreetmap.org/way/222078270) | — | tertiary | 808 | 5.5m-13m未満 | 不明 | OSM highway=tertiary で証拠なし |
| [1084344335](https://www.openstreetmap.org/way/1084344335) | — | tertiary | 387 | 5.5m-13m未満 | 不明 | OSM highway=tertiary で証拠なし |
| [1057683588](https://www.openstreetmap.org/way/1057683588) | — | tertiary | 313 | 5.5m-13m未満 | 不明 | OSM highway=tertiary で証拠なし |
| [1130906203](https://www.openstreetmap.org/way/1130906203) | — | tertiary | 266 | 19.5m以上 | 不明 | OSM highway=tertiary で証拠なし |
| [1127494640](https://www.openstreetmap.org/way/1127494640) | 新琴似2条通 | tertiary | 246 | 5.5m-13m未満 | 不明 | OSM highway=tertiary で証拠なし |
| [701844825](https://www.openstreetmap.org/way/701844825) | — | tertiary | 159 | 5.5m-13m未満 | 不明 | OSM highway=tertiary で証拠なし |
| [1133474927](https://www.openstreetmap.org/way/1133474927) | — | tertiary | 39 | 5.5m-13m未満 | 不明 | OSM highway=tertiary で証拠なし |
| [222078271](https://www.openstreetmap.org/way/222078271) | — | tertiary | 37 | 5.5m-13m未満 | 不明 | OSM highway=tertiary で証拠なし |
| [729755465](https://www.openstreetmap.org/way/729755465) | — | tertiary | 32 | 3m-5.5m未満 | 不明 | OSM highway=tertiary で証拠なし |
| [1103206591](https://www.openstreetmap.org/way/1103206591) | — | tertiary | 15 | 5.5m-13m未満 | 不明 | OSM highway=tertiary で証拠なし |
| [1110284409](https://www.openstreetmap.org/way/1110284409) | — | tertiary | 11 | 5.5m-13m未満 | 不明 | OSM highway=tertiary で証拠なし |

## 参考：JARTIC 規制速度と OSM `maxspeed` の不一致（0 way）

マップマッチ誤りか、どちらかのデータの古さを示す。

| OSM way | 名称 | highway | 長さ m | 地理院幅員 | 判定 | 根拠 |
| --- | --- | --- | ---: | --- | --- | --- |

---

出典：
- 「交通規制情報」（公益財団法人日本道路交通情報センター）（<https://www.jartic.or.jp/service/opendata/>）（2026年11月8日に利用）を加工して作成
- © OpenStreetMap contributors（ODbL）
- 国土地理院 道路中心線（ベクトルタイル提供実験 experimental_rdcl）を加工して作成
