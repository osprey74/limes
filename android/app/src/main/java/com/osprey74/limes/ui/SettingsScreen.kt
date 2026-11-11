package com.osprey74.limes.ui

import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.KeyboardArrowDown
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.rotate
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.work.WorkInfo
import androidx.work.WorkManager
import com.osprey74.limes.BuildConfig
import com.osprey74.limes.LimesApp
import com.osprey74.limes.access.AccessState
import com.osprey74.limes.data.Installed
import com.osprey74.limes.data.Published
import com.osprey74.limes.data.REGIONS
import com.osprey74.limes.data.UpdateWorker
import com.osprey74.limes.data.prefecture
import com.osprey74.limes.data.sizeLabel
import com.osprey74.limes.data.versionLabel
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.launch
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneId
import java.time.format.DateTimeFormatter

const val DISCLAIMER =
    "表示される速度は公開データからの推定です。実際の最高速度は現地の道路標識・道路標示に従ってください。本アプリは速度違反の有無を保証しません。"

const val ATTRIBUTION =
    "出典：『交通規制情報』（公益財団法人日本道路交通情報センター）（https://www.jartic.or.jp/service/opendata/）を加工して作成\n" +
        "道路データ：© OpenStreetMap contributors（ODbL）\n" +
        "祝日：内閣府「国民の祝日について」に基づき計算"

@Composable
fun SettingsScreen(app: LimesApp, onBack: () -> Unit, onDownload: () -> Unit, onSubscribe: () -> Unit) {
    val scope = rememberCoroutineScope()
    val installed by app.data.installed.collectAsState()
    val published by app.data.published.collectAsState()
    val lastUpdate by app.data.lastUpdate.collectAsState()
    val autoUpdate by app.settings.autoUpdate.collectAsState(initial = true)
    val wifiOnly by app.settings.wifiOnly.collectAsState(initial = true)
    val autoAdd by app.settings.autoAddCurrent.collectAsState(initial = true)
    val keepAwake by app.settings.keepAwake.collectAsState(initial = true)
    val lastChecked by app.settings.lastChecked.collectAsState(initial = 0L)
    val access by app.access.state.collectAsState()
    val work by remember(lastUpdate) {
        lastUpdate?.let { WorkManager.getInstance(app).getWorkInfoByIdFlow(it) } ?: flowOf(null)
    }.collectAsState(initial = null)

    LaunchedEffect(Unit) {
        app.data.refreshInstalled()
        app.data.loadPublished()
    }
    LaunchedEffect(work?.state) {
        if (work?.state?.isFinished == true) {
            app.data.refreshInstalled()
            app.data.loadPublished()
        }
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(Palette.Ground)
            .verticalScroll(rememberScrollState())
            .statusBarsPadding()
            .padding(start = 16.dp, end = 16.dp, top = 16.dp, bottom = 40.dp),
        verticalArrangement = Arrangement.spacedBy(24.dp),
    ) {
        Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
            BackButton("走行画面", onBack)
            Text("設定", color = Palette.Text, fontSize = 30.sp, fontWeight = FontWeight.Bold)
        }

        Section("有料プラン") {
            CardRow(first = true, onClick = onSubscribe) {
                Text(planLabel(access), color = Palette.Text, fontSize = 15.sp, modifier = Modifier.weight(1f))
                Text("詳しく", color = Palette.Muted, fontSize = 14.sp)
            }
        }

        Section("データの更新") {
            ToggleRow("自動更新", "起動時と1日1回、新しい版を確認して取得します", autoUpdate, first = true) {
                scope.launch {
                    app.settings.setAutoUpdate(it)
                    app.data.applyUpdateSettings()
                }
            }
            ToggleRow("Wi-Fi 接続時のみ", "モバイル回線のときは待機し、Wi-Fi につながると取得します", wifiOnly) {
                scope.launch {
                    app.settings.setWifiOnly(it)
                    app.data.applyUpdateSettings()
                }
            }
            CardRow {
                Text("最終確認", color = Palette.Text, fontSize = 15.sp, modifier = Modifier.weight(1f))
                Text(checkedLabel(lastChecked), color = Palette.Muted, fontSize = 14.sp)
            }
            updateStatus(work, wifiOnly)?.let { (text, color) ->
                CardRow { StatusLabel(text, color) }
            }
            Column(Modifier.padding(16.dp)) {
                FlatButton("今すぐ更新を確認", Modifier.fillMaxWidth()) { scope.launch { app.data.checkNow() } }
            }
        }

        StorageSection(
            installed = installed,
            published = published,
            wifiOnly = wifiOnly,
            autoAdd = autoAdd,
            onAutoAdd = { scope.launch { app.settings.setAutoAddCurrent(it) } },
            onRemove = { app.data.remove(it) },
            onDownload = onDownload,
        )

        Section("運転支援") {
            CardRow(first = true) {
                Text("車種", color = Palette.Text, fontSize = 15.sp, modifier = Modifier.weight(1f))
                Text("普通自動車", color = Palette.Muted, fontSize = 14.sp)
            }
            ToggleRow("画面を常に点灯", checked = keepAwake) { scope.launch { app.settings.setKeepAwake(it) } }
        }

        Section("情報") {
            CardRow(first = true, minHeight = 52) {
                Text("アプリのバージョン", color = Palette.Text, fontSize = 15.sp, modifier = Modifier.weight(1f))
                Text(BuildConfig.VERSION_NAME, color = Palette.Muted, fontSize = 14.sp)
            }
            ExpandableText("データの出典とライセンス", ATTRIBUTION)
            ExpandableText("免責事項", DISCLAIMER)
        }

        Text(DISCLAIMER, color = Palette.Muted, fontSize = 12.sp, lineHeight = 20.sp, modifier = Modifier.padding(horizontal = 4.dp))
    }
}

