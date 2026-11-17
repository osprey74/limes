# 公開前の準備

ストアに出す前に用意するものと、申告フォームに入れる内容の下書き。アプリが実際に行っていること（コード）と食い違わないように、根拠のファイルを添える。

作成：2026-11-15

## 1. アプリが扱う情報（申告の根拠）

| 情報 | 端末の外に出るか | 根拠 |
| --- | --- | --- |
| 位置情報（道路の特定と速度の表示） | 出ない。端末内で処理する。使用中のみ取得し、履歴は保存しない | `ios/Limes/Drive/DriveModel.swift`（`requestWhenInUseAuthorization`）、`android/app/src/main/AndroidManifest.xml`（バックグラウンドの位置情報の権限なし） |
| 位置情報（いまいる都道府県を調べる） | 出る。自動追加が有効（既定）のとき、3 km 移動するごとか10分ごとに、OS の逆ジオコーディング（iOS は `CLGeocoder` で Apple、Android は `Geocoder` で Google）へ現在地を送る。開発者のサーバーには届かない | `ios/Limes/Drive/DriveModel.swift`・`android/…/drive/DriveModel.kt` の `maybeAddCurrentPrefecture` |
| 端末を区別する値（ID の SHA-256） | 出る。最初のデータダウンロードのときに一度、OS の種類とともに `server/` へ送り、最初に届いた日時と合わせて保存する | `ios/Limes/Access/TrialClient.swift`、`android/…/access/TrialClient.kt`、`server/schema.sql` |
| 取得する都道府県 | 出る。データ配信（お名前.com のレンタルサーバー `limes.osprey74.com`）への要求として。自動追加が有効なら、いまいる県も要求する（iOS 版も 2026-11-16 にこの配信 URL へ切り替え済み） | `android/…/data/DataServer.kt`、`ios/Limes/Data/DataServer.swift`、`DriveModel.swift` |
| 購入の情報 | 開発者には届かない。登録の有無を端末上でストアに確認するだけ | `ios/Limes/Access/Billing.swift` |
| 広告・解析・トラッキング | なし。該当する SDK を入れていない | `android/app/build.gradle.kts` の依存、iOS は外部ライブラリなし |

## 2. プライバシーポリシー

- 本文：`site/privacy/index.html`（日本語と英語を1ページに）
- 公開先：`https://limes.osprey74.com/privacy/`（2026-11-16 公開。`site/` を変えたコミットが `main` に入ると `.github/workflows/site.yml` が置き直す。`docs/data-hosting.md`）。App Store Connect と Google Play Console への URL の登録はこれから
- データの取得先は、お名前.com のレンタルサーバー（運営：GMOインターネット株式会社）として書いてある（2026-11-16、Android 版の配信 URL の切り替えに合わせて、上の表・下の 3・ポリシー本文を書き換えた）。申告の内容は変えていない（2026-11-15決定。`docs/data-hosting.md` の 6）。iOS 版の配信 URL も 2026-11-16 に切り替えた
- アプリ内のリンク（iOS 版）：有料プラン画面と設定画面の「情報」に、プライバシーポリシーと利用規約（Apple の標準 EULA）へのリンクがある（2026-11-17。`ios/Limes/Config.swift`）。App Store に入れる文面と登録の手順は `app-store-listing.md`
- 問い合わせ先：GitHub Issues（<https://github.com/osprey74/limes/issues>）
- アプリの挙動を変えたら（送信する情報、外部サービス、位置情報の使い方）、ポリシー・下の申告・`ios/Limes/PrivacyInfo.xcprivacy` の3つをそろえて直す

## 3. App Store：アプリのプライバシー（App Store Connect）

| 質問 | 回答 |
| --- | --- |
| データを収集しますか | はい |
| 収集するデータの種類 | ID ＞ デバイス ID |
| 用途 | アプリの機能 |
| ユーザーに関連付けられますか | いいえ |
| トラッキングに使用しますか | いいえ |

- 位置情報は「収集」に入れない（2026-11-15、Apple の説明で確認）。根拠は <https://developer.apple.com/app-store/app-privacy-details/> の次の記述
  - 収集の定義："Collect" refers to transmitting data off the device in a way that allows you and/or your third-party partners to access it for a period longer than what is necessary to service the transmitted request in real time.
  - 端末内の処理："Data that is processed only on device is not "collected" and does not need to be disclosed in your answers. If you derive anything from that data and send it off device, the resulting data should be considered separately."（道路の特定と速度の表示がこれに当たる）
  - Apple のフレームワーク："If you collect data about your app from Apple frameworks or services, you should indicate what data you collect and how you use it. You are not responsible for disclosing data collected by Apple."（`CLGeocoder` へ送る現在地がこれに当たる。開発者も、開発者がコードを組み込んだ外部の事業者も受け取らない）
  - 位置から導いた「いまいる都道府県」は、データの要求として配信サーバー（お名前.com のレンタルサーバー）へ送られる。開発者がこの要求の記録を読める形で残していなければ収集に当たらない。県名入りのファイル名の取得要求は、申告を変えるほどの情報ではないと判断し、サーバーのアクセス記録の有無は調べていない（2026-11-15決定。`docs/data-hosting.md` の 6）
