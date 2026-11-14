import SwiftUI

let disclaimer = "表示される速度は公開データからの推定です。実際の最高速度は現地の道路標識・道路標示に従ってください。本アプリは速度違反の有無を保証しません。"

let attribution = """
    出典：『交通規制情報』（公益財団法人日本道路交通情報センター）（https://www.jartic.or.jp/service/opendata/）を加工して作成
    道路データ：© OpenStreetMap contributors（ODbL）
    祝日：内閣府「国民の祝日について」に基づき計算
    """

struct SettingsScreen: View {
    let data: DataModel
    var onBack: () -> Void
    var onDownload: () -> Void

    var body: some View {
        @Bindable var settings = data.settings
        Page {
            VStack(alignment: .leading, spacing: 12) {
                BackButton(label: "走行画面", action: onBack)
                Text("設定").font(.system(size: 30, weight: .bold)).foregroundStyle(Palette.text)
            }

            CardSection("データの更新") {
                ToggleRow(label: "自動更新", note: "起動時と1日1回、新しい版を確認して取得します", isOn: $settings.autoUpdate, first: true)
                ToggleRow(label: "Wi-Fi 接続時のみ", note: "モバイル回線のときは待機し、Wi-Fi につながると取得します", isOn: $settings.wifiOnly)
                CardRow {
                    Text("最終確認").font(.system(size: 15)).foregroundStyle(Palette.text)
                    Spacer()
                    Text(checkedLabel(settings.lastChecked)).font(.system(size: 14)).foregroundStyle(Palette.muted)
                }
                if let (text, color) = updateStatus(data.status, wifiOnly: settings.wifiOnly) {
                    CardRow { StatusLabel(text: text, color: color) }
                }
                FlatButton(text: "今すぐ更新を確認", wide: true) { data.checkNow() }
                    .padding(16)
            }

            StorageSection(data: data, autoAdd: $settings.autoAddCurrent, onDownload: onDownload)

            CardSection("運転支援") {
                CardRow(first: true) {
                    Text("車種").font(.system(size: 15)).foregroundStyle(Palette.text)
                    Spacer()
                    Text("普通自動車").font(.system(size: 14)).foregroundStyle(Palette.muted)
                }
                ToggleRow(label: "画面を常に点灯", isOn: $settings.keepAwake)
            }

            CardSection("情報") {
                CardRow(first: true, minHeight: 52) {
                    Text("アプリのバージョン").font(.system(size: 15)).foregroundStyle(Palette.text)
                    Spacer()
                    Text(Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "")
                        .font(.system(size: 14)).foregroundStyle(Palette.muted)
                }
                ExpandableText(title: "データの出典とライセンス", text: attribution)
                ExpandableText(title: "免責事項", text: disclaimer)
            }

            Text(disclaimer)
                .font(.system(size: 12)).lineSpacing(6).foregroundStyle(Palette.muted)
                .padding(.horizontal, 4)
        }
        .onAppear {
            data.refreshInstalled()
            data.loadPublished()
        }
        .onChange(of: settings.wifiOnly) { data.settingsChanged() }
        .onChange(of: settings.autoUpdate) { data.settingsChanged() }
    }
}

private func checkedLabel(_ date: Date?) -> String {
    guard let date else { return "未確認" }
    var calendar = Calendar(identifier: .gregorian)
    calendar.timeZone = TimeZone(identifier: "Asia/Tokyo")!
    let format = DateFormatter()
    format.calendar = calendar
    format.timeZone = calendar.timeZone
    format.locale = Locale(identifier: "ja_JP")
    if calendar.isDate(date, inSameDayAs: Date()) {
        format.dateFormat = "H:mm"
        return "今日 " + format.string(from: date)
    }
    format.dateFormat = "M月d日 H:mm"
    return format.string(from: date)
}

/// What the update last started is doing; nil when there is nothing to say.
private func updateStatus(_ status: UpdateStatus?, wifiOnly: Bool) -> (String, Color)? {
    switch status {
    case nil:
        return nil
    case .waiting:
        return (wifiOnly ? "Wi-Fi の接続を待っています" : "通信の接続を待っています", Palette.waiting)
    case .checking:
        return ("新しい版を確認しています", Palette.accent)
    case let .downloading(slug, done, total):
        return ("\(prefecture(slug)?.name ?? slug)を取得しています（\(done + 1)/\(total)）", Palette.accent)
    case let .finished(installed, mismatched, appUpdate):
        if appUpdate > 0 { return ("新しいデータを使うにはアプリの更新が必要です", Palette.waiting) }
        if mismatched > 0 { return ("\(mismatched) 件の取得に失敗しました。次回の確認で再取得します", Palette.waiting) }
        if installed > 0 { return ("\(installed) 件を更新しました", Palette.ok) }
        return ("すべて最新です", Palette.ok)
    case .failed:
        return ("更新に失敗しました", Palette.danger)
    }
}

