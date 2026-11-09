package com.osprey74.limes.data

import android.content.Context
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.longPreferencesKey
import androidx.datastore.preferences.core.stringSetPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map

private val Context.dataStore by preferencesDataStore(name = "settings")

/** User settings that drive data updates. */
class Settings(private val context: Context) {
    private object Keys {
        val selected = stringSetPreferencesKey("selected_prefectures")
        val wifiOnly = booleanPreferencesKey("wifi_only")
        val autoUpdate = booleanPreferencesKey("auto_update")
        val lastChecked = longPreferencesKey("last_checked")
    }

    /** Prefectures to keep and update (slugs). */
    val selected: Flow<Set<String>> = context.dataStore.data.map { it[Keys.selected] ?: emptySet() }

    /** Download only on unmetered networks (default on). */
    val wifiOnly: Flow<Boolean> = context.dataStore.data.map { it[Keys.wifiOnly] ?: true }

    /** Check for new data at launch and daily (default on). */
    val autoUpdate: Flow<Boolean> = context.dataStore.data.map { it[Keys.autoUpdate] ?: true }

    /** Epoch millis of the last finished update check, 0 when never. */
    val lastChecked: Flow<Long> = context.dataStore.data.map { it[Keys.lastChecked] ?: 0L }

    suspend fun select(slugs: Collection<String>, keep: Boolean) {
        context.dataStore.edit {
            val current = it[Keys.selected] ?: emptySet()
            it[Keys.selected] = if (keep) current + slugs else current - slugs.toSet()
        }
    }

    suspend fun setWifiOnly(on: Boolean) = context.dataStore.edit { it[Keys.wifiOnly] = on }

    suspend fun setAutoUpdate(on: Boolean) = context.dataStore.edit { it[Keys.autoUpdate] = on }

    suspend fun setLastChecked(millis: Long) = context.dataStore.edit { it[Keys.lastChecked] = millis }
}
