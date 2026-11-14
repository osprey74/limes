# iOS版 引き継ぎ資料

Android版（`android/`）で決めた動作を、iOS版（`ios/`）で同じにするための資料。設計上の決定とその理由は `CLAUDE.md` にある。ここには Android版の実装から読み取った「何をどう動かすか」を書く。コードの場所は Android版のファイルで示す（`android/app/src/main/java/com/osprey74/limes/` 以下は `…/` と略す）。

作成：2026-11-14（Android版 コミット 7eee9fa 時点）

## 1. 全体像

- アプリは4画面＋起動画面：走行画面、設定画面、データのダウンロード画面、有料プラン画面。地図はない
- 判定はすべて Rust の `limes-core` が行う。Swift で判定・マップマッチ・祝日計算を書き直さない
- 都道府県ごとの SQLite（zstd 圧縮）を R2 から取ってきて端末に置き、走行中は通信しない
- 無料期間はアプリ側の14日間。開始日は `server/` に記録する。課金は StoreKit 2 の自動更新サブスクリプション

## 2. Rust コアの組み込み

### ビルド

- `core/limes-ffi` は `crate-type = ["lib", "cdylib", "staticlib"]`。iOS は staticlib を使う
- ターゲット：`aarch64-apple-ios`（実機）、`aarch64-apple-ios-sim`（Apple シリコンのシミュレーター）。Intel Mac のシミュレーターも要るなら `x86_64-apple-ios` を足して `lipo` でまとめる
- Swift バインディングは UniFFI 0.32 の `uniffi-bindgen`（`limes-ffi` の bin）で、ビルドしたライブラリから生成する。モジュール名は `LimesCore`（`core/limes-ffi/uniffi.toml`）

```sh
cd core
cargo build --release -p limes-ffi --target aarch64-apple-ios
cargo build --release -p limes-ffi --target aarch64-apple-ios-sim
cargo run --release -p limes-ffi --bin uniffi-bindgen -- generate \
  --library target/aarch64-apple-ios/release/liblimes_ffi.a \
  --language swift --out-dir <出力先>
# 出力の LimesCoreFFI.h と modulemap を headers に置き、
# xcodebuild -create-xcframework -library … -headers … で LimesCore.xcframework にまとめる
```

- Android版はこれを Gradle のタスク（`android/app/build.gradle.kts` の `cargoNdk`・`uniffiBindings`）にしてビルドの前に自動で走らせている。iOS版もスクリプト化し、Xcode のビルド前フェーズか手動の手順にする。`*.xcframework` は `.gitignore` 済み
- 上の `--library` に `.a` を渡せるかは未確認（Android版は `.so` を渡している）。通らなければ `cdylib` の `.dylib` をホスト向けにビルドして渡す

### API（`core/limes-ffi/src/lib.rs`）

| 呼び出し | いつ | 備考 |
| --- | --- | --- |
| `Engine()` | 起動時に1つだけ | プロセス全体で共有 |
| `openStore(dir)` | 起動時 | 保存先フォルダ。中断した更新を片付け、保存済みの県をすべて開く |
| `localTime(year, month, day, hour, minute)` | 測位ごと | 日本時間（Asia/Tokyo）の日時から曜日・祝日を計算して返す |
| `locate(fix, time)` | 測位ごと | `GpsFix(lon, lat, heading, speedMps)`。道路が見つからなければ nil（「不明」） |
| `planUpdates(manifestJson, prefectures)` | 更新の確認 | `downloads`・`upToDate`・`appUpdateRequired`・`notPublished` |
| `installUpdate(download, filePath)` | ダウンロード後 | サイズ・sha256・展開後サイズ・メタを検証して切り替え。旧版は消える。合わなければ `DownloadMismatch` |
| `installedDatabases()` | 設定画面 | 県・版・容量 |
| `removePrefecture(slug)` | 削除 | 閉じてから消す |

- `locate` は SQLite を読むので、メインスレッドで呼ばない（Android版は専用のスレッド1本で呼ぶ。`…/drive/DriveModel.kt`）
- エラーのフィールド名は `detail`（Kotlin の `message` と衝突するため）

## 3. データの取得と更新

