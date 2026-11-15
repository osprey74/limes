# Android版 引き継ぎ資料

iOS版の準備で Android版（`android/`）のコードを読んだときに見つけた、Android版の開発環境で直す項目。コードの場所は `android/app/src/main/java/com/osprey74/limes/` 以下を `…/` と略す。

作成：2026-11-14（コミット a925a08 時点。コードを読んで見つけたもので、実機では再現させていない）

## 1. 更新の途中で通信が切れると、入れ終えた県が一覧に出ない

状態：修正済み（2026-11-15。エミュレーターで「確かめ方」の手順どおりに確認した）

### 起きること

複数の県を続けて更新している途中で、2県目以降のダウンロードが通信エラーになると、それまでに入れ終えた県が設定画面の「保持データ」とダウンロード画面の「保持済み」に出ない。走行画面上部の「データ ◯年◯月版」も古いままになる。再試行が成功するか、アプリを起動し直すと出る。

最高速度の判定には影響しない。入れ終えた県は `installUpdate` の時点でコアが開いているので、新しいデータで判定される。

### 原因

`…/data/UpdateWorker.kt` の `doWork()`。ダウンロードのループの中で `IOException` を受けると `return Result.retry()` でそのまま戻る（50行目）。一覧を読み直す `app.data.refreshInstalled()` はループのあと（56行目）にしかないので、途中で戻ると呼ばれない。

```kotlin
} catch (e: IOException) {
    return Result.retry()   // ここで戻ると refreshInstalled() を通らない
} finally {
    file.delete()
}
```

### 直し方の案

`Result.retry()` で戻る前に `app.data.refreshInstalled()` を呼ぶ。`setLastChecked` は呼ばない（確認が終わっていないため、「最終確認」は進めない）。

```kotlin
} catch (e: IOException) {
    app.data.refreshInstalled()
    return Result.retry()
}
```

### 確かめ方

1. 県を2つ以上選んでダウンロードを始める
2. 1県目が終わったところで通信を切る（機内モード）
3. 設定画面の「保持データ」に1県目が出ていること、「最終確認」が進んでいないことを見る
4. 通信を戻し、残りの県が入ることを見る

## 2. コメントの食い違い（動作は正しい）

状態：修正済み（2026-11-15）

`…/data/Settings.kt` の `autoAddCurrent` のコメントは「Add the prefecture the car is in and its neighbours」だが、実装（`…/drive/DriveModel.kt` の `maybeAddCurrentPrefecture`）が追加するのは今いる県だけ。県境を越えると、越えた先の県が「今いる県」になって追加される。コメントを実装に合わせる。

設定画面の説明「県境を越えると隣の県も取得します」は実装どおりなので、変えない。

## 3. 年額プランの「◯%お得」が切り上がる

状態：修正済み（2026-11-15。iOS版の課金を実装したときにコードを読んで見つけたもので、実機では見ていない）

`…/ui/SubscribeScreen.kt` の `yearlyNote`（160行目）。年額が月額12か月分の何%にあたるかを整数の割り算で切り捨ててから100から引くので、割引率は切り上がる。例：月額500円・年額5,000円なら実際は16.67%だが「17%お得」と出る。割り切れる価格（例：月額500円・年額4,800円で20%）では差は出ない。

```kotlin
val saving = (100 - yearly.priceMicros * 100 / (monthly.priceMicros * 12)).toInt()
```

直し方の案：割引率のほうを切り捨てる（iOS版は切り捨てにしてある。`ios/Limes/Access/SubscribeScreen.swift` の `yearlyNote`）。

```kotlin
val full = monthly.priceMicros * 12
val saving = ((full - yearly.priceMicros) * 100 / full).toInt()
```