private fun planLabel(access: AccessState?): String = when (access) {
    AccessState.NotStarted -> "無料期間（最初のダウンロードから14日間）"
    is AccessState.Trial -> {
        val date = Instant.ofEpochMilli(access.ends).atZone(ZoneId.of("Asia/Tokyo")).format(DateTimeFormatter.ofPattern("M月d日"))
        "無料期間中（${date}まで）"
    }
    AccessState.Subscribed -> "登録済み"
    AccessState.Expired -> "無料期間終了（未登録）"
    null -> "確認しています…"
}

private fun checkedLabel(millis: Long): String {
    if (millis == 0L) return "未確認"
    val zone = ZoneId.of("Asia/Tokyo")
    val time = Instant.ofEpochMilli(millis).atZone(zone)
    val clock = time.format(DateTimeFormatter.ofPattern("H:mm"))
    return if (time.toLocalDate() == LocalDate.now(zone)) "今日 $clock" else time.format(DateTimeFormatter.ofPattern("M月d日 H:mm"))
}

/** What the update last started is doing; null when there is nothing to say. */
private fun updateStatus(work: WorkInfo?, wifiOnly: Boolean): Pair<String, Color>? = when (work?.state) {
    WorkInfo.State.ENQUEUED, WorkInfo.State.BLOCKED ->
        (if (wifiOnly) "Wi-Fi の接続を待っています" else "通信の接続を待っています") to Palette.Waiting
    WorkInfo.State.RUNNING -> {
        val slug = work.progress.getString(UpdateWorker.KEY_PREFECTURE)
        val total = work.progress.getInt(UpdateWorker.KEY_TOTAL, 0)
        val done = work.progress.getInt(UpdateWorker.KEY_DONE, 0)
        (if (slug == null) "新しい版を確認しています" else "${prefecture(slug)?.name ?: slug}を取得しています（${done + 1}/$total）") to Palette.Accent
    }
    WorkInfo.State.SUCCEEDED -> {
        val n = work.outputData.getInt(UpdateWorker.KEY_INSTALLED, 0)
        val bad = work.outputData.getInt(UpdateWorker.KEY_MISMATCHED, 0)
        val appUpdate = work.outputData.getInt(UpdateWorker.KEY_APP_UPDATE, 0)
        when {
            appUpdate > 0 -> "新しいデータを使うにはアプリの更新が必要です" to Palette.Waiting
            bad > 0 -> "${bad} 件の取得に失敗しました。次回の確認で再取得します" to Palette.Waiting
            n > 0 -> "${n} 件を更新しました" to Palette.Ok
            else -> "すべて最新です" to Palette.Ok
        }
    }
    WorkInfo.State.FAILED -> "更新に失敗しました" to Palette.Danger
    WorkInfo.State.CANCELLED, null -> null
}

