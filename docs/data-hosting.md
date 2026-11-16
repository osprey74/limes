# データ配信の構成

アプリが読むデータをどこから配るか。決めたこと、確かめたこと、進み具合、残っている作業をまとめる。

作成：2026-11-15

## 1. 決めたこと（2026-11-15）

- アプリが読む `manifest.json` と県別データは、お名前.com のレンタルサーバー（RS プラン）から配る。URL は `https://limes.osprey74.com/data/`
- Cloudflare R2 は自動処理の保存場所として残す（前回の状態 `state.json`、検証の基準値 `stats/`、JARTIC の元 ZIP `archive/jartic/`、県別データ）。アプリからは接続しない
- 無料期間の記録（Workers＋D1）は `limes-trial.osprey74.workers.dev` のまま使う
- `osprey74.app` は取得しない。`osprey74.com` のネームサーバーも Cloudflare に移さない

理由：

- R2 の `r2.dev` は、Cloudflare が「レート制限があり、開発目的でのみ使う」としている。R2 に独自ドメインを付けるには、そのドメインを Cloudflare のゾーンにする必要がある
- `osprey74.com` のネームサーバーを Cloudflare に移すと、お名前.com レンタルサーバーの無料 SSL の条件（指定ネームサーバー）から外れ、既存サイトの SSL を作り直すことになる
- `osprey74.app` を取っても、Cloudflare 管理ではメールの送信ができず、`osprey74.com` より使い道が狭い
- お名前.com のサーバーは契約済みで、転送量は無制限、無料 SSL が使える
- `workers.dev` は Cloudflare が「個人・趣味のプロジェクト向け」としていて、Limes はこれに当たる。Android・iOS の既定の User-Agent が `workers.dev` のチェックで止められないことを確かめた（下の 3）

## 2. データの流れ

毎日の自動処理（`.github/workflows/data-release.yml`）：

1. GitHub Actions が JARTIC と OpenStreetMap のデータを取得し、ビルドと検証を行う
2. 結果を R2 に保存する（県別データが先、`manifest.json` と `state.json` が後）。古い世代を消す
3. `mirror` が、R2 にある `manifest.json` と県別データをお名前.com の `data` フォルダへ FTPS で写す。県別データが先、`manifest.json` が後。そのあと、R2 に無い県別データを消す
4. `mirror` が、公開 URL の `manifest.json` が R2 のものと一致することと、47県のデータが `manifest.json` に書かれた大きさで取れることを確かめる

アプリ：

- 起動時などに `manifest.json` を取りに行き、変わっていれば県別データを取得する（HTTPS）
- 最初のデータダウンロードのときに、端末 ID のハッシュを Workers へ送り、無料期間の終了日を受け取る

新しい規制情報が出ていない日は、`mirror` は動かない。手動実行で `mirror_only` を選ぶと、写す処理だけを動かせる。

## 3. 確かめたこと（2026-11-15）

お名前.com のサーバー（実データで試験）：

- `.sqlite.zst` は `application/zstd` として、変換されずに返る。取得したファイルの SHA-256 が `manifest.json` の値と一致した（北海道・東京・沖縄）
- 途中からの取得（Range）に対応している
- Android（`Dalvik/…`）と iOS（`CFNetwork/…`）の既定の User-Agent で取得できる
- 手前の nginx が応答を一時的に保存する。何も指定しないと、`manifest.json` を差し替えた直後は古い内容が返る（差し替えの13秒後に古い内容を確認。約80秒以内に新しい内容へ変わった。正確な保持時間は未計測）
- `data-pipeline/publish/htaccess` で `manifest.json` に `Cache-Control: no-cache` を付けると、差し替えた直後から新しい内容が返る
- その代わり、`no-cache` を付けた状態では、ETag が同じでも 304 ではなく 200 で全文が返る。1回あたり約3.5 KB（gzip 時）。アプリは 200 でも 304 でも同じように動く（`android/…/data/DataServer.kt`）
- `.htaccess` は外から読めない（404）。フォルダの一覧も見えない（403）
- サブドメインの作成から約3分で DNS に登録され、無料 SSL は申し込みから数分で有効になった。証明書は AlphaSSL、有効期間は199日（2027-06-02 まで）。期限の30日前から自動更新される

Workers（`workers.dev`）：

- ブラウザ整合性チェックは働いている（`Python-urllib` の User-Agent は 403、エラー 1010）
- Android と iOS の既定の User-Agent、User-Agent なしは、Workers まで届いた

アプリ（Android のコードで確認。iOS は未確認）：

- データの取得に失敗したら、あとで再試行する（`UpdateWorker.kt`）
- 無料期間の記録に失敗したら、その時点から数え、あとで照合する（`Access.kt`）
- 取得したデータは、大きさと SHA-256 を検証してから切り替える

## 4. 設定

| 場所 | 項目 | 内容 |
| --- | --- | --- |
| お名前.com | サブドメイン | `limes.osprey74.com`（2026-11-15 作成、無料 SSL 設定済み） |
| お名前.com | FTP アカウント | Limes 専用。`limes.osprey74.com` のフォルダの中だけに届く |
| GitHub | シークレット `MIRROR_FTP_USER`・`MIRROR_FTP_PASSWORD` | 上の専用アカウント |
| GitHub | 変数 `MIRROR_FTP_DIR` | `/data`（専用アカウントから見た場所） |
| ワークフロー | `FTP_HOST` | `www1135.onamae.ne.jp`。サーバーの証明書の名義が `*.onamae.ne.jp` なので、`osprey74.com` の名前では FTPS で接続できない |

