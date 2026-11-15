import Foundation
import Observation
import StoreKit
import SwiftUI

/// The Limes subscription on the App Store: one subscription group with a
/// monthly and a yearly product, no store trial (the trial is the app's own,
/// see Access).
@MainActor
@Observable
final class Billing {
    static let monthly = "com.osprey74.limes.premium.monthly"
    static let yearly = "com.osprey74.limes.premium.yearly"
    static let ids = [monthly, yearly]

    /// The plans as the App Store offers them to this user, monthly first.
    private(set) var plans: [Product] = []
    /// False until the store has answered (or failed to) once.
    private(set) var loaded = false
    /// Why the last purchase or restore did not go through, for the plans screen.
    private(set) var error: String?
    /// A purchase or restore is under way.
    private(set) var busy = false

    /// Called when a purchase arrives, renews or is taken back.
    @ObservationIgnored var onChange: (() async -> Void)?
    @ObservationIgnored private var updates: Task<Void, Never>?

    init() {
        // Purchases made elsewhere (another device, Ask to Buy approved,
        // renewals, refunds) arrive here for as long as the app runs.
        updates = Task { [weak self] in
            for await update in Transaction.updates {
                if case let .verified(transaction) = update { await transaction.finish() }
                await self?.onChange?()
            }
        }
    }

    /// True when an active subscription is held, nil when the store can't be asked.
    func subscribed() async -> Bool? {
        for await entitlement in Transaction.currentEntitlements {
            if case let .verified(transaction) = entitlement, Self.ids.contains(transaction.productID),
               transaction.revocationDate == nil {
                return true
            }
        }
        // Nothing current: a billing grace period still counts as subscribed.
        for id in Self.ids {
            guard case let .verified(transaction)? = await Transaction.latest(for: id),
                  let group = transaction.subscriptionGroupID else { continue }
            guard let statuses = try? await Product.SubscriptionInfo.status(for: group) else { return nil }
            return statuses.contains { $0.state == .subscribed || $0.state == .inGracePeriod }
        }
        return false
    }

    /// Fetches the plans and prices to show.
    func loadPlans() async {
        if let products = try? await Product.products(for: Self.ids) {
            plans = Self.ids.compactMap { id in products.first { $0.id == id } }
        }
        loaded = true
    }

    /// `purchase` is the screen's `\.purchase` action, which knows where to
    /// show the store's sheet.
    func buy(_ plan: Product, with purchase: PurchaseAction) async {
        guard !busy else { return }
        busy = true
        defer { busy = false }
        error = nil
        do {
            switch try await purchase(plan) {
            case let .success(.verified(transaction)):
                await transaction.finish()
                await onChange?()
            case .success(.unverified):
                error = "購入を確認できませんでした。"
            case .pending:
                error = "承認待ちです。承認されると自動で有効になります。"
            case .userCancelled:
                break
            @unknown default:
                break
            }
        } catch let failure {
            error = Self.message(failure)
        }
    }

    /// Asks the App Store again for purchases made with this Apple Account.
    func restore() async {
        guard !busy else { return }
        busy = true
        defer { busy = false }
        error = nil
        do {
            try await AppStore.sync()
            await onChange?()
            if await subscribed() != true { error = "復元できる購入は見つかりませんでした。" }
        } catch StoreKitError.userCancelled {
        } catch let failure {
            error = Self.message(failure)
        }
    }

    private static func message(_ failure: Error) -> String {
        switch failure {
        case StoreKitError.networkError, StoreKitError.systemError:
            return "App Store に接続できませんでした。通信できる環境でもう一度お試しください"
        case StoreKitError.notAvailableInStorefront, Product.PurchaseError.productUnavailable:
            return "このプランは現在登録できません"
        case Product.PurchaseError.purchaseNotAllowed:
            return "この端末では購入が許可されていません"
        default:
            return "登録を完了できませんでした（\(failure.localizedDescription)）"
        }
    }
}
