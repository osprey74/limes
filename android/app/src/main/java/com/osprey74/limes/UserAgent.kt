package com.osprey74.limes

/**
 * Sent with every request the app makes itself (the data server and the trial
 * ledger), in place of the system's default. It names the app, its version and
 * the platform, and nothing about the device (docs/data-hosting.md).
 */
const val USER_AGENT = "Limes/${BuildConfig.VERSION_NAME} (Android)"
