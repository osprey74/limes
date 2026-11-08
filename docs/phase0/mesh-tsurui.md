# Phase 0 試験区域の判定試算

- 区域：経度 144.29993–144.33289、緯度 43.22119–43.24520（ズーム16タイル x 59037–59042、y 24020–24025）
- OSM 道路：181 way、47.2 km（`highway=service` 26 way は対象外）
- JARTIC（2026年09月）：区域にかかる 112 6 件、114 0 件、20 0 件、17 0 件
- 照合条件：JARTIC 線の ±12 m に way 長の 50% 以上が入れば一致、地理院中心線は ±8 m で最も重なるもの

## 判定段ごとの延長

| 判定段 | way 数 | 延長 km | 割合 |
| --- | ---: | ---: | ---: |
| 1 規制速度 | 24 | 2.7 | 5.6% |
| 6 農道・林道等 | 6 | 4.3 | 9.0% |
| 7 生活道路 | 118 | 18.4 | 38.9% |
| 8 不明 | 33 | 21.9 | 46.5% |

## 判定結果 × 地理院の幅員区分（延長 km）

| 判定（信頼度） | 3m未満 | 3m-5.5m未満 | 5.5m-13m未満 | 13m-19.5m未満 | (該当なし) | 計 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 30（high） | 0.0 | 0.9 | 0.0 | 0.0 | 0.0 | 0.9 |
| 30（low） | 0.5 | 14.7 | 2.9 | 0.1 | 0.1 | 18.4 |
| 30（mid） | 0.0 | 0.2 | 2.3 | 0.0 | 1.8 | 4.3 |
| 40（high） | 0.0 | 0.0 | 0.9 | 0.3 | 0.0 | 1.2 |
| 50（high） | 0.0 | 0.0 | 0.6 | 0.0 | 0.0 | 0.6 |
| 不明 | 0.0 | 1.1 | 16.3 | 3.7 | 0.8 | 21.9 |

## 要確認 A：30（low）だが地理院幅員 5.5m 以上（20 way、3.0 km）

中央線がある可能性があり、60 の取りこぼし候補。路面画像で中央線の有無を確認する。

