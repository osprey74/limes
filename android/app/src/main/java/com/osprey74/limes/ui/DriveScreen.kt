package com.osprey74.limes.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.osprey74.limes.LimesApp
import com.osprey74.limes.data.versionLabel

/** Placeholder until the driving screen (GPS and locate) is built. */
@Composable
fun DriveScreen(app: LimesApp, onSettings: () -> Unit) {
    val installed by app.data.installed.collectAsState()
    val version = installed.mapNotNull { it.version }.maxOrNull()
    Column(
        modifier = Modifier.fillMaxSize().background(Palette.Ground).statusBarsPadding().navigationBarsPadding(),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(16.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Spacer(Modifier.size(44.dp))
            Text(
                if (version != null) "データ ${versionLabel(version)}" else "データ未取得",
                color = Palette.Muted, fontSize = 12.sp, textAlign = TextAlign.Center, modifier = Modifier.weight(1f),
            )
            IconButton(onClick = onSettings, modifier = Modifier.size(44.dp).clip(ButtonShape).background(Palette.Card)) {
                Icon(Icons.Default.Settings, contentDescription = "設定を開く", tint = Palette.Text)
            }
        }
        Box(Modifier.weight(1f).fillMaxWidth(), contentAlignment = Alignment.Center) {
            Column(horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("走行画面", color = Palette.Text, fontSize = 22.sp)
                Text("次の段階で実装します", color = Palette.Muted, fontSize = 14.sp)
            }
        }
        Text(
            DISCLAIMER,
            color = Palette.Muted, fontSize = 12.sp, lineHeight = 19.sp, textAlign = TextAlign.Center,
            modifier = Modifier.fillMaxWidth().padding(horizontal = 24.dp, vertical = 16.dp),
        )
    }
}