private class RegionUsage(val name: String, val color: Color, val prefs: List<Installed>) {
    val bytes = prefs.sumOf { it.bytes }
}

@Composable
private fun StorageSection(
    installed: List<Installed>,
    published: Map<String, Published>,
    wifiOnly: Boolean,
    autoAdd: Boolean,
    onAutoAdd: (Boolean) -> Unit,
    onRemove: (List<String>) -> Unit,
    onDownload: () -> Unit,
) {
    val regions = REGIONS.mapIndexed { i, name ->
        RegionUsage(name, Palette.Regions[i], installed.filter { prefecture(it.slug)?.region == name })
    }.filter { it.bytes > 0 }
    val total = regions.sumOf { it.bytes }
    var open by remember { mutableStateOf<String?>(null) }
    var confirm by remember { mutableStateOf<String?>(null) }

    Section("保持データ", trailing = {
        Text("合計 ${sizeLabel(total)}", color = Palette.Muted, fontSize = 12.sp)
    }) {
        if (total == 0L) {
            Text(
                "保持しているデータはありません。走行する地域のデータをダウンロードしてください。",
                color = Palette.Muted, fontSize = 14.sp, lineHeight = 22.sp,
                modifier = Modifier.padding(horizontal = 16.dp, vertical = 20.dp),
            )
        } else {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                // One bar for the total, a segment per region.
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(14.dp)
                        .clip(RoundedCornerShape(7.dp))
                        .background(Palette.Line)
                        .semantics {
                            contentDescription = "保持データ 合計 ${sizeLabel(total)}：" +
                                regions.joinToString("、") { "${it.name} ${sizeLabel(it.bytes)}" }
                        },
                    horizontalArrangement = Arrangement.spacedBy(2.dp),
                ) {
                    regions.forEach { Box(Modifier.weight(it.bytes.toFloat()).fillMaxHeight().background(it.color)) }
                }
                regions.chunked(2).forEach { pair ->
                    Row(horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                        pair.forEach { r ->
                            Row(Modifier.weight(1f), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                                Box(Modifier.size(8.dp).clip(RoundedCornerShape(2.dp)).background(r.color))
                                Text(r.name, color = Palette.Sub, fontSize = 12.sp, modifier = Modifier.weight(1f))
                                Text(sizeLabel(r.bytes), color = Palette.Muted, fontSize = 12.sp)
                            }
                        }
                        if (pair.size == 1) Spacer(Modifier.weight(1f))
                    }
                }
            }
            regions.forEach { r ->
                RegionRow(
                    region = r,
                    total = total,
                    open = open == r.name,
                    confirm = confirm,
                    published = published,
                    wifiOnly = wifiOnly,
                    onToggle = {
                        open = if (open == r.name) null else r.name
                        confirm = null
                    },
                    onConfirm = { confirm = it },
                    onRemove = {
                        onRemove(it)
                        confirm = null
                    },
                )
            }
        }
        ToggleRow("現在地の都道府県を自動で追加", "県境を越えると隣の県も取得します", autoAdd, onChange = onAutoAdd)
        CardRow(minHeight = 52, onClick = onDownload) {
            Icon(Icons.Default.Add, contentDescription = null, tint = Palette.Accent, modifier = Modifier.size(18.dp))
            Text("地方・都道府県のデータをダウンロード", color = Palette.Accent, fontSize = 15.sp, fontWeight = FontWeight.Medium)
        }
    }
}

