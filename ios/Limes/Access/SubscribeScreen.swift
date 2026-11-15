import StoreKit
import SwiftUI

/// The plans, what they include, and what stays free.
struct SubscribeScreen: View {
    let data: DataModel
    let access: Access
    let backLabel: String
    var onBack: () -> Void

    @Environment(\.purchase) private var purchase
    @State private var managing = false

    var body: some View {
        let removed = data.settings.dataRemovedNotice
        let billing = access.billing
        Page(spacing: 20) {
            VStack(alignment: .leading, spacing: 12) {
                BackButton(label: backLabel, action: onBack)
                Text("有料プラン").font(.system(size: 30, weight: .bold)).foregroundStyle(Palette.text)
            }

            if removed {
                Notice(text: "無料期間が終わったため、保存していた道路データを削除しました。登録すると、もう一度ダウンロードできます。", color: Palette.waiting)
            }
            Notice(text: statusText(access.state), color: access.state == .expired ? Palette.waiting : Palette.ok)

            CardSection("有料プランでできること") {
                Bullet(text: "走行中の道路の最高速度（推定）の表示", first: true)
                Bullet(text: "都道府県データのダウンロードと自動更新")
                Bullet(text: "登録しなくても、GPS による現在の速度はいつでも表示されます")
            }

            if access.state != .subscribed {
                CardSection("プラン") {
                    if billing.plans.isEmpty {
                        Text(billing.loaded
                            ? "App Store に接続できないため、プランを表示できません。通信できる環境で開き直してください。"
                            : "プランを読み込んでいます…")
                            .font(.system(size: 14)).lineSpacing(6).foregroundStyle(Palette.muted)
                            .padding(16)
                    } else {
                        let monthly = billing.plans.first { $0.id == Billing.monthly }
                        ForEach(Array(billing.plans.enumerated()), id: \.element.id) { i, plan in
                            PlanRow(plan: plan, monthly: monthly, first: i == 0, enabled: !billing.busy) {
                                Task { await billing.buy(plan, with: purchase) }
                            }
                        }
                    }
                }
                if let error = billing.error {
                    Text(error).font(.system(size: 13)).lineSpacing(5).foregroundStyle(Palette.dangerText)
                }
            }

            Text("有料プランは App Store のサブスクリプションです。期間の終わりに自動で更新され、同じ料金が請求されます。"
                + "解約は「サブスクリプションを管理」からいつでもでき、解約しても期間の終わりまでは使えます。")
                .font(.system(size: 12)).lineSpacing(6).foregroundStyle(Palette.muted)
            VStack(spacing: 12) {
                if access.state != .subscribed {
                    FlatButton(text: "購入を復元", wide: true, enabled: !billing.busy) {
                        Task { await billing.restore() }
                    }
                }
                FlatButton(text: "サブスクリプションを管理", wide: true) { managing = true }
            }
        }
        .manageSubscriptionsSheet(isPresented: $managing)
        .task {
            await billing.loadPlans()
            await access.refresh()
        }
        // The deletion notice is said once: cleared on leaving this screen.
        .onDisappear { if removed { data.settings.dataRemovedNotice = false } }
    }
}

private func statusText(_ state: AccessState) -> String {
    switch state {
    case .notStarted:
        return "データを初めてダウンロードした日から14日間、すべての機能を無料で使えます。"
    case let .trial(ends):
        let days = max(1, Int(ends.timeIntervalSinceNow / (24 * 60 * 60)) + 1)
        return "無料期間中です。あと\(days)日（\(monthDay(ends))まで）"
    case .subscribed:
        return "有料プランに登録済みです。"
    case .expired:
        return "無料期間は終了しました。"
    }
}

/// "11月28日" in Japan time.
func monthDay(_ date: Date) -> String {
    let format = DateFormatter()
    format.calendar = Calendar(identifier: .gregorian)
    format.timeZone = TimeZone(identifier: "Asia/Tokyo")
    format.locale = Locale(identifier: "ja_JP")
    format.dateFormat = "M月d日"
    return format.string(from: date)
}

private struct Notice: View {
    let text: String
    let color: Color

    var body: some View {
        Text(text)
            .font(.system(size: 14)).lineSpacing(6).foregroundStyle(color)
            .padding(16)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(Palette.card)
            .clipShape(Shapes.card)
    }
}

private struct Bullet: View {
    let text: String
    var first = false

    var body: some View {
        CardRow(first: first) {
            Text(text).font(.system(size: 15)).lineSpacing(4).foregroundStyle(Palette.text)
        }
    }
}

private struct PlanRow: View {
    let plan: Product
    let monthly: Product?
    let first: Bool
    let enabled: Bool
    let onBuy: () -> Void

    var body: some View {
        let yearly = plan.id == Billing.yearly
        CardRow(first: first) {
            VStack(alignment: .leading, spacing: 2) {
                HStack(spacing: 12) {
                    VStack(alignment: .leading, spacing: 2) {
                        Text(yearly ? "年額" : "月額")
                            .font(.system(size: 15, weight: .medium)).foregroundStyle(Palette.text)
                        Text(plan.displayPrice + (yearly ? "／年" : "／月"))
                            .font(.system(size: 18, weight: .bold)).foregroundStyle(Palette.text)
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                    FlatButton(text: "登録する", filled: Palette.accent, enabled: enabled, action: onBuy)
                }
                // Under both, the full width of the row: one line, never wrapped.
                if yearly, let note = yearlyNote(plan, monthly) {
                    Text(note).font(.system(size: 12)).foregroundStyle(Palette.muted)
                        .lineLimit(1).minimumScaleFactor(0.7)
                }
            }
        }
    }
}

/// "月あたり ¥400（月額の12か月分より20%お得）", worked out from the prices
/// on the screen. Both figures are rounded down, so neither is overstated.
private func yearlyNote(_ yearly: Product, _ monthly: Product?) -> String? {
    let year = amount(yearly)
    let each = floor(year / 12)
    guard each > 0 else { return nil }
    let perMonth = "月あたり " + each.formatted(yearly.priceFormatStyle)
    guard let monthly, monthly.priceFormatStyle.currencyCode == yearly.priceFormatStyle.currencyCode else { return perMonth }
    let full = amount(monthly) * 12
    guard full > year else { return perMonth }
    let saving = NSDecimalNumber(decimal: floor((full - year) * 100 / full)).intValue
    return saving > 0 ? "\(perMonth)（月額の12か月分より\(saving)%お得）" : perMonth
}

/// The price as a number, read from the price shown ("¥4,800"), so the note
/// always agrees with it. `Product.price` is the fallback only: Xcode's test
/// store gives 4 there for ¥4,800 (it sends "4,800", read up to the comma).
private func amount(_ product: Product) -> Decimal {
    (try? Decimal(product.displayPrice, format: product.priceFormatStyle)) ?? product.price
}

private func floor(_ value: Decimal) -> Decimal {
    var value = value
    var result = Decimal()
    NSDecimalRound(&result, &value, 0, .down)
    return result
}
