package com.osprey74.limes.data

import com.osprey74.limes.LimesApp
import com.osprey74.limes.access.entitled
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import org.json.JSONObject
import java.io.IOException
import java.util.UUID

/** A prefecture database as published (manifest.json). */
data class Published(val version: String, val downloadBytes: Long, val diskBytes: Long)

/** A prefecture database on the device. */
data class Installed(val slug: String, val version: String?, val bytes: Long)

/**
 * What the settings and download screens show: the installed databases, the
 * published ones, and the update request last started (followed by its id, so
 * the screens report that request and not an older one).
 */
class DataModel(private val app: LimesApp) {
    private val _installed = MutableStateFlow<List<Installed>>(emptyList())
    val installed: StateFlow<List<Installed>> = _installed.asStateFlow()

    private val _published = MutableStateFlow<Map<String, Published>>(emptyMap())
    val published: StateFlow<Map<String, Published>> = _published.asStateFlow()

    private val _lastUpdate = MutableStateFlow<UUID?>(null)
    val lastUpdate: StateFlow<UUID?> = _lastUpdate.asStateFlow()

    fun refreshInstalled() {
        _installed.value = runCatching { app.engine.installedDatabases() }.getOrDefault(emptyList())
            .map { Installed(it.prefecture, it.version, it.bytes.toLong()) }
    }

    /** The manifest last fetched, then a fresh one when the network allows. */
    fun loadPublished() {
        app.server.cachedManifest()?.let { _published.value = parse(it) }
        app.scope.launch {
            try {
                _published.value = parse(app.server.manifest())
            } catch (_: IOException) {
                // Offline: the cached sizes stay.
            }
        }
    }

    /**
     * Keep these prefectures and fetch them (on Wi-Fi only when so set). The
     * first download starts the free trial; after it, downloads need access.
     */
    fun download(slugs: Collection<String>) {
        app.scope.launch {
            if (!app.access.current().entitled) return@launch
            app.access.startTrial()
            app.settings.select(slugs, keep = true)
            checkNow()
        }
    }

    /** Stop keeping these prefectures and delete their databases. */
    fun remove(slugs: Collection<String>) {
        app.scope.launch {
            app.settings.select(slugs, keep = false)
            slugs.forEach { runCatching { app.engine.removePrefecture(it) } }
            refreshInstalled()
        }
    }

    /** Drops every kept prefecture (access ended). */
    suspend fun removeAll() {
        app.settings.select(app.settings.selected.first(), keep = false)
        _installed.value.forEach { runCatching { app.engine.removePrefecture(it.slug) } }
        refreshInstalled()
    }

    suspend fun checkNow() {
        _lastUpdate.value = UpdateWorker.runNow(app, app.settings.wifiOnly.first())
    }

    /** Re-register the daily check after a change to the update settings. */
    suspend fun applyUpdateSettings() {
        val wifiOnly = app.settings.wifiOnly.first()
        if (app.settings.autoUpdate.first()) {
            UpdateWorker.scheduleDaily(app, wifiOnly)
        } else {
            UpdateWorker.cancelDaily(app)
        }
    }

    private fun parse(json: String): Map<String, Published> {
        val prefectures = JSONObject(json).getJSONObject("prefectures")
        return prefectures.keys().asSequence().associateWith { slug ->
            val e = prefectures.getJSONObject(slug)
            Published(e.getString("version"), e.getLong("size"), e.getLong("raw_size"))
        }
    }
}

/** "2026-09.202611090651" -> "2026年9月版". */
fun versionLabel(version: String?): String {
    val month = version?.substringBefore('.')?.split('-') ?: return "版不明"
    val (y, m) = month.getOrNull(0) to month.getOrNull(1)?.toIntOrNull()
    return if (y != null && m != null) "${y}年${m}月版" else "版不明"
}

/** Bytes as "36 MB" / "1.2 GB" (decimal units, as the stores show sizes). */
fun sizeLabel(bytes: Long): String {
    val mb = bytes / 1_000_000.0
    return if (mb >= 1000) "%.1f GB".format(mb / 1000) else "%.0f MB".format(mb)
}