private struct RegionUsage: Identifiable {
    let name: String
    let color: Color
    let prefs: [InstalledDatabase]
    var bytes: Int64 { prefs.reduce(0) { $0 + Int64($1.bytes) } }
    var id: String { name }
}

private struct StorageSection: View {
    let data: DataModel
    @Binding var autoAdd: Bool
    var onDownload: () -> Void

    @State private var open: String?
    @State private var confirm: String?

    var body: some View {
        let usage = regions.enumerated().map { i, name in
            RegionUsage(name: name, color: Palette.regions[i], prefs: data.installed.filter { prefecture($0.prefecture)?.region == name })
        }.filter { $0.bytes > 0 }
        let total = usage.reduce(0) { $0 + $1.bytes }

        CardSection(title: "保持データ") {
            Text("合計 \(sizeLabel(total))").font(.system(size: 12)).foregroundStyle(Palette.muted)
        } content: {
            if total == 0 {
                Text("保持しているデータはありません。走行する地域のデータをダウンロードしてください。")
                    .font(.system(size: 14)).lineSpacing(6).foregroundStyle(Palette.muted)
                    .padding(.horizontal, 16).padding(.vertical, 20)
            } else {
                VStack(spacing: 12) {
                    // One bar for the total, a segment per region.
                    GeometryReader { geo in
                        let gaps = CGFloat(usage.count - 1) * 2
                        HStack(spacing: 2) {
                            ForEach(usage) { r in
                                r.color.frame(width: max(0, (geo.size.width - gaps) * CGFloat(r.bytes) / CGFloat(total)))
                            }
                        }
                    }
                    .frame(height: 14)
                    .background(Palette.line)
                    .clipShape(RoundedRectangle(cornerRadius: 7))
                    .accessibilityElement()
                    .accessibilityLabel("保持データ 合計 \(sizeLabel(total))：" + usage.map { "\($0.name) \(sizeLabel($0.bytes))" }.joined(separator: "、"))

                    LazyVGrid(columns: [GridItem(.flexible(), spacing: 16), GridItem(.flexible())], spacing: 12) {
                        ForEach(usage) { r in
                            HStack(spacing: 6) {
                                RoundedRectangle(cornerRadius: 2).fill(r.color).frame(width: 8, height: 8)
                                Text(r.name).font(.system(size: 12)).foregroundStyle(Palette.sub)
                                Spacer(minLength: 0)
                                Text(sizeLabel(r.bytes)).font(.system(size: 12)).foregroundStyle(Palette.muted)
                            }
                        }
                    }
                }
                .padding(16)

                ForEach(usage) { r in
                    RegionRow(
                        region: r, total: total, open: open == r.name, confirm: $confirm,
                        published: data.published, wifiOnly: data.settings.wifiOnly,
                        onToggle: {
                            open = open == r.name ? nil : r.name
                            confirm = nil
                        },
                        onRemove: {
                            data.remove($0)
                            confirm = nil
                        }
                    )
                }
            }
            ToggleRow(label: "現在地の都道府県を自動で追加", note: "県境を越えると隣の県も取得します", isOn: $autoAdd)
            CardRow(minHeight: 52, action: onDownload) {
                Image(systemName: "plus").font(.system(size: 15, weight: .semibold)).foregroundStyle(Palette.accent)
                Text("地方・都道府県のデータをダウンロード")
                    .font(.system(size: 15, weight: .medium)).foregroundStyle(Palette.accent)
            }
        }
    }
}

private struct RegionRow: View {
    let region: RegionUsage
    let total: Int64
    let open: Bool
    @Binding var confirm: String?
    let published: [String: Published]
    let wifiOnly: Bool
    var onToggle: () -> Void
    var onRemove: ([String]) -> Void

