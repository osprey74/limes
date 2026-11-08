# Phase 0 試験区域の判定試算

- 区域：経度 139.61975–139.65271、緯度 35.63944–35.66622（ズーム16タイル x 58185–58190、y 25810–25815）
- OSM 道路：1,385 way、218.1 km（`highway=service` 1,167 way は対象外）
- JARTIC（2026年09月）：区域にかかる 112 206 件、114 3 件、20 33 件、17 29 件
- 照合条件：JARTIC 線の ±12 m に way 長の 50% 以上が入れば一致、地理院中心線は ±8 m で最も重なるもの

## 判定段ごとの延長

| 判定段 | way 数 | 延長 km | 割合 |
| --- | ---: | ---: | ---: |
| 1 規制速度 | 470 | 95.9 | 44.0% |
| 4 中央分離帯 | 2 | 0.1 | 0.0% |
| 5 中央線・通行帯 | 22 | 3.1 | 1.4% |
| 7 生活道路 | 860 | 114.5 | 52.5% |
| 8 不明 | 31 | 4.5 | 2.1% |

## 判定結果 × 地理院の幅員区分（延長 km）

| 判定（信頼度） | 3m未満 | 3m-5.5m未満 | 5.5m-13m未満 | 13m-19.5m未満 | (該当なし) | 計 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 20（high） | 0.2 | 3.9 | 0.0 | 0.0 | 0.0 | 4.1 |
| 30（high） | 0.6 | 63.9 | 6.4 | 0.5 | 0.0 | 71.3 |
| 30（low） | 15.1 | 95.8 | 0.2 | 0.0 | 0.0 | 111.2 |
| 30（mid） | 0.3 | 3.0 | 0.0 | 0.0 | 0.0 | 3.3 |
| 40（high） | 0.6 | 0.5 | 17.1 | 2.3 | 0.0 | 20.5 |
| 60（high） | 0.3 | 0.1 | 0.6 | 0.1 | 0.0 | 1.0 |
| 60（mid） | 0.0 | 1.2 | 0.9 | 0.0 | 0.0 | 2.2 |
| 不明 | 0.7 | 3.4 | 0.4 | 0.0 | 0.0 | 4.5 |

## 要確認 A：30（low）だが地理院幅員 5.5m 以上（4 way、0.2 km）

中央線がある可能性があり、60 の取りこぼし候補。路面画像で中央線の有無を確認する。

