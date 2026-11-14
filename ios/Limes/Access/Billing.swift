import Foundation

/// The Limes subscription on the App Store. Not built yet (StoreKit 2 comes
/// next): until then the store "can't be asked", which keeps the trial rules
/// working and never counts as "not subscribed".
struct Billing {
    /// True when an active subscription is held, nil when the store can't be asked.
    func subscribed() async -> Bool? { nil }
}
