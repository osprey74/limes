package com.osprey74.limes

import android.app.Application
import android.util.Log
import com.osprey74.limes.core.Engine
import com.osprey74.limes.data.DataModel
import com.osprey74.limes.data.DataServer
import com.osprey74.limes.data.Settings
import com.osprey74.limes.drive.DriveModel
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import java.io.File

/** Holds the one Rust engine of the process, its store and the settings. */
class LimesApp : Application() {
    val engine: Engine by lazy { Engine() }
    val settings: Settings by lazy { Settings(this) }
    val server: DataServer by lazy { DataServer(BuildConfig.DATA_BASE_URL, filesDir) }
    val data: DataModel by lazy { DataModel(this) }
    val drive: DriveModel by lazy { DriveModel(this) }
    val scope = CoroutineScope(SupervisorJob() + Dispatchers.Default)

    override fun onCreate() {
        super.onCreate()
        try {
            engine.openStore(File(filesDir, "databases").absolutePath)
        } catch (e: Exception) {
            Log.e(TAG, "opening the store failed", e)
        }
        data.refreshInstalled()
        scope.launch {
            if (settings.autoUpdate.first()) {
                data.checkNow()
            }
            data.applyUpdateSettings()
        }
    }

    companion object {
        private const val TAG = "Limes"
    }
}
