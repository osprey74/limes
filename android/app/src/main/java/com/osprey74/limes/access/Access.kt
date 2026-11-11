package com.osprey74.limes.access

import com.osprey74.limes.LimesApp
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock

sealed interface AccessState {
    /** Nothing downloaded yet: the trial starts with the first download. */
    data object NotStarted : AccessState

    /** In the free trial, which ends at `ends` (epoch millis). */
    data class Trial(val ends: Long) : AccessState

    data object Subscribed : AccessState

    /** Trial over and no subscription: only the GPS speed is shown. */
    data object Expired : AccessState
}

val AccessState.entitled: Boolean get() = this !is AccessState.Expired

/**
 * Whether the speed limits may be shown: during the free trial (14 days from
 * the first data download, kept by server/ across reinstalls) or with a
 * subscription. When neither, decisions, downloads and updates stop, and the
 * kept databases are deleted once the subscription has really ended.
 */
class Access(private val app: LimesApp) {
    private val _state = MutableStateFlow<AccessState?>(null)

    /** Null until first worked out. */
    val state: StateFlow<AccessState?> = _state.asStateFlow()
    private val refreshing = Mutex()

    /** Entitled unless known to be expired (so nothing is cut off while Play answers). */
    fun entitled(): Boolean = _state.value?.entitled ?: true

    /** The state, working it out first when not known yet (e.g. in a worker). */
    suspend fun current(): AccessState = _state.value ?: refresh()

    suspend fun refresh(): AccessState = refreshing.withLock {
        val now = System.currentTimeMillis()
        val subscribed = app.billing.subscribed()
        if (subscribed == true) app.settings.setLastSubscribed(now)
        val lastSubscribed = app.settings.lastSubscribed.first()

        if (app.settings.trialEnds.first() == 0L && app.data.installed.value.isNotEmpty()) {
            startTrial() // data from before the trial existed
        } else if (app.settings.trialEnds.first() != 0L && !app.settings.trialConfirmed.first()) {
            confirmTrial()
        }
        val ends = app.settings.trialEnds.first()

        val state = when {
            subscribed == true -> AccessState.Subscribed
            // Play can't be asked: a recent subscriber keeps access meanwhile.
            subscribed == null && lastSubscribed != 0L && now - lastSubscribed < HOLD_MS -> AccessState.Subscribed
            ends == 0L -> AccessState.NotStarted
            now < ends -> AccessState.Trial(ends)
            else -> AccessState.Expired
        }
        _state.value = state
        if (state == AccessState.Expired && subscribed == false) removeDataWhenDue(now, lastSubscribed)
        state
    }

    /** Starts the trial at the first download; no-op once started. */
    suspend fun startTrial() {
        if (app.settings.trialEnds.first() != 0L) return
        val fromServer = runCatching { app.trial.register() }.getOrNull()
        // The ledger unreachable (or over its daily limit): count from now, confirm later.
        app.settings.setTrial(fromServer ?: (System.currentTimeMillis() + TRIAL_MS), confirmed = fromServer != null)
        if (_state.value == null || _state.value == AccessState.NotStarted) refreshState()
    }

    private suspend fun confirmTrial() {
        val fromServer = runCatching { app.trial.register() }.getOrNull() ?: return
        // A reinstall started earlier: the ledger's (earlier) end wins.
        app.settings.setTrial(minOf(fromServer, app.settings.trialEnds.first()), confirmed = true)
    }

    private suspend fun refreshState() {
        val ends = app.settings.trialEnds.first()
        if (ends != 0L && System.currentTimeMillis() < ends) _state.value = AccessState.Trial(ends)
    }

    /**
     * Deletes the kept databases: at once after a trial without subscription,
     * and HOLD_MS after a subscription was last seen, so a grace period or
     * account hold (payment trouble) does not cost the data.
     */
    private suspend fun removeDataWhenDue(now: Long, lastSubscribed: Long) {
        if (lastSubscribed != 0L && now - lastSubscribed < HOLD_MS) return
        if (app.data.installed.value.isEmpty() && app.settings.selected.first().isEmpty()) return
        app.data.removeAll()
        app.settings.setDataRemovedNotice(true)
    }

    companion object {
        const val TRIAL_MS = 14L * 24 * 60 * 60 * 1000
        // Google Play: grace period up to 30 days, then account hold.
        const val HOLD_MS = 60L * 24 * 60 * 60 * 1000
    }
}
