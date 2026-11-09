package com.osprey74.limes.data

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.File
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL

/**
 * The published data (manifest.json and the `.sqlite.zst` files) at `baseUrl`.
 * The manifest is kept in `dir` with its ETag, so an unchanged manifest costs
 * a 304 with no body.
 */
class DataServer(private val baseUrl: String, dir: File) {
    private val manifest = File(dir, "manifest.json")
    private val etag = File(dir, "manifest.etag")

    /** The current manifest, fetched or revalidated. */
    suspend fun manifest(): String = withContext(Dispatchers.IO) {
        val conn = open("manifest.json")
        try {
            if (manifest.exists() && etag.exists()) {
                conn.setRequestProperty("If-None-Match", etag.readText())
            }
            when (val code = conn.responseCode) {
                HttpURLConnection.HTTP_NOT_MODIFIED -> manifest.readText()
                HttpURLConnection.HTTP_OK -> {
                    val text = conn.inputStream.use { it.readBytes().decodeToString() }
                    val part = File(manifest.path + ".part")
                    part.writeText(text)
                    if (!part.renameTo(manifest)) {
                        manifest.delete()
                        part.renameTo(manifest)
                    }
                    conn.getHeaderField("ETag")?.let { etag.writeText(it) } ?: etag.delete()
                    text
                }
                else -> throw IOException("manifest.json: HTTP $code")
            }
        } finally {
            conn.disconnect()
        }
    }

    /** The manifest last fetched, for showing sizes without the network. */
    fun cachedManifest(): String? = manifest.takeIf { it.exists() }?.readText()

    /** Downloads a published file (path relative to the manifest) to `out`. */
    suspend fun download(path: String, out: File) = withContext(Dispatchers.IO) {
        val conn = open(path)
        try {
            val code = conn.responseCode
            if (code != HttpURLConnection.HTTP_OK) throw IOException("$path: HTTP $code")
            out.parentFile?.mkdirs()
            conn.inputStream.use { input -> out.outputStream().use { input.copyTo(it, 1 shl 16) } }
        } finally {
            conn.disconnect()
        }
    }

    private fun open(path: String): HttpURLConnection =
        (URL(baseUrl + path).openConnection() as HttpURLConnection).apply {
            connectTimeout = 15_000
            readTimeout = 60_000
            useCaches = false
        }
}
