import Foundation

/// Where the app talks to. The development addresses; `limes.osprey74.app`
/// and `limes-trial.osprey74.app` replace them for release.
enum Config {
    /// manifest.json and the databases (paths in the manifest are relative to it).
    static let dataBaseURL = URL(string: "https://pub-f67fb68aa5714cc7b4694371d04c0bf4.r2.dev/")!

    /// Records when each device started its free trial (server/).
    static let trialURL = URL(string: "https://limes-trial.osprey74.workers.dev/v1/trial")!
}
