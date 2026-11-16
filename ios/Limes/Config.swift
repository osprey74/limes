import Foundation

/// Where the app talks to (docs/data-hosting.md).
enum Config {
    /// manifest.json and the databases (paths in the manifest are relative to it).
    static let dataBaseURL = URL(string: "https://limes.osprey74.com/data/")!

    /// Records when each device started its free trial (server/).
    static let trialURL = URL(string: "https://limes-trial.osprey74.workers.dev/v1/trial")!

    /// Sent with every request the app makes itself (the data server and the
    /// trial ledger), in place of the system's default. It names the app, its
    /// version and the platform, and nothing about the device.
    static let userAgent: String = {
        let version = Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "0"
        return "Limes/\(version) (iOS)"
    }()
}