- 購入履歴も入れない（開発者は受け取らない）
- 送っているのはアプリが作った ID のハッシュだが、入れ直しても同じ値で端末を区別するので、デバイス ID として申告する（控えめな側の判断。Apple に確かめたものではない）
- プライバシーマニフェスト：`ios/Limes/PrivacyInfo.xcprivacy`。収集データ（デバイス ID、アプリの機能、関連付けなし、トラッキングなし）と、理由の申告が要る API（UserDefaults：CA92.1、ファイルのタイムスタンプ：C617.1。後者は Rust コアが `stat` 系を呼ぶため）

## 4. Google Play：データ セーフティ

| 質問 | 回答 |
| --- | --- |
| ユーザーデータを収集または共有しますか | はい（収集） |
| 収集するデータ | デバイスまたはその他の ID、正確な位置情報 |
| 共有しますか | いいえ |
| 用途 | アプリの機能 |
| 収集は必須ですか | ID は必須（データをダウンロードすると送られる）。位置情報は任意（自動追加を無効にすると送られない） |
| 転送時に暗号化されますか | はい（HTTPS） |
| ユーザーはデータの削除をリクエストできますか | いいえ（値が個人と結び付いておらず、特定の利用者の値を探せない） |

- 位置情報も申告する（2026-11-15決定）：「正確な位置情報：収集する、共有しない、用途はアプリの機能、任意（設定で止められる）」。自動追加が有効なとき、Android の `Geocoder` を通じて現在地（緯度・経度）が Google のサービスへ送られるため。Google の定義では、収集はアプリから端末の外へデータを送ること全般を指す（<https://support.google.com/googleplay/android-developer/answer/10787469>）
- 位置情報の権限は「使用中のみ」（精度の高い位置情報）。バックグラウンドの位置情報は使わないので、その申告は不要

## 5. 審査メモ

App Store の「App Review に関する情報」のメモ欄と、Google Play の審査向けの説明に入れる。App Review 向けは英語で書く。

```text
Limes shows the estimated speed limit of the road being driven on, next to the GPS speed. It is for use in Japan only: the road data covers Japan.

What the reviewer needs to know
- No account or sign-in.
- The app is used while driving, mounted in view. It has no map and no controls to operate while driving: the driving screen only displays. It never warns about speeding and plays no sound.
- The speed limit shown is an estimate from open data (JARTIC traffic regulation data, OpenStreetMap, GSI aerial photos). The driving screen always says so and tells the driver to follow the actual signs. When the road cannot be determined, the app shows "unknown" instead of a number.
- Location is used only while the app is in use. Finding the road and the speed limit happens on the device, and the location is never sent to our server. With "add the current prefecture automatically" on (the default), the app asks the system geocoder (CLGeocoder) which prefecture the device is in, every 3 km or 10 minutes, so that it can download that prefecture's data.

How to see it work
1. Open Settings (gear icon) > Download, choose a prefecture (for example Tokushima, about 33 MB) and download it.
2. The speed limit appears when the device moves along a road in that prefecture. Outside Japan, or when standing still, the sign shows "unknown". A simulated drive (a GPX route in Japan) shows the limit changing.

Free trial and subscription
- The free trial is the app's own: 14 days from the first data download, with every feature. It is not an App Store introductory offer.
- To stop a reinstall from restarting the trial, the app sends a SHA-256 hash of an app-generated ID to our server once, at the first download. Nothing else is sent to our server.
- After the trial, without a subscription, the app keeps showing the GPS speed; the speed limit and the data downloads need the subscription (com.osprey74.limes.premium.monthly / .yearly, one subscription group).
- The plans screen (Settings > Paid plan) has the prices from the store, Restore Purchases, Manage Subscription, and the links to the Terms of Use (Apple's standard EULA) and the Privacy Policy. There is no other way to unlock the paid features.
```

日本語の要点（上の英文と同じ内容）：

- アカウントなし。日本国内専用
- 運転中に使うアプリで、走行画面は表示だけ。運転中に操作させない。速度超過の警告や音は出さない
- 表示は公開データからの推定で、走行画面に常にその旨と「現地の標識・標示に従ってください」を出す。判定できないときは数値を出さず「不明」
- 位置情報は使用中のみ。道路の特定は端末内で処理し、開発者のサーバーへは送らない。自動追加が有効なときは、いまいる都道府県を調べるために OS の逆ジオコーディングへ現在地を送る
- 無料期間はアプリ独自（最初のダウンロードから14日間）。入れ直しでやり直せないよう、アプリが作った ID のハッシュを一度だけ送る
- 無料期間のあとは、登録しなくても GPS の現在速度は表示する。有料機能を解放する別の手段はない

### 決めること・用意するもの

- 走行中の画面の録画は添えない（2026-11-15決定）。位置情報を使う既存アプリ（Michi-Navi、Rindo）は録画なしで審査を通っており、審査側でも位置情報のシミュレーションはできる。審査で求められたら、そのとき用意する
- 審査メモの「33 MB」などの数値は、提出時点のデータで確かめ直す（2026-11-17 時点：徳島県は展開後 33 MB で変わらず）
- Sandbox で購入を試すためのテスト用アカウントは App Review 側が持っているので、こちらで用意するものはない（Sandbox の商品が App Store Connect で「提出準備完了」になっていること）