`MIRROR_FTP_DIR` が `/data` で終わらないと、`mirror` は何もせずに止まる（古いデータを消す処理が別のフォルダに及ばないようにするため）。

## 5. 進み具合

- [x] `limes.osprey74.com` の作成、SSL の設定、専用 FTP アカウントの作成（2026-11-15）
- [x] `mirror` の追加（コミット `fa8696a`）
- [x] 最初の全県コピー（2026-11-15 21:10〜21:17、約7分）。`data` フォルダに県別データ94件（47県 × 2世代、約1.39 GB）、`manifest.json`、`.htaccess`
- [x] 公開 URL の `manifest.json` が R2 と一致することを確認

- [x] Android 版の配信 URL を `https://limes.osprey74.com/data/` に変更（2026-11-16。`android/app/build.gradle.kts` の `DATA_BASE_URL`）
- [x] データの取得先の名前の書き換え（2026-11-16）。`docs/release-prep.md`（1 の表、2、3）と `site/privacy/index.html`（5. 外部サービスとの通信）を、お名前.com のレンタルサーバー（運営：GMOインターネット株式会社）に直した。事実に合わせるだけの修正で、ストアの申告の内容は変えていない（2026-11-15決定。県名入りのファイル名の取得要求は、申告を変えるほどの情報ではないと判断。サーバーのアクセス記録の有無も調べない）
- [x] iOS 版の配信 URL を `https://limes.osprey74.com/data/` に変更（2026-11-16。`ios/Limes/Config.swift` の `dataBaseURL`）。シミュレーターで起動し、アプリが取得した `manifest.json` が公開 URL のものと一致することを確かめた。関東7県（茨城・栃木・群馬・埼玉・千葉・東京・神奈川）をアプリからダウンロードし、展開後の大きさが `manifest.json` の値と一致することも確かめた

## 6. 残っている作業

1. （済み。5 を参照）
2. （済み。5 を参照）
3. （済み。2026-11-16）R2 の `r2.dev` での公開を止めた。`r2.dev` の URL は `manifest.json`・`state.json`・県別データとも 401 を返し、`https://limes.osprey74.com/data/manifest.json` は 200 のままであることを確かめた。バケットの中身は外から取れなくなった
4. ストアにプライバシーポリシーの URL `https://limes.osprey74.com/privacy/` を登録する。ページは 2026-11-16 に公開した（リポジトリの `site/privacy/index.html` と一致、`text/html; charset=UTF-8`）。置き方は自動（2026-11-16決定）：`site/` を変えたコミットが `main` に入ると、`.github/workflows/site.yml` が `mirror` と同じ FTP アカウントでアップロードし、公開されたページがリポジトリの内容と一致することを確かめる。ファイルは足すか置き換えるだけで、消さない。`data` フォルダには触れない
5. 定期実行が止まることへの備え。公開リポジトリでは、60日間リポジトリに動きがないと、定期実行が自動で無効になる（GitHub の仕様）。止まらないようにする細工（空コミット、API での有効化）はしない。GitHub の外から見張って気づき、手で再開する（2026-11-16決定）：`server/` の Workers が1日1回（12:00 JST）、`data-release` の状態と最後の定期実行の日時を見て、有効でないか3日以上動いていなければ、リポジトリに Issue を立てる（`server/src/watch.ts`）。再開は Actions の画面の「Enable workflow」か `gh workflow enable data-release.yml`。2026-11-16 にトークン（`osprey74/limes` のみ、Issues の読み書きと Actions の読み取り、期限なし）を登録してデプロイした。Cloudflare 上で定期処理を一度手動で動かし、GitHub と配信先を読んで「問題なし」と判定することを確かめた。実際に Issue が立つところは試していない（`server/README.md`）
6. （コードは済み。実際の定期実行ではまだ確かめていない）証明書の期限切れに気づく仕組み。`mirror` の確認は `mirror` が動いた日にしか行われない。切れる前に気づく仕組み（2026-11-16）：`data-release` の `certificate` ジョブが毎日（新しい規制情報がない日も）証明書の期限を読み、残りが21日を切ると Issue を立てる。自動更新は30日前から始まるので、21日を切っていれば更新が進んでいない。期限を読めなかった日はジョブが失敗する。切れたあとは、5 の見張りが `manifest.json` を HTTPS で取れないことでも気づける
7. （済み。2026-11-16）アプリから独自の User-Agent を送る。`workers.dev` のチェックの対象が将来変わることへの備え。値は `Limes/<アプリの版> (Android)`・`Limes/<アプリの版> (iOS)` で、端末の機種や OS の版は入れない（`android/…/UserAgent.kt`、`ios/Limes/Config.swift` の `userAgent`）。データの取得と無料期間の記録の両方に付ける。この値でお名前.com のサーバーから取得でき、Workers まで届くことを確かめた。iOS 版は Xcode でビルドでき、この値で `manifest.json` を取得できた（2026-11-16、シミュレーター）。無料期間の記録も、アプリが覚えている終了日を消して起動し直すと、Workers から同じ終了日を受け取り直した（同日、シミュレーター）。実機ではまだ確かめていない

## 7. 未確認のこと

- お名前.com のサーバーの同時接続数の上限（公式の機能一覧に記載なし。負荷をかける試験はしていない）
- iOS 版の、取得に失敗したときの動き
- `ETag` が同じでも 200 が返る原因（nginx の仕組みによると見ているが、特定していない）
