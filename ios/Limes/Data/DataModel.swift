import Foundation
import Observation

/// A prefecture database as published (manifest.json).
struct Published: Equatable {
    let version: String
    let downloadBytes: Int64
    let diskBytes: Int64
}

/// What the update last started is doing.
enum UpdateStatus: Equatable {
    /// No usable network (or the server was not reached): tried again later.
    case waiting
    case checking
    case downloading(slug: String, done: Int, total: Int)
    case finished(installed: Int, mismatched: Int, appUpdate: Int)
    case failed
}

/// The Rust engine with its store of prefecture databases, and what the
/// settings and download screens show: the installed databases, the published
/// ones, and the state of the update last started.
///
/// An update brings the selected prefectures up to date: fetch the manifest,
/// plan, then download and install each changed database (the core verifies
/// size, sha256 and meta before switching). Without a usable network it waits
/// and runs again when the network changes; a download that does not match is
/// skipped until the next run.
@MainActor
@Observable
final class DataModel {
    let engine = Engine()
    let settings: Settings

    private(set) var installed: [InstalledDatabase] = []
    private(set) var published: [String: Published] = [:]
    private(set) var status: UpdateStatus?

    /// Set once at launch (the two need each other).
    @ObservationIgnored var access: Access!

    /// Why the store could not be opened, if it could not.
    private(set) var storeError: String?

    @ObservationIgnored private let server: DataServer
    @ObservationIgnored private let network = NetworkMonitor()
    @ObservationIgnored private let downloads: URL
    @ObservationIgnored private var running = false
    @ObservationIgnored private var again = false
    @ObservationIgnored private var pending = false
    @ObservationIgnored private var retry: Task<Void, Never>?

    private static let retryAfter: Duration = .seconds(60)
    private static let checkEvery: TimeInterval = 24 * 60 * 60

    init(settings: Settings) {
        self.settings = settings
        let files = FileManager.default
        let support = (try? files.url(for: .applicationSupportDirectory, in: .userDomainMask, appropriateFor: nil, create: true))
            ?? files.temporaryDirectory
        let caches = (try? files.url(for: .cachesDirectory, in: .userDomainMask, appropriateFor: nil, create: true))
            ?? files.temporaryDirectory
        server = DataServer(baseURL: Config.dataBaseURL, dir: support)
        downloads = caches.appendingPathComponent("downloads", isDirectory: true)

        // Application Support/databases, left out of backups: the data is
        // large and can be downloaded again.
        do {
            var dir = support.appendingPathComponent("databases", isDirectory: true)
            try files.createDirectory(at: dir, withIntermediateDirectories: true)
            var values = URLResourceValues()
            values.isExcludedFromBackup = true
            try dir.setResourceValues(values)
            _ = try engine.openStore(dir: dir.path)
        } catch {
            storeError = String(describing: error)
        }
        try? files.removeItem(at: downloads) // left by an interrupted run
        refreshInstalled()
        network.onChange = { [weak self] in
            Task { @MainActor in
                guard let self, self.pending else { return }
                self.checkNow()
            }
        }
    }

    /// At launch, once `access` is set: work out the access, then check for updates.
    func start() {
        Task {
            await access.refresh()
            if settings.autoUpdate { checkNow() }
        }
    }

    func refreshInstalled() {
        installed = (try? engine.installedDatabases()) ?? []
    }

    /// The manifest last fetched, then a fresh one when the network allows.
    func loadPublished() {
        if let cached = server.cachedManifest() { published = Self.parse(cached) }
        Task {
            // Offline: the cached sizes stay.
            if let fresh = try? await server.manifest(wifiOnly: false) { published = Self.parse(fresh) }
        }
    }

    /// Keep these prefectures and fetch them (on Wi-Fi only when so set). The
    /// first download starts the free trial; after it, downloads need access.
    func download(_ slugs: some Sequence<String>) {
        let slugs = Array(slugs)
        Task {
            guard access.state.entitled else { return }
            await access.startTrial()
            settings.selected.formUnion(slugs)
            checkNow()
        }
    }

