package com.osprey74.limes.ui

import android.Manifest
import android.content.pm.PackageManager
import android.content.res.Configuration
import android.os.SystemClock
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import androidx.lifecycle.compose.LifecycleResumeEffect
import com.osprey74.limes.LimesApp
import com.osprey74.limes.core.Confidence
import com.osprey74.limes.core.RoadSpeed
import com.osprey74.limes.data.versionLabel
import com.osprey74.limes.drive.DriveState
import com.osprey74.limes.drive.GpsQuality
import kotlinx.coroutines.delay

private const val STALE_MS = 5_000L
private val SignRed = Color(0xFFD7262E)
private val SignBlue = Color(0xFF1D4E9E)

private const val DISCLAIMER_SHORT = "表示される速度は公開データからの推定です。実際の最高速度は現地の標識・標示に従ってください。"

@Composable
fun DriveScreen(app: LimesApp, onSettings: () -> Unit) {
    val context = LocalContext.current
    var permitted by remember {
        mutableStateOf(
            ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_FINE_LOCATION) ==
                PackageManager.PERMISSION_GRANTED,
        )
    }
    val ask = rememberLauncherForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) {
        permitted = it[Manifest.permission.ACCESS_FINE_LOCATION] == true
    }
    LaunchedEffect(Unit) {
        if (!permitted) {
            ask.launch(arrayOf(Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION))
        }
    }
    if (permitted) {
        LifecycleResumeEffect(Unit) {
            app.drive.start()
            onPauseOrDispose { app.drive.stop() }
        }
    }

    val keepAwake by app.settings.keepAwake.collectAsState(initial = true)
    val view = LocalView.current
    DisposableEffect(keepAwake) {
        view.keepScreenOn = keepAwake
        onDispose { view.keepScreenOn = false }
    }

    val state by app.drive.state.collectAsState()
    val installed by app.data.installed.collectAsState()
    var now by remember { mutableLongStateOf(SystemClock.elapsedRealtime()) }
    LaunchedEffect(Unit) {
        while (true) {
            delay(1_000)
            now = SystemClock.elapsedRealtime()
        }
    }
    val stale = state.fixAt == 0L || now - state.fixAt > STALE_MS
    val version = installed.mapNotNull { it.version }.maxOrNull()
    val landscape = LocalConfiguration.current.orientation == Configuration.ORIENTATION_LANDSCAPE

    val top: @Composable () -> Unit = {
        Row(Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 8.dp), verticalAlignment = Alignment.CenterVertically) {
            Spacer(Modifier.size(44.dp))
            Text(
                if (version != null) "データ ${versionLabel(version)}" else "データ未取得",
                color = Palette.Muted, fontSize = 12.sp, textAlign = TextAlign.Center, modifier = Modifier.weight(1f),
            )
            IconButton(onClick = onSettings, modifier = Modifier.size(44.dp).clip(ButtonShape).background(Palette.Card)) {
                Icon(Icons.Default.Settings, contentDescription = "設定を開く", tint = Palette.Text)
            }
        }
    }
    val limit: @Composable (Dp) -> Unit = { sign ->
        LimitPanel(
            state = state,
            stale = stale,
            sign = sign,
            note = when {
                !permitted -> "位置情報を許可すると速度を表示します"
                installed.isEmpty() -> "データがありません。設定からダウンロードしてください"
                else -> null
            },
        )
    }

    Column(Modifier.fillMaxSize().background(Palette.Ground).statusBarsPadding().navigationBarsPadding()) {
        top()
        if (landscape) {
            Row(Modifier.weight(1f).fillMaxWidth().padding(horizontal = 32.dp)) {
                Box(Modifier.weight(1f).fillMaxHeight(), contentAlignment = Alignment.Center) { limit(170.dp) }
                Box(Modifier.width(1.dp).fillMaxHeight().padding(vertical = 8.dp).background(Palette.Line))
                Box(Modifier.weight(1f).fillMaxHeight(), contentAlignment = Alignment.Center) { SpeedPanel(state, stale) }
            }
        } else {
            Box(Modifier.weight(1f).fillMaxWidth(), contentAlignment = Alignment.Center) { limit(220.dp) }
            Box(Modifier.fillMaxWidth().padding(horizontal = 16.dp).height(1.dp).background(Palette.Line))
            Box(Modifier.weight(1f).fillMaxWidth(), contentAlignment = Alignment.Center) { SpeedPanel(state, stale) }
        }
        Text(
            DISCLAIMER_SHORT,
            color = Palette.Muted, fontSize = 12.sp, lineHeight = 19.sp, textAlign = TextAlign.Center,
            modifier = Modifier.fillMaxWidth().padding(horizontal = 24.dp, vertical = 10.dp),
        )
    }
}