- 配信元：開発中は `https://pub-f67fb68aa5714cc7b4694371d04c0bf4.r2.dev/`。正式リリースまでに `https://limes.osprey74.app/` へ移す予定（CLAUDE.md「配信URL」。osprey74.com を使う案も検討中）。URL は設定値で持ち、差し替えられるようにする
- `manifest.json` を ETag 付きで取る。前回の本文と ETag を保存し、`If-None-Match` で 304 なら保存済みを使う（`…/data/DataServer.kt`）。オフライン時の容量表示にも保存済みを使う
- manifest の形式：`prefectures.<slug> = {version, schema_version, jartic_month, osm_date, path, size, sha256, raw_size}`。`path` は manifest からの相対パス
- 更新の流れ（`…/data/UpdateWorker.kt`）：選んだ県が空なら何もしない → manifest 取得（通信失敗は後で再試行）→ `planUpdates` → 各 `downloads` をキャッシュに落として `installUpdate` → 一時ファイルを消す。`DownloadMismatch` はその県だけ飛ばして次回に回す
- 起動時（自動更新がオンなら）と1日1回確認する。Android版は WorkManager。iOS は起動時・前面に戻ったときの確認に加え、`BGAppRefreshTask` を登録する（実行は OS 任せで保証されない）
- 「Wi-Fi 接続時のみ」（既定オン）：従量制の回線では待つ。iOS では `NWPathMonitor` の `isExpensive`／`isConstrained` で判断する
- 保存先：Android は `filesDir/databases`。iOS は Application Support 配下に置き、iCloud バックアップから外す（`isExcludedFromBackup`）のがよい（容量が大きく、いつでも取り直せるため）
- 県の一覧と地方：`…/data/Prefectures.kt`（slug は `data-pipeline/prefectures.json` と同じ。群馬は `gumma`）。地方の表示順は 北海道・東北・関東・中部・近畿・中国・四国・九州・沖縄
- 現在地の県を自動で追加（既定オン）：3km 動くか10分ごとに逆ジオコーディングで都道府県名を出し、持っていなければダウンロードする。iOS は `CLGeocoder` の `administrativeArea`。名前は「北海道」「東京都」のように Prefectures の `name` と照合する

## 4. 走行画面

- 位置情報は「使用中のみ」。走行画面が前面にある間だけ測位する（バックグラウンド測位はしない）。Android版は高精度・1秒間隔。iOS は `kCLLocationAccuracyBestForNavigation`、`activityType = .automotiveNavigation`
- 測位ごとに `localTime` → `locate`。速度は m/s → km/h（四捨五入）
- 向き（heading）は 2 m/s 以上のときだけ渡す。止まっているときの向きは当てにならず、照合を乱すため
- 測位が5秒来なければ「GPS 受信待ち」とし、最高速度も現在速度も「—」にする（トンネルなど）
- GPS の質：水平精度 20m 以下「GPS 良好」、50m 以下「GPS 精度低下」、それ以上「GPS 精度不足」
- 画面を常に点灯（既定オン）：走行画面の間だけ。iOS は `isIdleTimerDisabled`
- 縦・横の両方に対応（横は左に標識、右に現在速度）

### 標識の表示（`…/ui/DriveScreen.kt` の `SpeedSign`）

- 白い円＋赤い輪＋青い数字。輪の太さは直径の 20/220。数字は直径の 0.47（100以上は 0.40）、太字、字間を詰める
- 色：輪 `#D7262E`、数字 `#1D4E9E`。確度「低」は輪を淡い赤 `#EB9297` の実線にする（点線は継ぎ目がずれるのでやめた）
- 道路が見つからない：白地なしで灰色の輪（`#3A414B`）と「—」
- 標識の上に道路名：名前 → なければ国道（`highway` が `trunk` で始まり `ref` がある）は「国道◯号」→ どちらもなければ「道路名なし」
- 標識の下に確度の表示：棒3本（高3・中2・低1）と「確度 高／中／低」、根拠の文言