    /// Stop keeping these prefectures and delete their databases.
    func remove(_ slugs: some Sequence<String>) {
        settings.selected.subtract(slugs)
        for slug in slugs { try? engine.removePrefecture(prefecture: slug) }
        refreshInstalled()
    }

    /// Drops every kept prefecture (access ended).
    func removeAll() {
        settings.selected = []
        for database in installed { try? engine.removePrefecture(prefecture: database.prefecture) }
        refreshInstalled()
    }

    /// Update now (or as soon as the network allows); a request made while
    /// one runs is served by another run after it.
    func checkNow() {
        if running {
            again = true
            return
        }
        running = true
        Task {
            repeat {
                again = false
                await update()
            } while again
            running = false
        }
    }

    /// Back in front: the trial may have ended, or a subscription changed,
    /// while away; then take up a waiting update, or make the daily check.
    func becameActive() {
        Task {
            await access.refresh()
            resumeUpdates()
        }
    }

    private func resumeUpdates() {
        if pending {
            checkNow()
        } else if settings.autoUpdate, settings.lastChecked.map({ Date().timeIntervalSince($0) > Self.checkEvery }) ?? true {
            checkNow()
        }
    }

    /// After a change to the update settings: a waiting update may run now.
    func settingsChanged() {
        if pending { checkNow() }
    }

    private func update() async {
        pending = false
        retry?.cancel()
        guard access.state.entitled else {
            status = nil
            return
        }
        let wanted = settings.selected.sorted()
        guard !wanted.isEmpty else {
            status = .finished(installed: 0, mismatched: 0, appUpdate: 0)
            return
        }
        let wifiOnly = settings.wifiOnly
        guard network.allows(wifiOnly: wifiOnly) else { return wait() }
        status = .checking
        guard let manifest = try? await server.manifest(wifiOnly: wifiOnly) else { return wait() }
        published = Self.parse(manifest)

        let engine = self.engine
        let planned = Task.detached { try engine.planUpdates(manifestJson: manifest, prefectures: wanted) }
        guard let plan = try? await planned.value else {
            status = .failed
            return
        }
        var mismatched = 0
        for (i, d) in plan.downloads.enumerated() {
            status = .downloading(slug: d.prefecture, done: i, total: plan.downloads.count)
            let file = downloads.appendingPathComponent("\(d.prefecture).sqlite.zst")
            defer { try? FileManager.default.removeItem(at: file) }
            do {
                try await server.download(d.path, to: file, wifiOnly: wifiOnly)
                // Verifying and decompressing takes seconds: off the main thread.
                try await Task.detached { _ = try engine.installUpdate(download: d, file: file.path) }.value
            } catch LimesError.DownloadMismatch {
                mismatched += 1
            } catch is LimesError {
                refreshInstalled()
                status = .failed
                return
            } catch {
                // The network dropped: what was installed so far shows, the rest waits.
                refreshInstalled()
                return wait()
            }
        }
        refreshInstalled()
        settings.lastChecked = Date()
        status = .finished(
            installed: plan.downloads.count - mismatched,
            mismatched: mismatched,
            appUpdate: plan.appUpdateRequired.count
        )
    }

    private func wait() {
        pending = true
        status = .waiting
        retry = Task { [weak self] in
            try? await Task.sleep(for: Self.retryAfter)
            guard !Task.isCancelled, let self, self.pending else { return }
            self.checkNow()
        }
    }

    private static func parse(_ json: String) -> [String: Published] {
        guard let root = try? JSONSerialization.jsonObject(with: Data(json.utf8)) as? [String: Any],
              let entries = root["prefectures"] as? [String: [String: Any]]
        else { return [:] }
        return entries.compactMapValues { e in
            guard let version = e["version"] as? String,
                  let size = (e["size"] as? NSNumber)?.int64Value,
                  let raw = (e["raw_size"] as? NSNumber)?.int64Value
            else { return nil }
            return Published(version: version, downloadBytes: size, diskBytes: raw)
        }
    }
}