@Composable
private fun LimitPanel(state: DriveState, stale: Boolean, sign: Dp, note: String?) {
    val road = state.road.takeIf { !stale }
    Column(horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Text(
            road?.let(::roadLabel) ?: " ",
            color = Palette.Text, fontSize = 22.sp, fontWeight = FontWeight.Bold, textAlign = TextAlign.Center,
            maxLines = 1,
        )
        SpeedSign(road?.speedKmh?.toInt(), dashed = road?.confidence == Confidence.LOW, size = sign)
        ConfidencePill(road)
        if (note != null) Text(note, color = Palette.Waiting, fontSize = 13.sp, textAlign = TextAlign.Center)
    }
}

/** Name, else the route number, else nothing to show. */
private fun roadLabel(road: RoadSpeed): String = when {
    road.roadName.isNotBlank() -> road.roadName
    road.roadRef.isNotBlank() && road.highway.startsWith("trunk") -> "国道${road.roadRef.substringBefore(';')}号"
    else -> "道路名なし"
}

/** The regulatory sign: white disc, red ring (dashed when the confidence is low), blue figures. */
@Composable
private fun SpeedSign(speed: Int?, dashed: Boolean, size: Dp) {
    val ring = size * (20f / 220f)
    val figure = with(LocalDensity.current) { (size * if (speed != null && speed >= 100) 0.40f else 0.47f).toSp() }
    Box(
        modifier = Modifier
            .size(size)
            .semantics { contentDescription = if (speed != null) "推定最高速度 $speed キロ" else "最高速度を判定できません" }
            .drawBehind {
                val stroke = ring.toPx()
                val radius = this.size.minDimension / 2 - stroke / 2
                if (speed != null) drawCircle(Color.White, radius = this.size.minDimension / 2)
                drawCircle(
                    color = if (speed != null) SignRed else Palette.Border,
                    radius = radius,
                    center = Offset(this.size.width / 2, this.size.height / 2),
                    style = Stroke(
                        width = stroke,
                        pathEffect = if (dashed) PathEffect.dashPathEffect(floatArrayOf(stroke * 1.2f, stroke * 0.8f)) else null,
                    ),
                )
            },
        contentAlignment = Alignment.Center,
    ) {
        Text(
            speed?.toString() ?: "—",
            color = if (speed != null) SignBlue else Palette.Faint,
            fontSize = figure, fontWeight = FontWeight.Bold, letterSpacing = (-2).sp,
        )
    }
}

@Composable
private fun ConfidencePill(road: RoadSpeed?) {
    val (label, bars, source) = when (road?.confidence) {
        Confidence.HIGH -> Triple("高", 3, source(road))
        Confidence.MID -> Triple("中", 2, source(road))
        Confidence.LOW -> Triple("低", 1, "中央線の証拠なし（安全側で30）")
        null -> Triple("—", 0, "道路を特定できません")
    }
    Row(
        modifier = Modifier.clip(RoundedCornerShape(50)).background(Palette.Card).padding(horizontal = 14.dp, vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Row(horizontalArrangement = Arrangement.spacedBy(3.dp)) {
            repeat(3) { i ->
                Box(Modifier.size(width = 16.dp, height = 6.dp).clip(RoundedCornerShape(3.dp)).background(if (i < bars) Palette.Text else Palette.Border))
            }
        }
        Text("確度 $label", color = Palette.Text, fontSize = 14.sp, fontWeight = FontWeight.Medium)
        Text(source, color = Palette.Muted, fontSize = 13.sp, maxLines = 1)
    }
}

/** Why this speed, in the words of the design (stage numbers from limes-core decide.rs). */
private fun source(road: RoadSpeed): String = when (road.stage.toInt()) {
    1 -> "規制速度（JARTIC）"
    2 -> "高速自動車国道"
    3 -> "自動車専用道路"
    4 -> "中央分離帯あり"
    5 -> if (road.confidence == Confidence.HIGH) "中央線・車線（JARTIC）" else "中央線・車線から推定（写真・OSM）"
    7 -> "区画線なし（OSM）"
    else -> road.reason
}

@Composable
private fun SpeedPanel(state: DriveState, stale: Boolean) {
    Column(horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Text("現在の速度", color = Palette.Muted, fontSize = 14.sp)
        Row(verticalAlignment = Alignment.Bottom, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(
                if (stale) "—" else (state.speedKmh ?: 0).toString(),
                color = Palette.Text, fontSize = 140.sp, lineHeight = 140.sp, fontWeight = FontWeight.Bold, letterSpacing = (-4).sp,
            )
            Text("km/h", color = Palette.Muted, fontSize = 24.sp, fontWeight = FontWeight.SemiBold, modifier = Modifier.padding(bottom = 22.dp))
        }
        val (text, color) = when {
            stale -> "GPS 受信待ち" to Palette.Muted
            state.gps == GpsQuality.Good -> "GPS 良好" to Palette.Ok
            state.gps == GpsQuality.Fair -> "GPS 精度低下" to Palette.Waiting
            else -> "GPS 精度不足" to Palette.Waiting
        }
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            Box(Modifier.size(8.dp).clip(CircleShape).background(color))
            Text(text, color = Palette.Muted, fontSize = 13.sp)
        }
    }
}
