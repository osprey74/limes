import Foundation
import Observation

/// User settings, kept in UserDefaults (the same keys as the Android app).
@Observable
final class Settings {
    @ObservationIgnored private let store = UserDefaults.standard

    /// Prefectures to keep and update (slugs).
    var selected: Set<String> { didSet { store.set(selected.sorted(), forKey: "selected_prefectures") } }

    /// Download only on networks that are neither metered nor in Low Data Mode (default on).
    var wifiOnly: Bool { didSet { store.set(wifiOnly, forKey: "wifi_only") } }

    /// Check for new data at launch and daily (default on).
    var autoUpdate: Bool { didSet { store.set(autoUpdate, forKey: "auto_update") } }

    /// When the last update check finished, nil when never.
    var lastChecked: Date? { didSet { store.set(lastChecked, forKey: "last_checked") } }

    /// Add the prefecture the car is in (default on).
    var autoAddCurrent: Bool { didSet { store.set(autoAddCurrent, forKey: "auto_add_current") } }

    /// Keep the screen on while the driving screen shows (default on).
    var keepAwake: Bool { didSet { store.set(keepAwake, forKey: "keep_awake") } }

    /// When the free trial ends, nil before the first download.
    var trialEnds: Date? { didSet { store.set(trialEnds?.timeIntervalSince1970 ?? 0, forKey: "trial_ends") } }

    /// False while the trial end is the device's own count (server/ not reached yet).
    var trialConfirmed: Bool { didSet { store.set(trialConfirmed, forKey: "trial_confirmed") } }

    /// When an active subscription was last seen, nil when never.
    var lastSubscribed: Date? { didSet { store.set(lastSubscribed?.timeIntervalSince1970 ?? 0, forKey: "last_subscribed") } }

    /// The kept databases were deleted at the end of access; say so once.
    var dataRemovedNotice: Bool { didSet { store.set(dataRemovedNotice, forKey: "data_removed_notice") } }

    init() {
        let flag = { (key: String) in UserDefaults.standard.object(forKey: key) as? Bool ?? true }
        selected = Set(store.stringArray(forKey: "selected_prefectures") ?? [])
        wifiOnly = flag("wifi_only")
        autoUpdate = flag("auto_update")
        lastChecked = store.object(forKey: "last_checked") as? Date
        autoAddCurrent = flag("auto_add_current")
        keepAwake = flag("keep_awake")
        // Seconds since 1970, 0 when unset.
        let date = { (key: String) -> Date? in
            let seconds = UserDefaults.standard.double(forKey: key)
            return seconds > 0 ? Date(timeIntervalSince1970: seconds) : nil
        }
        trialEnds = date("trial_ends")
        trialConfirmed = store.bool(forKey: "trial_confirmed")
        lastSubscribed = date("last_subscribed")
        dataRemovedNotice = store.bool(forKey: "data_removed_notice")
    }
}
