import StoreKit
import StoreKitTest
import XCTest
@testable import Limes

/// Access against Xcode's test store (Limes.storekit): what the app does when
/// the trial is over, on subscribing from there, and when the subscription
/// lapses.
///
/// The tests run inside the app, on its own settings and database store: they
/// put the settings back afterwards, but the kept databases are deleted along
/// the way. They download one prefecture, so they need the network.
@MainActor
final class AccessTests: XCTestCase {
    private var session: SKTestSession!
    private var settings: Settings!
    private var data: DataModel!
    private var access: Access!
    private var saved: [String: Any] = [:]

    private static let keys = [
        "selected_prefectures", "wifi_only", "auto_update", "last_checked",
        "trial_ends", "trial_confirmed", "last_subscribed", "data_removed_notice",
    ]
    private static let prefecture = "tokushima"

    override func setUp() async throws {
        let store = UserDefaults.standard
        saved = [:]
        for key in Self.keys { saved[key] = store.object(forKey: key) }

        print("STEP setup a")
        session = try SKTestSession(configurationFileNamed: "Limes")
        print("STEP setup b")
        session.disableDialogs = true
        session.clearTransactions()

        print("STEP setup c")
        settings = Settings()
        data = DataModel(settings: settings)
        access = Access(data: data)
        data.access = access
        print("STEP setup d")
    }

    override func tearDown() async throws {
        data.stop()
        session.clearTransactions()
        let store = UserDefaults.standard
        for key in Self.keys {
            if let value = saved[key] { store.set(value, forKey: key) } else { store.removeObject(forKey: key) }
        }
    }

    /// The trial over and never subscribed.
    private func endTrial() {
        settings.trialEnds = Date().addingTimeInterval(-60 * 60)
        settings.trialConfirmed = true
        settings.lastSubscribed = nil
        settings.dataRemovedNotice = false
    }

    private func waitFor(_ what: String, seconds: Double, _ done: () async -> Bool) async {
        let until = Date().addingTimeInterval(seconds)
        while Date() < until {
            if await done() { return }
            try? await Task.sleep(for: .milliseconds(250))
        }
        XCTFail("timed out: \(what)")
    }

    func testPlansComeWithTheirPrices() async {
        await access.billing.loadPlans()
        XCTAssertEqual(access.billing.plans.map(\.id), Billing.ids)
        XCTAssertEqual(access.billing.plans.map(\.displayPrice), ["¥500", "¥4,800"])
    }

    func testTrialOverThenSubscribedThenLapsed() async throws {
        // The trial ends without a subscription: the data goes at once, and the app says so.
        endTrial()
        settings.selected = [Self.prefecture]
        var state = await access.refresh()
        XCTAssertEqual(state, .expired)
        XCTAssertTrue(settings.selected.isEmpty)
        XCTAssertTrue(data.installed.isEmpty)
        XCTAssertTrue(settings.dataRemovedNotice)
        settings.dataRemovedNotice = false

        // No downloads meanwhile.
        data.download([Self.prefecture])
        try await Task.sleep(for: .seconds(1))
        XCTAssertTrue(settings.selected.isEmpty)

        // Nothing to restore.
        await access.billing.restore()
        XCTAssertEqual(access.billing.error, "復元できる購入は見つかりませんでした。")

        // Subscribing from there gives everything back.
        _ = try await session.buyProduct(identifier: Billing.monthly)
        state = await access.refresh()
        XCTAssertEqual(state, .subscribed)
        XCTAssertNotNil(settings.lastSubscribed)

        settings.wifiOnly = false
        data.download([Self.prefecture])
        await waitFor("download", seconds: 120) { data.installed.contains { $0.prefecture == Self.prefecture } }

        // Restoring with the subscription held finds it.
        await access.billing.restore()
        XCTAssertNil(access.billing.error)
        XCTAssertEqual(access.state, .subscribed)

        // The subscription ends: the limits are back, the data stays for now.
        try session.expireSubscription(productIdentifier: Billing.monthly)
        await waitFor("expiry", seconds: 10) { await access.billing.subscribed() == false }
        state = await access.refresh()
        XCTAssertEqual(state, .expired)
        XCTAssertFalse(data.installed.isEmpty)
        XCTAssertEqual(settings.selected, [Self.prefecture])
        XCTAssertFalse(settings.dataRemovedNotice)

        // Just short of the hold: still kept.
        settings.lastSubscribed = Date().addingTimeInterval(-(Access.hold - 60 * 60))
        _ = await access.refresh()
        XCTAssertFalse(data.installed.isEmpty)

        // Past it: deleted, and the app says so.
        settings.lastSubscribed = Date().addingTimeInterval(-(Access.hold + 60 * 60))
        state = await access.refresh()
        XCTAssertEqual(state, .expired)
        XCTAssertTrue(data.installed.isEmpty)
        XCTAssertTrue(settings.selected.isEmpty)
        XCTAssertTrue(settings.dataRemovedNotice)
    }

    func testRefundEndsTheSubscription() async throws {
        endTrial()
        let transaction = try await session.buyProduct(identifier: Billing.yearly)
        var state = await access.refresh()
        XCTAssertEqual(state, .subscribed)

        try session.refundTransaction(identifier: UInt(transaction.id))
        await waitFor("refund", seconds: 10) { await access.billing.subscribed() == false }
        state = await access.refresh()
        XCTAssertEqual(state, .expired)
    }

    /// A renewal that fails with the billing grace period on: still subscribed.
    func testGracePeriodCountsAsSubscribed() async throws {
        print("STEP 1")
        endTrial()
        print("STEP 2")
        session.billingGracePeriodIsEnabled = true
        print("STEP 3")
        session.shouldEnterBillingRetryOnRenewal = true
        print("STEP 4")
        session.timeRate = .oneRenewalEveryTwoSeconds
        print("STEP 5")
        _ = try await session.buyProduct(identifier: Billing.monthly)

        print("STEP 6")
        await waitFor("grace period", seconds: 30) {
            guard case let .verified(transaction)? = await Transaction.latest(for: Billing.monthly),
                  let group = transaction.subscriptionGroupID,
                  let statuses = try? await Product.SubscriptionInfo.status(for: group) else { return false }
            return statuses.contains { $0.state == .inGracePeriod }
        }
        print("STEP 7")
        let subscribed = await access.billing.subscribed()
        print("STEP 8")
        XCTAssertEqual(subscribed, true)
        print("STEP 9")
        let state = await access.refresh()
        print("STEP 10")
        XCTAssertEqual(state, .subscribed)
    }
}