| 判定段（`stage`） | 根拠の文言 |
| --- | --- |
| 1 | 規制速度（JARTIC） |
| 2 | 高速自動車国道 |
| 3 | 自動車専用道路 |
| 4 | 中央分離帯あり |
| 5 | 中央線・車線（JARTIC）（確度高）／中央線・車線から推定（写真・OSM）（確度中） |
| 7 | 区画線なし（OSM） |
| それ以外（6 など） | コアが返す `reason` をそのまま |
| 道路なし | 道路を特定できません |

確度「低」の判定は段の番号より先に見る（低なら常に「中央線の証拠なし（安全側で30）」）。

- 画面下に常に：「表示される速度は公開データからの推定です。実際の最高速度は現地の標識・標示に従ってください。」
- 上部中央に「データ 2026年9月版」（保持データの最新の版）。持っていなければ「データ未取得」
- 速度超過の警告は出さない。カメラの標識認識もない（CLAUDE.md）

## 5. 起動画面

- OS の起動画面：背景色 `#0B0D10` とアイコンだけ（文字は置かない。HIG）
- 続いてアプリの画面：アイコン、「Limes」「リメス」、「道路状況や実際の交通規制にあわせ、安全運転を心がけましょう」を約1.5秒。タップで飛ばせる。毎回の起動で出す（`…/ui/LaunchScreen.kt`）
- アイコンはメーター（画面デザインの案C）。ベクターは `android/app/src/main/res/drawable/ic_launcher_foreground.xml`（108 グリッドの中央 72 に収まる）。色：背景 `#0B0D10`、目盛り帯 `#4A525E`、進んだ部分 `#34D3B8`、上限の目盛り `#D7262E`、針と中心 `#F2F4F7`

## 6. 設定画面とダウンロード画面

- 設定の並び：有料プラン（状態と「詳しく」）→ データの更新（自動更新、Wi-Fi 接続時のみ、最終確認、状態、「今すぐ更新を確認」）→ 保持データ（合計容量、地方ごとの横棒グラフ、地方を開くと県ごとの版・容量・状態と削除、現在地の県を自動で追加、ダウンロード画面へ）→ 運転支援（車種「普通自動車」、画面を常に点灯）→ 情報（バージョン、出典とライセンス、免責事項）
- 地方ごとのまとめて削除は、その地方に2県以上持っているときだけ出す
- 出典の文言（必須）：

```text
出典：『交通規制情報』（公益財団法人日本道路交通情報センター）（https://www.jartic.or.jp/service/opendata/）を加工して作成
道路データ：© OpenStreetMap contributors（ODbL）
祝日：内閣府「国民の祝日について」に基づき計算
```

- 免責事項：「表示される速度は公開データからの推定です。実際の最高速度は現地の道路標識・道路標示に従ってください。本アプリは速度違反の有無を保証しません。」
- 色の一覧は `…/ui/Theme.kt` の `Palette`（地の色 `#0B0D10`、カード `#15181D`、強調 `#C8F169`、良好 `#34D3B8`、待機 `#FFB020` など。地方ごとの色もここ）
- 画面デザイン（Claude.ai のキャンバス）：<https://claude.ai/artifact/EyFmB982XNvmo5xtBXGtqY>（走行・設定・ダウンロード・横画面・アイコン・起動画面）

## 7. 無料期間（`…/access/TrialClient.kt`・`Access.kt`）

- 最初のデータダウンロードのときに始まり、14日間。データを持っていない間は「開始前」で、全機能扱い
- 端末の識別：再インストールしても変わらない ID の SHA-256。Android は `"limes:" + ANDROID_ID`。iOS はキーチェーンに保存した UUID を使い、同じく `"limes:" + UUID` の SHA-256（小文字16進64桁）にする。キーチェーン項目は `kSecAttrAccessibleAfterFirstUnlock` などで、アプリを消しても残る種類にする
- サーバー：

```text
POST https://limes-trial.osprey74.workers.dev/v1/trial
{"id": "<64桁の16進>", "platform": "ios"}
→ 200 {"first_seen": "<ISO 8601>", "trial_ends": "<ISO 8601>"}
```

- サーバーにつながらないときは端末の時計で14日を数え始め、「未確認」の印を付ける。次の判定でサーバーに聞き直し、サーバーの終了日が早ければそちらを使う（再インストールで延ばさせない）
- 終了日は端末に保存し、以後の判定は端末の時計で行う
- URL は正式リリースまでに `https://limes-trial.osprey74.app/v1/trial` へ移す予定（設定値で持つ）

