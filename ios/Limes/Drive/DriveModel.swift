import CoreLocation
import Foundation
import Observation

enum GpsQuality {
    case none, poor, fair, good
}

/// What the driving screen shows for the latest fix. `road` is nil when no
/// road matched ("unknown"); `fixAt` lets the screen notice when fixes stop,
/// e.g. in a tunnel.
struct DriveState {
    var road: RoadSpeed?
    var speedKmh: Int?
    var gps: GpsQuality = .none
    var fixAt: Date?
}

/// GPS fixes in, decisions out: every fix goes to the Rust core with the local
/// (JST) time, on a queue of its own so the screen never waits for SQLite.
/// Runs only while the driving screen is in front.
@MainActor
@Observable
final class DriveModel: NSObject, CLLocationManagerDelegate {
    private(set) var state = DriveState()
    private(set) var authorization: CLAuthorizationStatus

    var permitted: Bool {
        authorization == .authorizedWhenInUse || authorization == .authorizedAlways
    }

    @ObservationIgnored private let engine: Engine
    @ObservationIgnored private let data: DataModel
    @ObservationIgnored private let geocoder = CLGeocoder()
    @ObservationIgnored private var lastLookup: CLLocation?
    @ObservationIgnored private var lastLookupAt = Date.distantPast
    @ObservationIgnored private let manager = CLLocationManager()
    @ObservationIgnored private let worker = DispatchQueue(label: "com.osprey74.limes.locate", qos: .userInitiated)
    @ObservationIgnored private var running = false

    /// Below this speed the heading is noise; matching then relies on distance.
    private nonisolated static let minHeadingSpeed = 2.0 // m/s

    private nonisolated static let jst: Calendar = {
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = TimeZone(identifier: "Asia/Tokyo")!
        return calendar
    }()

    init(data: DataModel) {
        self.data = data
        engine = data.engine
        authorization = manager.authorizationStatus
        super.init()
        manager.delegate = self
        manager.desiredAccuracy = kCLLocationAccuracyBestForNavigation
        manager.activityType = .automotiveNavigation
        manager.distanceFilter = kCLDistanceFilterNone
    }

    /// Start reading GPS, asking for the permission ("while using") first
    /// when it has not been asked yet.
    func start() {
        running = true
        if authorization == .notDetermined {
            manager.requestWhenInUseAuthorization()
        } else if permitted {
            manager.startUpdatingLocation()
        }
    }

    func stop() {
        running = false
        manager.stopUpdatingLocation()
    }

    nonisolated func locationManagerDidChangeAuthorization(_ manager: CLLocationManager) {
        let status = manager.authorizationStatus
        DispatchQueue.main.async { [weak self] in
            guard let self else { return }
            self.authorization = status
            if self.running, self.permitted { self.manager.startUpdatingLocation() }
        }
    }

    nonisolated func locationManager(_ manager: CLLocationManager, didUpdateLocations locations: [CLLocation]) {
        guard let location = locations.last else { return }
        let engine = self.engine
        worker.async { [weak self] in
            let next = Self.decide(location, engine: engine)
            DispatchQueue.main.async {
                guard let self, self.running else { return }
                self.state = next
                self.maybeAddCurrentPrefecture(location)
            }
        }
    }

    nonisolated func locationManager(_ manager: CLLocationManager, didFailWithError error: Error) {
        // No fix for now; the screen shows "waiting" once the last one is stale.
    }

    private nonisolated static func decide(_ location: CLLocation, engine: Engine) -> DriveState {
        let c = jst.dateComponents([.year, .month, .day, .hour, .minute], from: location.timestamp)
        let time = localTime(
            year: Int32(c.year!), month: UInt8(c.month!), day: UInt8(c.day!),
            hour: UInt8(c.hour!), minute: UInt8(c.minute!)
        )
        // Core Location reports "unknown" as a negative value.
        let speed: Double? = location.speed >= 0 ? location.speed : nil
        let heading: Double? =
            location.course >= 0 && (speed ?? 0) >= minHeadingSpeed ? location.course : nil
        let fix = GpsFix(
            lon: location.coordinate.longitude, lat: location.coordinate.latitude,
            heading: heading, speedMps: speed
        )
        return DriveState(
            road: engine.locate(fix: fix, time: time),
            speedKmh: speed.map { Int(($0 * 3.6).rounded()) },
            gps: quality(location),
            fixAt: Date()
        )
    }

    /// Keeps the prefecture the car is in: looks it up (reverse geocoding)
    /// after moving 3 km or every 10 minutes and fetches it when not kept yet,
    /// under the Wi-Fi setting. Crossing a border makes the neighbour the
    /// current one.
    private func maybeAddCurrentPrefecture(_ location: CLLocation) {
        guard data.settings.autoAddCurrent, !geocoder.isGeocoding else { return }
        if let last = lastLookup, location.distance(from: last) < 3000, Date().timeIntervalSince(lastLookupAt) < 10 * 60 {
            return
        }
        lastLookup = location
        lastLookupAt = Date()
        geocoder.reverseGeocodeLocation(location, preferredLocale: Locale(identifier: "ja_JP")) { [weak self] places, _ in
            guard let area = places?.first?.administrativeArea else { return }
            DispatchQueue.main.async {
                guard let self, let slug = prefectures.first(where: { $0.name == area })?.slug else { return }
                if !self.data.settings.selected.contains(slug) { self.data.download([slug]) }
            }
        }
    }

    private nonisolated static func quality(_ location: CLLocation) -> GpsQuality {
        let accuracy = location.horizontalAccuracy
        if accuracy < 0 { return .poor }
        if accuracy <= 20 { return .good }
        if accuracy <= 50 { return .fair }
        return .poor
    }
}
