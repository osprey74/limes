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
import kotlinx.coroutines.launch
import androidx.core.splashscreen.SplashScreen.Companion.installSplashScreen
import com.osprey74.limes.access.AccessState
import com.osprey74.limes.ui.DownloadScreen
import com.osprey74.limes.ui.DriveScreen
import com.osprey74.limes.ui.LaunchScreen
import com.osprey74.limes.ui.LimesTheme
import com.osprey74.limes.ui.SettingsScreen
import com.osprey74.limes.ui.SubscribeScreen

private enum class Screen { Launch, Drive, Settings, Download, Subscribe }

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        installSplashScreen()
        enableEdgeToEdge()
        super.onCreate(savedInstanceState)
        val app = application as LimesApp
        setContent {
            LimesTheme {
                var screen by rememberSaveable { mutableStateOf(Screen.Launch) }
                // Where the plans were opened from, for their back button.
                var plansFrom by rememberSaveable { mutableStateOf(Screen.Drive) }
                val openPlans = { from: Screen ->
                    plansFrom = from
                    screen = Screen.Subscribe
                }
                BackHandler(enabled = screen != Screen.Launch && screen != Screen.Drive) {
                    screen = when (screen) {
                        Screen.Download -> Screen.Settings
                        Screen.Subscribe -> plansFrom
                        else -> Screen.Drive
                    }
                }
                when (screen) {
                    // With the trial over, the plans show once at launch, never while driving.
                    Screen.Launch -> LaunchScreen(onDone = {
                        if (app.access.state.value == AccessState.Expired) openPlans(Screen.Drive) else screen = Screen.Drive
                    })
                    Screen.Drive -> DriveScreen(app, onSettings = { screen = Screen.Settings }, onSubscribe = { openPlans(Screen.Drive) })
                    Screen.Settings -> SettingsScreen(
                        app,
                        onBack = { screen = Screen.Drive },
                        onDownload = { screen = Screen.Download },
                        onSubscribe = { openPlans(Screen.Settings) },
                    )
                    Screen.Download -> DownloadScreen(app, onBack = { screen = Screen.Settings })
                    Screen.Subscribe -> SubscribeScreen(
                        app,
                        backLabel = if (plansFrom == Screen.Settings) "設定" else "走行画面",
                        onBack = { screen = plansFrom },
                    )
                }
            }
        }
    }

    // The trial may have ended, or a subscription changed, while away.
    override fun onResume() {
        super.onResume()
        val app = application as LimesApp
        app.scope.launch { app.access.refresh() }
    }
}