## 8. 課金（StoreKit 2）

- Android版の商品：定期購入 `premium`、基本プラン `monthly`（1か月）・`yearly`（1年）。ストアの無料体験（お試しオファー）は付けない（無料期間はアプリ側）
- iOS では、サブスクリプショングループ1つに月額・年額の2つのプロダクトを作る。プロダクト ID は未決定（例：`com.osprey74.limes.premium.monthly`／`.yearly`）。価格は App Store Connect で設定し、アプリには書かない（ストアから受け取る）
- 価格ポイントに望みの金額があるかは App Store Connect で確かめる（未確認）
- 有料プラン画面（`…/ui/SubscribeScreen.kt`）：状態（無料期間の残り日数と終了日／終了／登録済み）、できること（最高速度の表示、データのダウンロードと自動更新）、「登録しなくても、GPS による現在の速度はいつでも表示されます」、月額・年額と登録ボタン（年額は「月あたり◯円（月額の12か月分より◯%お得）」をストアの価格から計算）、自動更新と解約方法の説明、「定期購入を管理」（iOS は `showManageSubscriptions` か App Store の管理画面）
- 「購入を復元」ボタンは App Store では必要とされることが多い（審査ガイドライン 3.1.1 の扱いは要確認）。StoreKit 2 なら `AppStore.sync()`

## 9. 利用状態と制限

状態は4つ：開始前、無料期間中、登録済み、期間終了。起動時と前面に戻ったときに判定する。

| 状態 | 最高速度 | ダウンロード・更新 | 自動追加 |
| --- | --- | --- | --- |
| 開始前・無料期間中・登録済み | 表示 | する | する |
| 期間終了 | 出さない（現在速度のみ） | しない | しない |

- 期間終了の走行画面：標識の代わりに「最高速度の表示は有料プランの機能です」「無料期間が終わりました。現在の速度はこのまま表示されます。」と［有料プランを見る］。運転中に画面を切り替えない
- 有料プラン画面を自動で出すのは、期間終了のときの起動直後に1回だけ
- ダウンロード画面には「無料期間が終わったため、ダウンロードできません。設定の「有料プラン」から登録できます。」
- ストアに問い合わせられないとき：直近60日以内に登録を確認できていれば登録済みとして扱い、データも消さない
- 保持データの削除：
  - 無料期間だけで登録しなかった → 期間終了の時点で削除
  - 登録していた → 最後に有効な登録を確認してから60日後に削除（Android は猶予期間とアカウント保留を端末から区別できないため）。iOS は StoreKit 2 の `Product.SubscriptionInfo.RenewalState` で `.inGracePeriod`・`.inBillingRetryPeriod` を判別できるはずなので、その間は消さず、`.expired`・`.revoked` で消す形にできる（要確認。60日の目安と併用してよい）
  - 削除したら、有料プラン画面で一度だけ「無料期間が終わったため、保存していた道路データを削除しました。登録すると、もう一度ダウンロードできます。」と知らせる
- 作者用の解放手段は入れない（CLAUDE.md、ガイドライン 3.1.1）

## 10. Android版で確かめたこと（2026-11-11）

- 無料期間の開始とサーバーへの記録、価格の表示、テスト購入、登録済みの表示
- テスト購入が終わると無料期間に戻る
- 端末の日付を進めて、期間終了の制限（データは残る）→ 60日後の削除とお知らせ

iOS版でも Sandbox と StoreKit の設定ファイル（Xcode の StoreKit テスト）で同じ順に確かめるとよい。

## 11. 公開前に要るもの（両OS共通）

- プライバシーポリシー（置き場所は `limes.osprey74.app/privacy` などを予定）
- App Store のプライバシー情報：端末の識別子（ハッシュ）を無料期間の管理のために送る。位置情報は端末の外に出さない（測位は端末内で判定に使うだけ）
- 審査メモ：運転中の利用を前提とするアプリであること、速度超過の警告を出さないこと、表示は推定であることの説明
