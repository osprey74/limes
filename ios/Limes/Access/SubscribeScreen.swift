import SwiftUI

/// The plans, what they include, and what stays free.
struct SubscribeScreen: View {
    let data: DataModel
    let access: Access
    let backLabel: String
    var onBack: () -> Void

    var body: some View {
        let removed = data.settings.dataRemovedNotice
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
                    // StoreKit 2 comes next; until then there is nothing to buy.
                    Text("プランの表示と登録は準備中です。")
                        .font(.system(size: 14)).lineSpacing(6).foregroundStyle(Palette.muted)
                        .padding(16)
                }
            }
        }
        .task { await access.refresh() }
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
