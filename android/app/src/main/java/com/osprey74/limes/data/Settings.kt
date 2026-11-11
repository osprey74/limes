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
        val autoAddCurrent = booleanPreferencesKey("auto_add_current")
        val keepAwake = booleanPreferencesKey("keep_awake")
        val trialEnds = longPreferencesKey("trial_ends")
        val trialConfirmed = booleanPreferencesKey("trial_confirmed")
        val lastSubscribed = longPreferencesKey("last_subscribed")
        val dataRemovedNotice = booleanPreferencesKey("data_removed_notice")
    }

    /** Epoch millis when the free trial ends, 0 before the first download. */
    val trialEnds: Flow<Long> = context.dataStore.data.map { it[Keys.trialEnds] ?: 0L }

    /** False while the trial end is the device's own count (server/ not reached yet). */
    val trialConfirmed: Flow<Boolean> = context.dataStore.data.map { it[Keys.trialConfirmed] ?: false }

    /** Epoch millis when an active subscription was last seen, 0 when never. */
    val lastSubscribed: Flow<Long> = context.dataStore.data.map { it[Keys.lastSubscribed] ?: 0L }

    /** The kept databases were deleted at the end of access; say so once. */
    val dataRemovedNotice: Flow<Boolean> = context.dataStore.data.map { it[Keys.dataRemovedNotice] ?: false }

    suspend fun setTrial(ends: Long, confirmed: Boolean) = context.dataStore.edit {
        it[Keys.trialEnds] = ends
        it[Keys.trialConfirmed] = confirmed
    }

    suspend fun setLastSubscribed(millis: Long) = context.dataStore.edit { it[Keys.lastSubscribed] = millis }

    suspend fun setDataRemovedNotice(on: Boolean) = context.dataStore.edit { it[Keys.dataRemovedNotice] = on }

    /** Add the prefecture the car is in and its neighbours (default on). */
    val autoAddCurrent: Flow<Boolean> = context.dataStore.data.map { it[Keys.autoAddCurrent] ?: true }

    /** Keep the screen on while the driving screen shows (default on). */
    val keepAwake: Flow<Boolean> = context.dataStore.data.map { it[Keys.keepAwake] ?: true }

    suspend fun setAutoAddCurrent(on: Boolean) = context.dataStore.edit { it[Keys.autoAddCurrent] = on }

    suspend fun setKeepAwake(on: Boolean) = context.dataStore.edit { it[Keys.keepAwake] = on }

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
