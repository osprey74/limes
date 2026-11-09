package com.osprey74.limes

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.osprey74.limes.core.Engine
import java.io.File

/**
 * First milestone: the Rust core loads on the device and answers. The driving
 * and settings screens come next.
 */
class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val status = coreStatus(File(filesDir, "databases"))
        setContent { CoreCheck(status) }
    }

    private fun coreStatus(store: File): String = try {
        val engine = Engine()
        engine.openStore(store.absolutePath)
        val installed = engine.installedDatabases()
        "Rust コア: 接続 OK\n保持データ: ${installed.size} 件"
    } catch (e: Throwable) {
        "Rust コア: 読み込みに失敗\n$e"
    }
}

@Composable
private fun CoreCheck(status: String) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(Color(0xFF0B0D10))
            .padding(24.dp),
        verticalArrangement = Arrangement.Center,
    ) {
        Text("Limes", color = Color(0xFFF2F4F7), fontSize = 32.sp)
        Text(status, color = Color(0xFFC3C9D0), fontSize = 16.sp, modifier = Modifier.padding(top = 12.dp))
    }
}
