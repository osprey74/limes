package com.osprey74.limes.drive

import android.annotation.SuppressLint
import android.location.Geocoder
import android.location.Location
import android.os.SystemClock
import com.google.android.gms.location.LocationCallback
import com.google.android.gms.location.LocationRequest
import com.google.android.gms.location.LocationResult
import com.google.android.gms.location.LocationServices
import com.google.android.gms.location.Priority
import com.osprey74.limes.LimesApp
import com.osprey74.limes.core.GpsFix
import com.osprey74.limes.core.RoadSpeed
import com.osprey74.limes.core.localTime
import com.osprey74.limes.data.PREFECTURES
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import java.time.Instant
import java.time.ZoneId
import java.util.Locale
import java.util.concurrent.Executors
import kotlin.math.roundToInt

enum class GpsQuality { None, Poor, Fair, Good }

/**
 * What the driving screen shows for the latest fix. `road` is null when no
 * road matched ("unknown"); `fixAt` (elapsed realtime millis) lets the screen
 * notice when fixes stop, e.g. in a tunnel.
 */
data class DriveState(
    val road: RoadSpeed? = null,
    val speedKmh: Int? = null,
    val gps: GpsQuality = GpsQuality.None,
    val fixAt: Long = 0L,
    /** No access (trial over, no subscription): only the speed is shown. */
    val locked: Boolean = false,
)

/**
 * GPS fixes in, decisions out: every fix goes to the Rust core with the local
 * (JST) time, on a thread of its own so the screen never waits for SQLite.
 * Runs only while the driving screen is resumed.
 */
class DriveModel(private val app: LimesApp) {
    private val client by lazy { LocationServices.getFusedLocationProviderClient(app) }
    private val worker = Executors.newSingleThreadExecutor()
    private val _state = MutableStateFlow(DriveState())
    val state: StateFlow<DriveState> = _state.asStateFlow()

    private val callback = object : LocationCallback() {
        override fun onLocationResult(result: LocationResult) {
            result.lastLocation?.let(::onFix)
        }
    }

    /** Caller holds the location permission. */
    @SuppressLint("MissingPermission")
    fun start() {
        val request = LocationRequest.Builder(Priority.PRIORITY_HIGH_ACCURACY, 1_000)
            .setMinUpdateIntervalMillis(500)
            .build()
        client.requestLocationUpdates(request, worker, callback)
    }

    fun stop() {
        client.removeLocationUpdates(callback)
    }

    private fun onFix(loc: Location) {
        val t = Instant.ofEpochMilli(loc.time).atZone(JST)
        val time = localTime(t.year, t.monthValue.toUByte(), t.dayOfMonth.toUByte(), t.hour.toUByte(), t.minute.toUByte())
        val speed = if (loc.hasSpeed()) loc.speed.toDouble() else null
        // Heading is noise when standing still; matching then relies on distance.
        val heading = if (loc.hasBearing() && (speed ?: 0.0) >= MIN_HEADING_SPEED) loc.bearing.toDouble() else null
        val locked = !app.access.entitled()
        val road = if (locked) null else app.engine.locate(GpsFix(loc.longitude, loc.latitude, heading, speed), time)
        _state.value = DriveState(
            road = road,
            speedKmh = speed?.let { (it * 3.6).roundToInt() },
            gps = quality(loc),
            fixAt = SystemClock.elapsedRealtime(),
            locked = locked,
        )
        if (!locked) maybeAddCurrentPrefecture(loc)
    }

    private fun quality(loc: Location): GpsQuality = when {
        !loc.hasAccuracy() -> GpsQuality.Poor
        loc.accuracy <= 20f -> GpsQuality.Good
        loc.accuracy <= 50f -> GpsQuality.Fair
        else -> GpsQuality.Poor
    }

    private var lastLookup: Location? = null
    private var lastLookupAt = 0L

    /**
     * Keeps the prefecture the car is in: looks it up (Geocoder) after moving
     * 3 km or every 10 minutes and fetches it when not kept yet, under the
     * Wi-Fi setting. Crossing a border makes the neighbour the current one.
     */
    private fun maybeAddCurrentPrefecture(loc: Location) {
        if (!Geocoder.isPresent()) return
        val now = SystemClock.elapsedRealtime()
        val last = lastLookup
        if (last != null && loc.distanceTo(last) < 3_000 && now - lastLookupAt < 10 * 60_000) return
        lastLookup = loc
        lastLookupAt = now
        app.scope.launch {
            if (!app.settings.autoAddCurrent.first()) return@launch
            val area = adminArea(loc) ?: return@launch
            val slug = PREFECTURES.firstOrNull { it.name == area }?.slug ?: return@launch
            if (slug !in app.settings.selected.first()) app.data.download(listOf(slug))
        }
    }

    @Suppress("DEPRECATION") // the blocking call is fine here, off the main thread
    private fun adminArea(loc: Location): String? = runCatching {
        Geocoder(app, Locale.JAPAN).getFromLocation(loc.latitude, loc.longitude, 1)?.firstOrNull()?.adminArea
    }.getOrNull()

    companion object {
        private val JST = ZoneId.of("Asia/Tokyo")
        private const val MIN_HEADING_SPEED = 2.0 // m/s
    }
}
