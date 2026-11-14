import Foundation
import Network

/// Whether downloads may run now: connected, and under "Wi-Fi only" on a
/// network that is neither metered (cellular, hotspot) nor in Low Data Mode.
final class NetworkMonitor {
    private let monitor = NWPathMonitor()
    private var path: NWPath?

    /// Called on the main queue whenever the network changes.
    var onChange: (() -> Void)?

    init() {
        monitor.pathUpdateHandler = { [weak self] path in
            DispatchQueue.main.async {
                self?.path = path
                self?.onChange?()
            }
        }
        monitor.start(queue: .global(qos: .utility))
    }

    func allows(wifiOnly: Bool) -> Bool {
        // Not reported yet: try, the request itself carries the same limits.
        guard let path else { return true }
        guard path.status == .satisfied else { return false }
        return !wifiOnly || !(path.isExpensive || path.isConstrained)
    }
}
