package com.osprey74.limes.access

import android.annotation.SuppressLint
import android.content.Context
import android.provider.Settings.Secure
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL
import java.security.MessageDigest
import java.time.Instant

/**
 * Asks the trial ledger (server/) when this device's free trial ends. The
 * device is known by a hash of ANDROID_ID, which keeps its value when the app
 * is reinstalled (same signing key), so a reinstall gets the same trial back.
 */
class TrialClient(private val url: String, private val context: Context) {
    /** Epoch millis when the trial ends; the first call starts it. */
    suspend fun register(): Long = withContext(Dispatchers.IO) {
        val conn = (URL(url).openConnection() as HttpURLConnection).apply {
            requestMethod = "POST"
            doOutput = true
            connectTimeout = 15_000
            readTimeout = 15_000
            setRequestProperty("content-type", "application/json")
        }
        try {
            val body = JSONObject().put("id", deviceHash()).put("platform", "android").toString()
            conn.outputStream.use { it.write(body.toByteArray()) }
            val code = conn.responseCode
            if (code != HttpURLConnection.HTTP_OK) throw IOException("trial: HTTP $code")
            val text = conn.inputStream.use { it.readBytes().decodeToString() }
            Instant.parse(JSONObject(text).getString("trial_ends")).toEpochMilli()
        } finally {
            conn.disconnect()
        }
    }

    // Only the hash leaves the device, prefixed so it matches no other app's.
    @SuppressLint("HardwareIds")
    private fun deviceHash(): String {
        val id = Secure.getString(context.contentResolver, Secure.ANDROID_ID).orEmpty()
        return MessageDigest.getInstance("SHA-256").digest("limes:$id".toByteArray())
            .joinToString("") { "%02x".format(it) }
    }
}
