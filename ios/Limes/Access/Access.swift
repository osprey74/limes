import Foundation
import Observation

enum AccessState: Equatable {
    /// Nothing downloaded yet: the trial starts with the first download.
    case notStarted
    /// In the free trial, which ends at `ends`.
    case trial(ends: Date)
    case subscribed
    /// Trial over and no subscription: only the GPS speed is shown.
    case expired

    var entitled: Bool { self != .expired }
}

/// Whether the speed limits may be shown: during the free trial (14 days from
/// the first data download, kept by server/ across reinstalls) or with a
/// subscription. When neither, decisions, downloads and updates stop, and the
/// kept databases are deleted once the subscription has really ended.
@MainActor
@Observable
final class Access {
    /// Worked out from what the device remembers until `refresh` has asked
    /// the store and the ledger.
    private(set) var state: AccessState

    @ObservationIgnored private let settings: Settings
    @ObservationIgnored private unowned let data: DataModel
    @ObservationIgnored private let trial = TrialClient(url: Config.trialURL)
    @ObservationIgnored private let billing = Billing()
    @ObservationIgnored private var refreshing: Task<AccessState, Never>?

    static let trialLength: TimeInterval = 14 * 24 * 60 * 60
    /// How long after a subscription was last seen it still counts when the
    /// store can't be asked, and how long the data is kept after it.
    static let hold: TimeInterval = 60 * 24 * 60 * 60

    init(data: DataModel) {
        self.data = data
        settings = data.settings
        state = Self.resolve(subscribed: nil, settings: data.settings, now: Date())
    }

    /// Asks the store and, when needed, the ledger; one at a time.
    @discardableResult
    func refresh() async -> AccessState {
        if let refreshing { return await refreshing.value }
        let task = Task { await self.work() }
        refreshing = task
        let result = await task.value
        refreshing = nil
        return result
    }

    private func work() async -> AccessState {
        let now = Date()
        let subscribed = await billing.subscribed()
        if subscribed == true { settings.lastSubscribed = now }

        if settings.trialEnds == nil, !data.installed.isEmpty {
            await startTrial() // data from before the trial existed
        } else if settings.trialEnds != nil, !settings.trialConfirmed {
            await confirmTrial()
        }
        let next = Self.resolve(subscribed: subscribed, settings: settings, now: now)
        state = next
        if next == .expired, subscribed == false { removeDataWhenDue(now) }
        return next
    }

    private static func resolve(subscribed: Bool?, settings: Settings, now: Date) -> AccessState {
        if subscribed == true { return .subscribed }
        // The store can't be asked: a recent subscriber keeps access meanwhile.
        if subscribed == nil, let last = settings.lastSubscribed, now.timeIntervalSince(last) < hold { return .subscribed }
        guard let ends = settings.trialEnds else { return .notStarted }
        return now < ends ? .trial(ends: ends) : .expired
    }

    /// Starts the trial at the first download; no-op once started.
    func startTrial() async {
        guard settings.trialEnds == nil else { return }
        let fromServer = try? await trial.register()
        guard settings.trialEnds == nil else { return }
        // The ledger unreachable (or over its daily limit): count from now, confirm later.
        settings.trialConfirmed = fromServer != nil
        settings.trialEnds = fromServer ?? Date().addingTimeInterval(Self.trialLength)
        if state == .notStarted, let ends = settings.trialEnds, Date() < ends { state = .trial(ends: ends) }
    }

    private func confirmTrial() async {
        guard let fromServer = try? await trial.register(), let mine = settings.trialEnds else { return }
        // A reinstall started earlier: the ledger's (earlier) end wins.
        settings.trialEnds = min(fromServer, mine)
        settings.trialConfirmed = true
    }

    /// Deletes the kept databases: at once after a trial without subscription,
    /// and `hold` after a subscription was last seen, so a grace period or
    /// billing retry (payment trouble) does not cost the data.
    private func removeDataWhenDue(_ now: Date) {
        if let last = settings.lastSubscribed, now.timeIntervalSince(last) < Self.hold { return }
        if data.installed.isEmpty, settings.selected.isEmpty { return }
        data.removeAll()
        settings.dataRemovedNotice = true
    }
}
