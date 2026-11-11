package com.osprey74.limes.ui

import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.KeyboardArrowDown
import androidx.compose.material3.Checkbox
import androidx.compose.material3.CheckboxDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.material3.TriStateCheckbox
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
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.state.ToggleableState
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.osprey74.limes.LimesApp
import com.osprey74.limes.access.entitled
import com.osprey74.limes.data.PREFECTURES
import com.osprey74.limes.data.Prefecture
import com.osprey74.limes.data.Published
import com.osprey74.limes.data.REGIONS
import com.osprey74.limes.data.sizeLabel
import kotlinx.coroutines.launch

private val checkboxColors
    @Composable get() = CheckboxDefaults.colors(
        checkedColor = Palette.Accent,
        uncheckedColor = Palette.Faint,
        checkmarkColor = Palette.Ground,
    )

@Composable
fun DownloadScreen(app: LimesApp, onBack: () -> Unit) {
    val scope = rememberCoroutineScope()
    val published by app.data.published.collectAsState()
    val installed by app.data.installed.collectAsState()
    val wifiOnly by app.settings.wifiOnly.collectAsState(initial = true)
    val access by app.access.state.collectAsState()
    var selected by remember { mutableStateOf(emptySet<String>()) }
    var open by remember { mutableStateOf<String?>(null) }
    val held = installed.map { it.slug }.toSet()

    LaunchedEffect(Unit) { app.data.loadPublished() }

    val chosen = selected.mapNotNull { published[it] }
    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(Palette.Ground)
            .verticalScroll(rememberScrollState())
            .statusBarsPadding()
            .padding(start = 16.dp, end = 16.dp, top = 16.dp, bottom = 40.dp),
        verticalArrangement = Arrangement.spacedBy(20.dp),
    ) {
        Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
            BackButton("設定", onBack)
            Text("データのダウンロード", color = Palette.Text, fontSize = 26.sp, fontWeight = FontWeight.Bold)
            Text(
                "走行する地域のデータを端末に保存します。保存したデータで判定するので、走行中は通信しません。",
                color = Palette.Sub, fontSize = 14.sp, lineHeight = 23.sp,
            )
        }

        if (access?.entitled == false) {
            Text(
                "無料期間が終わったため、ダウンロードできません。設定の「有料プラン」から登録できます。",
                color = Palette.Waiting, fontSize = 14.sp, lineHeight = 22.sp,
            )
        }

        Column(Modifier.clip(CardShape).background(Palette.Card)) {
            ToggleRow("Wi-Fi 接続時のみ", "モバイル回線のときは待機し、Wi-Fi につながると始まります", wifiOnly, first = true) {
                scope.launch {
                    app.settings.setWifiOnly(it)
                    app.data.applyUpdateSettings()
                }
            }
        }

        Section("地方・都道府県", trailing = {
            Text("ダウンロード量 ／ 端末の容量", color = Palette.Muted, fontSize = 12.sp)
        }) {
            if (published.isEmpty()) {
                Text(
                    "配信データの一覧を取得できませんでした。通信できる環境で開き直してください。",
                    color = Palette.Muted, fontSize = 14.sp, lineHeight = 22.sp,
                    modifier = Modifier.padding(horizontal = 16.dp, vertical = 20.dp),
                )
            } else {
                REGIONS.forEachIndexed { i, region ->
                    RegionChooser(
                        name = region,
                        first = i == 0,
                        prefs = PREFECTURES.filter { it.region == region && it.slug in published },
                        published = published,
                        held = held,
                        selected = selected,
                        open = open == region,
                        onToggle = { open = if (open == region) null else region },
                        onSelect = { slugs, on -> selected = if (on) selected + slugs else selected - slugs.toSet() },
                    )
                }
            }
        }

        Column(
            modifier = Modifier.fillMaxWidth().clip(CardShape).background(Palette.Card).padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Figure("選択中", "${selected.size} 件", Modifier.weight(1f))
                Figure("ダウンロード量", sizeLabel(chosen.sumOf { it.downloadBytes }), Modifier.weight(1f))
                Figure("端末の容量", sizeLabel(chosen.sumOf { it.diskBytes }), Modifier.weight(1f))
            }
            FlatButton(
                text = when {
                    selected.isEmpty() -> "都道府県を選んでください"
                    wifiOnly -> "ダウンロード（Wi-Fi 接続時）"
                    else -> "ダウンロード"
                },
                modifier = Modifier.fillMaxWidth().height(50.dp),
                filled = Palette.Accent,
                enabled = selected.isNotEmpty(),
            ) {
                app.data.download(selected)
                selected = emptySet()
                onBack()
            }
            Text(
                "ダウンロードはバックグラウンドで続きます。保存済みのデータは設定の「保持データ」から削除できます。",
                color = Palette.Muted, fontSize = 12.sp, lineHeight = 19.sp,
            )
        }
    }
}

