package com.osprey74.limes

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.work.WorkInfo
import androidx.work.WorkManager
import com.osprey74.limes.core.InstalledDatabase
import com.osprey74.limes.data.UpdateWorker
import com.osprey74.limes.data.prefecture
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch

/**
 * Temporary check screen for the data layer: add or remove a prefecture, run
 * an update and see what is installed. The designed screens replace it.
 */
class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { DataCheck(application as LimesApp) }
    }
}

private const val TEST_PREFECTURE = "kochi"

@Composable
private fun DataCheck(app: LimesApp) {
    val scope = rememberCoroutineScope()
    val selected by app.settings.selected.collectAsState(initial = emptySet())
    val work by WorkManager.getInstance(app).getWorkInfosForUniqueWorkFlow(UpdateWorker.NOW)
        .collectAsState(initial = emptyList())
    var installed by remember { mutableStateOf(emptyList<InstalledDatabase>()) }
    var refresh by remember { mutableStateOf(0) }
    val last = work.lastOrNull()
    LaunchedEffect(last?.state, refresh) {
        installed = runCatching { app.engine.installedDatabases() }.getOrDefault(emptyList())
    }
    val name = prefecture(TEST_PREFECTURE)?.name ?: TEST_PREFECTURE

    Column(
        modifier = Modifier.fillMaxSize().background(Color(0xFF0B0D10)).padding(24.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text("Limes データ確認", color = Color(0xFFF2F4F7), fontSize = 26.sp, modifier = Modifier.padding(top = 48.dp))
        Text("保持対象: ${selected.sorted().joinToString { prefecture(it)?.name ?: it }.ifEmpty { "なし" }}", color = Color(0xFFC3C9D0))
        Text("更新: ${describe(last)}", color = Color(0xFFC3C9D0))
        Text("保持データ:", color = Color(0xFFC3C9D0))
        installed.forEach {
            Text(
                "  ${prefecture(it.prefecture)?.name ?: it.prefecture}  ${it.version}  ${it.bytes.toLong() / 1_000_000} MB",
                color = Color(0xFFF2F4F7),
            )
        }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(onClick = {
                scope.launch {
                    app.settings.select(listOf(TEST_PREFECTURE), keep = true)
                    UpdateWorker.runNow(app, app.settings.wifiOnly.first())
                }
            }) { Text("${name}を取得") }
            OutlinedButton(onClick = {
                scope.launch {
                    app.settings.select(listOf(TEST_PREFECTURE), keep = false)
                    runCatching { app.engine.removePrefecture(TEST_PREFECTURE) }
                    refresh += 1
                }
            }) { Text("${name}を削除") }
        }
    }
}

private fun describe(info: WorkInfo?): String = when (info?.state) {
    null -> "未実行"
    WorkInfo.State.ENQUEUED -> "待機中（ネットワーク待ち）"
    WorkInfo.State.RUNNING -> {
        val p = info.progress
        val slug = p.getString(UpdateWorker.KEY_PREFECTURE)
        if (slug == null) "実行中" else "実行中 ${prefecture(slug)?.name ?: slug}（${p.getInt(UpdateWorker.KEY_DONE, 0) + 1}/${p.getInt(UpdateWorker.KEY_TOTAL, 0)}）"
    }
    WorkInfo.State.SUCCEEDED -> "完了（取得 ${info.outputData.getInt(UpdateWorker.KEY_INSTALLED, 0)} 件）"
    WorkInfo.State.FAILED -> "失敗"
    WorkInfo.State.BLOCKED -> "前の更新の完了待ち"
    WorkInfo.State.CANCELLED -> "取り消し"
}