    var body: some View {
        VStack(spacing: 0) {
            RowLine()
            Button(action: onToggle) {
                VStack(spacing: 8) {
                    HStack(spacing: 8) {
                        RoundedRectangle(cornerRadius: 2).fill(region.color).frame(width: 8, height: 8)
                        Text(region.name).font(.system(size: 15)).foregroundStyle(Palette.text)
                        Text("\(region.prefs.count) 件").font(.system(size: 12)).foregroundStyle(Palette.muted)
                        Spacer()
                        Text(sizeLabel(region.bytes)).font(.system(size: 15, weight: .semibold)).foregroundStyle(Palette.text)
                        Chevron(open: open)
                    }
                    GeometryReader { geo in
                        RoundedRectangle(cornerRadius: 3).fill(region.color)
                            .frame(width: geo.size.width * CGFloat(region.bytes) / CGFloat(total))
                    }
                    .frame(height: 6)
                    .background(Palette.line, in: RoundedRectangle(cornerRadius: 3))
                }
                .padding(.horizontal, 16).padding(.vertical, 10)
                .frame(minHeight: 60)
                .contentShape(Rectangle())
            }
            .buttonStyle(.plain)
            .accessibilityHint(open ? "閉じる" : "開く")

            if open {
                VStack(spacing: 0) {
                    ForEach(region.prefs, id: \.prefecture) { p in
                        prefectureRow(p)
                    }
                    // Bulk delete only when the region holds two or more prefectures.
                    if region.prefs.count >= 2 { bulkDelete }
                }
                .padding(.horizontal, 16).padding(.bottom, 12)
            }
        }
    }

    @ViewBuilder
    private func prefectureRow(_ p: InstalledDatabase) -> some View {
        let name = prefecture(p.prefecture)?.name ?? p.prefecture
        RowLine(color: Palette.inset)
        HStack(spacing: 10) {
            VStack(alignment: .leading, spacing: 2) {
                Text(name).font(.system(size: 14)).foregroundStyle(Palette.text)
                Text("\(versionLabel(p.version)) ・ \(sizeLabel(Int64(p.bytes)))")
                    .font(.system(size: 12)).foregroundStyle(Palette.muted)
            }
            Spacer()
            if confirm == p.prefecture {
                FlatButton(text: "やめる") { confirm = nil }
                FlatButton(text: "削除", filled: Palette.danger) { onRemove([p.prefecture]) }
            } else {
                if let pub = published[p.prefecture] {
                    if pub.version == p.version {
                        StatusLabel(text: "最新", color: Palette.ok)
                    } else {
                        StatusLabel(text: wifiOnly ? "更新待ち（Wi-Fi）" : "更新待ち", color: Palette.waiting)
                    }
                }
                Button { confirm = p.prefecture } label: {
                    Image(systemName: "trash").font(.system(size: 16)).foregroundStyle(Palette.muted)
                        .frame(width: 44, height: 44)
                }
                .accessibilityLabel("\(name)のデータを削除")
            }
        }
        .frame(minHeight: 56)
    }

    @ViewBuilder
    private var bulkDelete: some View {
        let key = "region:\(region.name)"
        if confirm == key {
            VStack(alignment: .leading, spacing: 10) {
                Text("\(region.name)の \(region.prefs.count) 件（\(sizeLabel(region.bytes))）を削除します。走行中にこの地方では速度を表示できなくなります。")
                    .font(.system(size: 13)).lineSpacing(5).foregroundStyle(Palette.sub)
                HStack(spacing: 8) {
                    FlatButton(text: "やめる", wide: true) { confirm = nil }
                    FlatButton(text: "すべて削除", filled: Palette.danger, wide: true) { onRemove(region.prefs.map(\.prefecture)) }
                }
            }
            .padding(12)
            .background(Palette.inset, in: Shapes.button)
            .padding(.top, 8)
        } else {
            FlatButton(text: "\(region.name)のデータをすべて削除", textColor: Palette.dangerText, wide: true) { confirm = key }
                .padding(.top, 8)
        }
    }
}

private struct ExpandableText: View {
    let title: String
    let text: String
    @State private var open = false

    var body: some View {
        CardRow(minHeight: 52, action: { open.toggle() }) {
            Text(title).font(.system(size: 15)).foregroundStyle(Palette.text)
            Spacer()
            Chevron(open: open)
        }
        if open {
            Text(text)
                .font(.system(size: 13)).lineSpacing(6).foregroundStyle(Palette.sub)
                .padding(.horizontal, 16).padding(.bottom, 14)
        }
    }
}
