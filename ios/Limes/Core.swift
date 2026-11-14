import Foundation
import Observation

/// Holds the one Rust engine of the process and its store of prefecture
/// databases (Application Support/databases, left out of backups: the data is
/// large and can be downloaded again).
@Observable
final class Core {
    let engine = Engine()

    /// The databases on the device, as the storage settings show them.
    private(set) var installed: [InstalledDatabase] = []

    /// Why the store could not be opened, if it could not.
    private(set) var storeError: String?

    init() {
        do {
            var dir = try FileManager.default
                .url(for: .applicationSupportDirectory, in: .userDomainMask, appropriateFor: nil, create: true)
                .appendingPathComponent("databases", isDirectory: true)
            try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
            var values = URLResourceValues()
            values.isExcludedFromBackup = true
            try dir.setResourceValues(values)
            _ = try engine.openStore(dir: dir.path)
            refreshInstalled()
        } catch {
            storeError = String(describing: error)
        }
    }

    func refreshInstalled() {
        installed = (try? engine.installedDatabases()) ?? []
    }
}
