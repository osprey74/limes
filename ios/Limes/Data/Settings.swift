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

    init() {
        let flag = { (key: String) in UserDefaults.standard.object(forKey: key) as? Bool ?? true }
        selected = Set(store.stringArray(forKey: "selected_prefectures") ?? [])
        wifiOnly = flag("wifi_only")
        autoUpdate = flag("auto_update")
        lastChecked = store.object(forKey: "last_checked") as? Date
        autoAddCurrent = flag("auto_add_current")
        keepAwake = flag("keep_awake")
    }
}
