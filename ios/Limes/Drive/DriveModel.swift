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
@Observable
final class DriveModel: NSObject, CLLocationManagerDelegate {
    private(set) var state = DriveState()
    private(set) var authorization: CLAuthorizationStatus

    var permitted: Bool {
        authorization == .authorizedWhenInUse || authorization == .authorizedAlways
    }

    @ObservationIgnored private let engine: Engine
    @ObservationIgnored private let manager = CLLocationManager()
    @ObservationIgnored private let worker = DispatchQueue(label: "com.osprey74.limes.locate", qos: .userInitiated)
    @ObservationIgnored private var running = false

    /// Below this speed the heading is noise; matching then relies on distance.
    private static let minHeadingSpeed = 2.0 // m/s

    private static let jst: Calendar = {
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = TimeZone(identifier: "Asia/Tokyo")!
        return calendar
    }()

    init(engine: Engine) {
        self.engine = engine
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

    func locationManagerDidChangeAuthorization(_ manager: CLLocationManager) {
        authorization = manager.authorizationStatus
        if running, permitted { manager.startUpdatingLocation() }
    }

    func locationManager(_ manager: CLLocationManager, didUpdateLocations locations: [CLLocation]) {
        guard let location = locations.last else { return }
        worker.async { [weak self] in self?.onFix(location) }
    }

    func locationManager(_ manager: CLLocationManager, didFailWithError error: Error) {
        // No fix for now; the screen shows "waiting" once the last one is stale.
    }

    private func onFix(_ location: CLLocation) {
        let c = Self.jst.dateComponents([.year, .month, .day, .hour, .minute], from: location.timestamp)
        let time = localTime(
            year: Int32(c.year!), month: UInt8(c.month!), day: UInt8(c.day!),
            hour: UInt8(c.hour!), minute: UInt8(c.minute!)
        )
        // Core Location reports "unknown" as a negative value.
        let speed: Double? = location.speed >= 0 ? location.speed : nil
        let heading: Double? =
            location.course >= 0 && (speed ?? 0) >= Self.minHeadingSpeed ? location.course : nil
        let fix = GpsFix(
            lon: location.coordinate.longitude, lat: location.coordinate.latitude,
            heading: heading, speedMps: speed
        )
        let next = DriveState(
            road: engine.locate(fix: fix, time: time),
            speedKmh: speed.map { Int(($0 * 3.6).rounded()) },
            gps: Self.quality(location),
            fixAt: Date()
        )
        DispatchQueue.main.async { [weak self] in
            guard let self, self.running else { return }
            self.state = next
        }
    }

    private static func quality(_ location: CLLocation) -> GpsQuality {
        let accuracy = location.horizontalAccuracy
        if accuracy < 0 { return .poor }
        if accuracy <= 20 { return .good }
        if accuracy <= 50 { return .fair }
        return .poor
    }
}