| OSM way | 名称 | highway | 長さ m | 地理院幅員 | 判定 | 根拠 |
| --- | --- | --- | ---: | --- | --- | --- |
| [113530540](https://www.openstreetmap.org/way/113530540) | — | unclassified | 370 | 5.5m-13m未満 | 30（low） | OSM highway=unclassified |
| [721833886](https://www.openstreetmap.org/way/721833886) | — | residential | 309 | 5.5m-13m未満 | 30（low） | OSM highway=residential |
| [113529441](https://www.openstreetmap.org/way/113529441) | — | unclassified | 212 | 5.5m-13m未満 | 30（low） | OSM highway=unclassified |
| [113529829](https://www.openstreetmap.org/way/113529829) | — | residential | 190 | 5.5m-13m未満 | 30（low） | OSM highway=residential |
| [113529198](https://www.openstreetmap.org/way/113529198) | — | unclassified | 189 | 5.5m-13m未満 | 30（low） | OSM highway=unclassified |
| [113530041](https://www.openstreetmap.org/way/113530041) | — | unclassified | 186 | 5.5m-13m未満 | 30（low） | OSM highway=unclassified |
| [113529018](https://www.openstreetmap.org/way/113529018) | — | unclassified | 181 | 5.5m-13m未満 | 30（low） | OSM highway=unclassified |
| [113529959](https://www.openstreetmap.org/way/113529959) | — | unclassified | 163 | 5.5m-13m未満 | 30（low） | OSM highway=unclassified |
| [113529729](https://www.openstreetmap.org/way/113529729) | — | unclassified | 160 | 5.5m-13m未満 | 30（low） | OSM highway=unclassified |
| [721833887](https://www.openstreetmap.org/way/721833887) | — | residential | 155 | 5.5m-13m未満 | 30（low） | OSM highway=residential |
| [721806236](https://www.openstreetmap.org/way/721806236) | — | residential | 143 | 5.5m-13m未満 | 30（low） | OSM highway=residential |
| [1425484311](https://www.openstreetmap.org/way/1425484311) | — | residential | 114 | 5.5m-13m未満 | 30（low） | OSM highway=residential |
| [113529135](https://www.openstreetmap.org/way/113529135) | — | unclassified | 103 | 5.5m-13m未満 | 30（low） | OSM highway=unclassified |
| [113530064](https://www.openstreetmap.org/way/113530064) | — | unclassified | 94 | 5.5m-13m未満 | 30（low） | OSM highway=unclassified |
| [721817304](https://www.openstreetmap.org/way/721817304) | — | residential | 88 | 5.5m-13m未満 | 30（low） | OSM highway=residential |

## 要確認 B：不明（33 way、21.9 km）

幹線系（trunk〜tertiary）で JARTIC にも OSM の車線情報にも証拠がない道路。

| OSM way | 名称 | highway | 長さ m | 地理院幅員 | 判定 | 根拠 |
| --- | --- | --- | ---: | --- | --- | --- |
| [113528928](https://www.openstreetmap.org/way/113528928) | 釧路鶴居弟子屈線 | primary | 7570 | 5.5m-13m未満 | 不明 | OSM highway=primary で証拠なし |
| [113528986](https://www.openstreetmap.org/way/113528986) | 釧路鶴居弟子屈線 | primary | 3747 | 13m-19.5m未満 | 不明 | OSM highway=primary で証拠なし |
| [113528994](https://www.openstreetmap.org/way/113528994) | — | tertiary | 981 | 3m-5.5m未満 | 不明 | OSM highway=tertiary で証拠なし |
| [113530595](https://www.openstreetmap.org/way/113530595) | — | tertiary | 954 | 5.5m-13m未満 | 不明 | OSM highway=tertiary で証拠なし |
| [113530297](https://www.openstreetmap.org/way/113530297) | 阿寒公園鶴居線 | secondary | 941 | 5.5m-13m未満 | 不明 | OSM highway=secondary で証拠なし |
| [113530583](https://www.openstreetmap.org/way/113530583) | 幌呂原野鶴居線 | secondary | 908 | 5.5m-13m未満 | 不明 | OSM highway=secondary で証拠なし |
| [113529263](https://www.openstreetmap.org/way/113529263) | — | tertiary | 902 | 5.5m-13m未満 | 不明 | OSM highway=tertiary で証拠なし |
| [113529498](https://www.openstreetmap.org/way/113529498) | — | tertiary | 790 | (該当なし) | 不明 | OSM highway=tertiary で証拠なし |
| [113529015](https://www.openstreetmap.org/way/113529015) | 幌呂原野鶴居線 | secondary | 711 | 5.5m-13m未満 | 不明 | OSM highway=secondary で証拠なし |
| [113529569](https://www.openstreetmap.org/way/113529569) | — | tertiary | 479 | 5.5m-13m未満 | 不明 | OSM highway=tertiary で証拠なし |
| [113530142](https://www.openstreetmap.org/way/113530142) | — | tertiary | 457 | 5.5m-13m未満 | 不明 | OSM highway=tertiary で証拠なし |
| [113530312](https://www.openstreetmap.org/way/113530312) | — | tertiary | 334 | 5.5m-13m未満 | 不明 | OSM highway=tertiary で証拠なし |
| [113530421](https://www.openstreetmap.org/way/113530421) | — | tertiary | 329 | 5.5m-13m未満 | 不明 | OSM highway=tertiary で証拠なし |
| [113530139](https://www.openstreetmap.org/way/113530139) | 阿寒公園鶴居線 | secondary | 299 | 5.5m-13m未満 | 不明 | OSM highway=secondary で証拠なし |
| [113529097](https://www.openstreetmap.org/way/113529097) | — | tertiary | 283 | 5.5m-13m未満 | 不明 | OSM highway=tertiary で証拠なし |

## 参考：JARTIC 規制速度と OSM `maxspeed` の不一致（0 way）

マップマッチ誤りか、どちらかのデータの古さを示す。

| OSM way | 名称 | highway | 長さ m | 地理院幅員 | 判定 | 根拠 |
| --- | --- | --- | ---: | --- | --- | --- |

---

出典：
- 「交通規制情報」（公益財団法人日本道路交通情報センター）（<https://www.jartic.or.jp/service/opendata/>）（2026年11月8日に利用）を加工して作成
- © OpenStreetMap contributors（ODbL）
- 国土地理院 道路中心線（ベクトルタイル提供実験 experimental_rdcl）を加工して作成
