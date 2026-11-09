package com.osprey74.limes.data

import android.content.Context
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import androidx.work.workDataOf
import com.osprey74.limes.LimesApp
import com.osprey74.limes.core.LimesException
import kotlinx.coroutines.flow.first
import java.io.File
import java.io.IOException
import java.util.concurrent.TimeUnit

/**
 * Brings the selected prefectures up to date: fetch the manifest, plan, then
 * download and install each changed database (the core verifies size, sha256
 * and meta before switching). A network failure retries later; a download that
 * does not match is skipped until the next run.
 */
class UpdateWorker(context: Context, params: WorkerParameters) : CoroutineWorker(context, params) {
    override suspend fun doWork(): Result {
        val app = applicationContext as LimesApp
        val selected = app.settings.selected.first()
        if (selected.isEmpty()) return Result.success()
        val manifest = try {
            app.server.manifest()
        } catch (e: IOException) {
            return Result.retry()
        }
        val plan = app.engine.planUpdates(manifest, selected.sorted())
        var mismatched = 0
        for ((i, d) in plan.downloads.withIndex()) {
            setProgress(workDataOf(KEY_PREFECTURE to d.prefecture, KEY_DONE to i, KEY_TOTAL to plan.downloads.size))
            val file = File(applicationContext.cacheDir, "downloads/${d.prefecture}.sqlite.zst")
            try {
                app.server.download(d.path, file)
                app.engine.installUpdate(d, file.absolutePath)
            } catch (e: LimesException.DownloadMismatch) {
                mismatched += 1
            } catch (e: IOException) {
                return Result.retry()
            } finally {
                file.delete()
            }
        }
        app.settings.setLastChecked(System.currentTimeMillis())
        return Result.success(
            workDataOf(
                KEY_INSTALLED to plan.downloads.size - mismatched,
                KEY_MISMATCHED to mismatched,
                KEY_APP_UPDATE to plan.appUpdateRequired.size,
            ),
        )
    }

    companion object {
        const val NOW = "data-update"
        const val DAILY = "data-update-daily"
        const val KEY_PREFECTURE = "prefecture"
        const val KEY_DONE = "done"
        const val KEY_TOTAL = "total"
        const val KEY_INSTALLED = "installed"
        const val KEY_MISMATCHED = "mismatched"
        const val KEY_APP_UPDATE = "app_update_required"

        private fun constraints(wifiOnly: Boolean) = Constraints.Builder()
            .setRequiredNetworkType(if (wifiOnly) NetworkType.UNMETERED else NetworkType.CONNECTED)
            .build()

        /** Update now (or as soon as the network allows); a later request runs after it. */
        fun runNow(context: Context, wifiOnly: Boolean) {
            val request = OneTimeWorkRequestBuilder<UpdateWorker>().setConstraints(constraints(wifiOnly)).build()
            WorkManager.getInstance(context).enqueueUniqueWork(NOW, ExistingWorkPolicy.APPEND_OR_REPLACE, request)
        }

        fun scheduleDaily(context: Context, wifiOnly: Boolean) {
            val request = PeriodicWorkRequestBuilder<UpdateWorker>(1, TimeUnit.DAYS)
                .setConstraints(constraints(wifiOnly))
                .build()
            WorkManager.getInstance(context).enqueueUniquePeriodicWork(DAILY, ExistingPeriodicWorkPolicy.UPDATE, request)
        }

        fun cancelDaily(context: Context) {
            WorkManager.getInstance(context).cancelUniqueWork(DAILY)
        }
    }
}