| OSM way | 名称 | highway | 長さ m | 地理院幅員 | 判定 | 根拠 |
| --- | --- | --- | ---: | --- | --- | --- |
| [163149173](https://www.openstreetmap.org/way/163149173) | — | residential | 122 | 5.5m-13m未満 | 30（low） | OSM highway=residential |
| [43112252](https://www.openstreetmap.org/way/43112252) | 旧登戸道 | unclassified | 39 | 5.5m-13m未満 | 30（low） | OSM highway=unclassified |
| [882030368](https://www.openstreetmap.org/way/882030368) | — | residential | 37 | 5.5m-13m未満 | 30（low） | OSM highway=residential |
| [50054591](https://www.openstreetmap.org/way/50054591) | — | residential | 18 | 5.5m-13m未満 | 30（low） | OSM highway=residential |

## 要確認 B：不明（31 way、4.5 km）

幹線系（trunk〜tertiary）で JARTIC にも OSM の車線情報にも証拠がない道路。

| OSM way | 名称 | highway | 長さ m | 地理院幅員 | 判定 | 根拠 |
| --- | --- | --- | ---: | --- | --- | --- |
| [242685425](https://www.openstreetmap.org/way/242685425) | 環八通り | primary | 724 | 3m未満 | 不明 | OSM highway=primary で証拠なし |
| [31573444](https://www.openstreetmap.org/way/31573444) | 滝坂道南廻り | tertiary | 550 | 3m-5.5m未満 | 不明 | OSM highway=tertiary で証拠なし |
| [41378506](https://www.openstreetmap.org/way/41378506) | 瀬田貫井線 | secondary | 392 | 3m-5.5m未満 | 不明 | OSM highway=secondary で証拠なし |
| [719100633](https://www.openstreetmap.org/way/719100633) | 瀬田貫井線 | secondary | 342 | 3m-5.5m未満 | 不明 | OSM highway=secondary で証拠なし |
| [34622845](https://www.openstreetmap.org/way/34622845) | — | tertiary | 284 | 3m-5.5m未満 | 不明 | OSM highway=tertiary で証拠なし |
| [719100631](https://www.openstreetmap.org/way/719100631) | 渋谷経堂線 | secondary | 259 | 3m-5.5m未満 | 不明 | OSM highway=secondary で証拠なし |
| [386611984](https://www.openstreetmap.org/way/386611984) | 調布経堂停車場線 | secondary | 213 | 3m-5.5m未満 | 不明 | OSM highway=secondary で証拠なし |
| [58858402](https://www.openstreetmap.org/way/58858402) | — | tertiary | 144 | 3m-5.5m未満 | 不明 | OSM highway=tertiary で証拠なし |
| [750975765](https://www.openstreetmap.org/way/750975765) | 世田谷町田線 | primary | 140 | 3m-5.5m未満 | 不明 | OSM highway=primary で証拠なし |
| [41377961](https://www.openstreetmap.org/way/41377961) | 瀬田貫井線（補助第128号線） | secondary | 117 | 5.5m-13m未満 | 不明 | OSM highway=secondary で証拠なし |
| [645615585](https://www.openstreetmap.org/way/645615585) | 世田谷町田線 | primary | 113 | 5.5m-13m未満 | 不明 | OSM highway=primary で証拠なし |
| [43112251](https://www.openstreetmap.org/way/43112251) | 世田谷町田線 | primary | 107 | 3m-5.5m未満 | 不明 | OSM highway=primary で証拠なし |
| [1342319519](https://www.openstreetmap.org/way/1342319519) | 渋谷経堂線（緊急車両等通行路） | secondary_link | 106 | 3m-5.5m未満 | 不明 | OSM highway=secondary_link で証拠なし |
| [674069667](https://www.openstreetmap.org/way/674069667) | — | tertiary | 103 | 5.5m-13m未満 | 不明 | OSM highway=tertiary で証拠なし |
| [41577426](https://www.openstreetmap.org/way/41577426) | 補助54号線 | tertiary | 98 | 3m-5.5m未満 | 不明 | OSM highway=tertiary で証拠なし |

## 参考：JARTIC 規制速度と OSM `maxspeed` の不一致（11 way）

マップマッチ誤りか、どちらかのデータの古さを示す。

| OSM way | 名称 | highway | 長さ m | 地理院幅員 | 判定 | 根拠 |
| --- | --- | --- | ---: | --- | --- | --- |
| [261996438](https://www.openstreetmap.org/way/261996438) | ユリの木通り | tertiary | 322 | 3m-5.5m未満 | 30（high） | JARTIC 112 |
| [36878848](https://www.openstreetmap.org/way/36878848) | 日大通り | unclassified | 277 | 3m-5.5m未満 | 30（high） | JARTIC 112 |
| [76042727](https://www.openstreetmap.org/way/76042727) | 船橋仲通り | unclassified | 228 | 3m-5.5m未満 | 30（high） | JARTIC 112 |
| [560850261](https://www.openstreetmap.org/way/560850261) | 城山通り | tertiary | 222 | 5.5m-13m未満 | 30（high） | JARTIC 112 |
| [46615554](https://www.openstreetmap.org/way/46615554) | 日大通り | unclassified | 150 | 3m-5.5m未満 | 30（high） | JARTIC 112 |
| [674069664](https://www.openstreetmap.org/way/674069664) | — | residential | 114 | 3m-5.5m未満 | 30（high） | JARTIC 114 |
| [41176392](https://www.openstreetmap.org/way/41176392) | 赤堤通り | tertiary | 82 | 5.5m-13m未満 | 40（high） | JARTIC 112 |
| [41377855](https://www.openstreetmap.org/way/41377855) | — | unclassified | 46 | 3m-5.5m未満 | 30（high） | JARTIC 112 |
| [1435649755](https://www.openstreetmap.org/way/1435649755) | 城山通り | tertiary | 32 | 5.5m-13m未満 | 30（high） | JARTIC 112 |
| [1435649756](https://www.openstreetmap.org/way/1435649756) | 城山通り;宮の坂1号踏切 | tertiary | 13 | 5.5m-13m未満 | 30（high） | JARTIC 112 |
| [1090708206](https://www.openstreetmap.org/way/1090708206) | 城山通り | tertiary | 11 | 3m未満 | 40（high） | JARTIC 112 |

---

出典：
- 「交通規制情報」（公益財団法人日本道路交通情報センター）（<https://www.jartic.or.jp/service/opendata/>）（2026年11月8日に利用）を加工して作成
- © OpenStreetMap contributors（ODbL）
- 国土地理院 道路中心線（ベクトルタイル提供実験 experimental_rdcl）を加工して作成