@Composable
private fun RegionRow(
    region: RegionUsage,
    total: Long,
    open: Boolean,
    confirm: String?,
    published: Map<String, Published>,
    wifiOnly: Boolean,
    onToggle: () -> Unit,
    onConfirm: (String?) -> Unit,
    onRemove: (List<String>) -> Unit,
) {
    val chevron by animateFloatAsState(if (open) 180f else 0f, label = "chevron")
    Column {
        Box(Modifier.fillMaxWidth().height(1.dp).background(Palette.Line))
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .clickable(role = Role.Button, onClickLabel = if (open) "閉じる" else "開く", onClick = onToggle)
                .heightIn(min = 60.dp)
                .padding(horizontal = 16.dp, vertical = 10.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Box(Modifier.size(8.dp).clip(RoundedCornerShape(2.dp)).background(region.color))
                Text(region.name, color = Palette.Text, fontSize = 15.sp)
                Text("${region.prefs.size} 件", color = Palette.Muted, fontSize = 12.sp, modifier = Modifier.weight(1f))
                Text(sizeLabel(region.bytes), color = Palette.Text, fontSize = 15.sp, fontWeight = FontWeight.SemiBold)
                Icon(Icons.Default.KeyboardArrowDown, contentDescription = null, tint = Palette.Muted, modifier = Modifier.size(20.dp).rotate(chevron))
            }
            Box(Modifier.fillMaxWidth().height(6.dp).clip(RoundedCornerShape(3.dp)).background(Palette.Line)) {
                Box(Modifier.fillMaxWidth(region.bytes.toFloat() / total).fillMaxHeight().clip(RoundedCornerShape(3.dp)).background(region.color))
            }
        }
        if (open) {
            Column(Modifier.padding(start = 16.dp, end = 16.dp, bottom = 12.dp)) {
                region.prefs.forEach { p ->
                    val name = prefecture(p.slug)?.name ?: p.slug
                    Box(Modifier.fillMaxWidth().height(1.dp).background(Palette.Inset))
                    Row(
                        modifier = Modifier.fillMaxWidth().heightIn(min = 56.dp),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(10.dp),
                    ) {
                        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                            Text(name, color = Palette.Text, fontSize = 14.sp)
                            Text("${versionLabel(p.version)} ・ ${sizeLabel(p.bytes)}", color = Palette.Muted, fontSize = 12.sp)
                        }
                        if (confirm == p.slug) {
                            FlatButton("やめる") { onConfirm(null) }
                            FlatButton("削除", filled = Palette.Danger) { onRemove(listOf(p.slug)) }
                        } else {
                            published[p.slug]?.let { pub ->
                                if (pub.version == p.version) {
                                    StatusLabel("最新", Palette.Ok)
                                } else {
                                    StatusLabel(if (wifiOnly) "更新待ち（Wi-Fi）" else "更新待ち", Palette.Waiting)
                                }
                            }
                            IconButton(onClick = { onConfirm(p.slug) }) {
                                Icon(Icons.Default.Delete, contentDescription = "${name}のデータを削除", tint = Palette.Muted)
                            }
                        }
                    }
                }
                // Bulk delete only when the region holds two or more prefectures.
                if (region.prefs.size >= 2) {
                    val key = "region:${region.name}"
                    if (confirm == key) {
                        Column(
                            modifier = Modifier.padding(top = 8.dp).fillMaxWidth().clip(ButtonShape).background(Palette.Inset).padding(12.dp),
                            verticalArrangement = Arrangement.spacedBy(10.dp),
                        ) {
                            Text(
                                "${region.name}の ${region.prefs.size} 件（${sizeLabel(region.bytes)}）を削除します。走行中にこの地方では速度を表示できなくなります。",
                                color = Palette.Sub, fontSize = 13.sp, lineHeight = 20.sp,
                            )
                            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                FlatButton("やめる", Modifier.weight(1f)) { onConfirm(null) }
                                FlatButton("すべて削除", Modifier.weight(1f), filled = Palette.Danger) { onRemove(region.prefs.map { it.slug }) }
                            }
                        }
                    } else {
                        FlatButton("${region.name}のデータをすべて削除", Modifier.padding(top = 8.dp).fillMaxWidth(), textColor = Palette.DangerText) {
                            onConfirm(key)
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun ExpandableText(title: String, body: String) {
    var open by remember { mutableStateOf(false) }
    val chevron by animateFloatAsState(if (open) 180f else 0f, label = "chevron")
    CardRow(minHeight = 52, onClick = { open = !open }) {
        Text(title, color = Palette.Text, fontSize = 15.sp, modifier = Modifier.weight(1f))
        Icon(Icons.Default.KeyboardArrowDown, contentDescription = null, tint = Palette.Muted, modifier = Modifier.size(20.dp).rotate(chevron))
    }
    if (open) {
        Text(body, color = Palette.Sub, fontSize = 13.sp, lineHeight = 21.sp, modifier = Modifier.padding(start = 16.dp, end = 16.dp, bottom = 14.dp))
    }
}
