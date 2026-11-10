package com.osprey74.limes

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.core.splashscreen.SplashScreen.Companion.installSplashScreen
import com.osprey74.limes.ui.DownloadScreen
import com.osprey74.limes.ui.DriveScreen
import com.osprey74.limes.ui.LaunchScreen
import com.osprey74.limes.ui.LimesTheme
import com.osprey74.limes.ui.SettingsScreen

private enum class Screen { Launch, Drive, Settings, Download }

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        installSplashScreen()
        enableEdgeToEdge()
        super.onCreate(savedInstanceState)
        val app = application as LimesApp
        setContent {
            LimesTheme {
                var screen by rememberSaveable { mutableStateOf(Screen.Launch) }
                BackHandler(enabled = screen == Screen.Settings || screen == Screen.Download) {
                    screen = if (screen == Screen.Download) Screen.Settings else Screen.Drive
                }
                when (screen) {
                    Screen.Launch -> LaunchScreen(onDone = { screen = Screen.Drive })
                    Screen.Drive -> DriveScreen(app, onSettings = { screen = Screen.Settings })
                    Screen.Settings -> SettingsScreen(
                        app,
                        onBack = { screen = Screen.Drive },
                        onDownload = { screen = Screen.Download },
                    )
                    Screen.Download -> DownloadScreen(app, onBack = { screen = Screen.Settings })
                }
            }
        }
    }
}