@Composable
private fun Figure(label: String, value: String, modifier: Modifier) {
    Column(modifier, verticalArrangement = Arrangement.spacedBy(2.dp)) {
        Text(label, color = Palette.Muted, fontSize = 12.sp)
        Text(value, color = Palette.Text, fontSize = 20.sp, fontWeight = FontWeight.Bold)
    }
}

@Composable
private fun RegionChooser(
    name: String,
    first: Boolean,
    prefs: List<Prefecture>,
    published: Map<String, Published>,
    held: Set<String>,
    selected: Set<String>,
    open: Boolean,
    onToggle: () -> Unit,
    onSelect: (List<String>, Boolean) -> Unit,
) {
    val choosable = prefs.filter { it.slug !in held }.map { it.slug }
    val picked = choosable.count { it in selected }
    val state = when {
        choosable.isNotEmpty() && picked == choosable.size -> ToggleableState.On
        picked > 0 -> ToggleableState.Indeterminate
        else -> ToggleableState.Off
    }
    val heldCount = prefs.size - choosable.size
    val download = prefs.sumOf { published[it.slug]?.downloadBytes ?: 0 }
    val disk = prefs.sumOf { published[it.slug]?.diskBytes ?: 0 }
    val chevron by animateFloatAsState(if (open) 180f else 0f, label = "chevron")

    Column {
        if (!first) Box(Modifier.fillMaxWidth().height(1.dp).background(Palette.Line))
        Row(
            modifier = Modifier.fillMaxWidth().heightIn(min = 64.dp).padding(start = 4.dp, end = 8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            TriStateCheckbox(
                state = state,
                onClick = { onSelect(choosable, state != ToggleableState.On) },
                enabled = choosable.isNotEmpty(),
                colors = checkboxColors,
                modifier = Modifier.semantics { contentDescription = "${name}をまとめて選ぶ" },
            )
            Row(
                modifier = Modifier
                    .weight(1f)
                    .heightIn(min = 48.dp)
                    .clickable(role = Role.Button, onClickLabel = if (open) "閉じる" else "開く", onClick = onToggle)
                    .padding(start = 4.dp, end = 4.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                    Text(name, color = Palette.Text, fontSize = 15.sp)
                    Text(
                        buildString {
                            append("${prefs.size} 都道府県")
                            if (heldCount > 0) append(" ・ $heldCount 件保持済み")
                            if (picked > 0) append(" ・ $picked 件選択")
                        },
                        color = Palette.Muted, fontSize = 12.sp,
                    )
                }
                Text("${sizeLabel(download)} ／ ${sizeLabel(disk)}", color = Palette.Sub, fontSize = 13.sp, fontWeight = FontWeight.SemiBold)
                Icon(Icons.Default.KeyboardArrowDown, contentDescription = null, tint = Palette.Muted, modifier = Modifier.size(20.dp).rotate(chevron))
            }
        }
        if (open) {
            Column(Modifier.padding(start = 4.dp, end = 16.dp, bottom = 8.dp)) {
                prefs.forEach { p ->
                    val pub = published[p.slug]
                    Box(Modifier.fillMaxWidth().height(1.dp).background(Palette.Inset))
                    Row(
                        modifier = Modifier.fillMaxWidth().heightIn(min = 52.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        if (p.slug in held) {
                            Box(Modifier.size(48.dp), contentAlignment = Alignment.Center) {
                                Icon(Icons.Default.Check, contentDescription = null, tint = Palette.Ok, modifier = Modifier.size(18.dp))
                            }
                            Text(p.name, color = Palette.Text, fontSize = 14.sp, modifier = Modifier.weight(1f).padding(start = 4.dp))
                            Text("保持済み", color = Palette.Ok, fontSize = 12.sp)
                        } else {
                            val on = p.slug in selected
                            Checkbox(
                                checked = on,
                                onCheckedChange = { onSelect(listOf(p.slug), it) },
                                colors = checkboxColors,
                                modifier = Modifier.semantics { contentDescription = "${p.name}を選ぶ" },
                            )
                            Text(p.name, color = Palette.Text, fontSize = 14.sp, modifier = Modifier.weight(1f).padding(start = 4.dp))
                            if (pub != null) {
                                Text(
                                    "${sizeLabel(pub.downloadBytes)} ／ ${sizeLabel(pub.diskBytes)}",
                                    color = Palette.Sub, fontSize = 13.sp, fontWeight = FontWeight.SemiBold,
                                )
                            }
                        }
                    }
                }
            }
        }
    }
}
