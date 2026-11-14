import SwiftUI

/// Choose regions and prefectures to keep on the device.
struct DownloadScreen: View {
    let data: DataModel
    var onBack: () -> Void

    @State private var selected: Set<String> = []
    @State private var open: String?

    var body: some View {
        @Bindable var settings = data.settings
        let held = Set(data.installed.map(\.prefecture))
        let chosen = selected.compactMap { data.published[$0] }
        Page(spacing: 20) {
            VStack(alignment: .leading, spacing: 12) {
                BackButton(label: "設定", action: onBack)
                Text("データのダウンロード").font(.system(size: 26, weight: .bold)).foregroundStyle(Palette.text)
                Text("走行する地域のデータを端末に保存します。保存したデータで判定するので、走行中は通信しません。")
                    .font(.system(size: 14)).lineSpacing(7).foregroundStyle(Palette.sub)
            }

            if !data.access.state.entitled {
                Text("無料期間が終わったため、ダウンロードできません。設定の「有料プラン」から登録できます。")
                    .font(.system(size: 14)).lineSpacing(6).foregroundStyle(Palette.waiting)
            }

            ToggleRow(label: "Wi-Fi 接続時のみ", note: "モバイル回線のときは待機し、Wi-Fi につながると始まります", isOn: $settings.wifiOnly, first: true)
                .background(Palette.card)
                .clipShape(Shapes.card)

            CardSection(title: "地方・都道府県") {
                Text("ダウンロード量 ／ 端末の容量").font(.system(size: 12)).foregroundStyle(Palette.muted)
            } content: {
                if data.published.isEmpty {
                    Text("配信データの一覧を取得できませんでした。通信できる環境で開き直してください。")
                        .font(.system(size: 14)).lineSpacing(6).foregroundStyle(Palette.muted)
                        .padding(.horizontal, 16).padding(.vertical, 20)
                } else {
                    ForEach(Array(regions.enumerated()), id: \.element) { i, region in
                        RegionChooser(
                            name: region, first: i == 0,
                            prefs: prefectures.filter { $0.region == region && data.published[$0.slug] != nil },
                            published: data.published, held: held, selected: selected,
                            open: open == region,
                            onToggle: { open = open == region ? nil : region },
                            onSelect: { slugs, on in
                                if on { selected.formUnion(slugs) } else { selected.subtract(slugs) }
                            }
                        )
                    }
                }
            }

            VStack(alignment: .leading, spacing: 12) {
                HStack(spacing: 8) {
                    Figure(label: "選択中", value: "\(selected.count) 件")
                    Figure(label: "ダウンロード量", value: sizeLabel(chosen.reduce(0) { $0 + $1.downloadBytes }))
                    Figure(label: "端末の容量", value: sizeLabel(chosen.reduce(0) { $0 + $1.diskBytes }))
                }
                FlatButton(
                    text: selected.isEmpty ? "都道府県を選んでください" : settings.wifiOnly ? "ダウンロード（Wi-Fi 接続時）" : "ダウンロード",
                    filled: Palette.accent, wide: true, height: 50, enabled: !selected.isEmpty
                ) {
                    data.download(selected)
                    selected = []
                    onBack()
                }
                Text("ダウンロードが終わるまで、アプリを開いたままにしてください。保存済みのデータは設定の「保持データ」から削除できます。")
                    .font(.system(size: 12)).lineSpacing(5).foregroundStyle(Palette.muted)
            }
            .padding(16)
            .background(Palette.card)
            .clipShape(Shapes.card)
        }
        .onAppear { data.loadPublished() }
        .onChange(of: settings.wifiOnly) { data.settingsChanged() }
    }
}

private struct Figure: View {
    let label: String
    let value: String

    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(label).font(.system(size: 12)).foregroundStyle(Palette.muted)
            Text(value).font(.system(size: 20, weight: .bold)).foregroundStyle(Palette.text)
                .lineLimit(1).minimumScaleFactor(0.7)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

private enum Check {
    case off, some, on
}

/// A 48-point checkbox in the design's colors.
private struct Checkbox: View {
    let state: Check
    var enabled = true
    let label: String
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            Image(systemName: state == .on ? "checkmark.square.fill" : state == .some ? "minus.square.fill" : "square")
                .font(.system(size: 22))
                .foregroundStyle(!enabled ? Palette.border : state == .off ? Palette.faint : Palette.accent)
                .frame(width: 48, height: 48)
                .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .disabled(!enabled)
        .accessibilityLabel(label)
        .accessibilityValue(state == .on ? "選択済み" : state == .some ? "一部選択" : "未選択")
    }
}

private struct RegionChooser: View {
    let name: String
    let first: Bool
    let prefs: [Prefecture]
    let published: [String: Published]
    let held: Set<String>
    let selected: Set<String>
    let open: Bool
    var onToggle: () -> Void
    var onSelect: ([String], Bool) -> Void

    var body: some View {
        let choosable = prefs.map(\.slug).filter { !held.contains($0) }
        let picked = choosable.filter(selected.contains).count
        let state: Check = !choosable.isEmpty && picked == choosable.count ? .on : picked > 0 ? .some : .off
        let heldCount = prefs.count - choosable.count
        let download = prefs.reduce(Int64(0)) { $0 + (published[$1.slug]?.downloadBytes ?? 0) }
        let disk = prefs.reduce(Int64(0)) { $0 + (published[$1.slug]?.diskBytes ?? 0) }

        VStack(spacing: 0) {
            if !first { RowLine() }
            HStack(spacing: 0) {
                Checkbox(state: state, enabled: !choosable.isEmpty, label: "\(name)をまとめて選ぶ") {
                    onSelect(choosable, state != .on)
                }
                Button(action: onToggle) {
                    HStack(spacing: 8) {
                        VStack(alignment: .leading, spacing: 2) {
                            Text(name).font(.system(size: 15)).foregroundStyle(Palette.text)
                            Text("\(prefs.count) 都道府県"
                                + (heldCount > 0 ? " ・ \(heldCount) 件保持済み" : "")
                                + (picked > 0 ? " ・ \(picked) 件選択" : ""))
                                .font(.system(size: 12)).foregroundStyle(Palette.muted)
                        }
                        Spacer()
                        Text("\(sizeLabel(download)) ／ \(sizeLabel(disk))")
                            .font(.system(size: 13, weight: .semibold)).foregroundStyle(Palette.sub)
                        Chevron(open: open)
                    }
                    .padding(.horizontal, 4)
                    .frame(minHeight: 48)
                    .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .accessibilityHint(open ? "閉じる" : "開く")
            }
            .padding(.leading, 4).padding(.trailing, 8)
            .frame(minHeight: 64)

            if open {
                VStack(spacing: 0) {
                    ForEach(prefs) { p in
                        RowLine(color: Palette.inset)
                        HStack(spacing: 0) {
                            if held.contains(p.slug) {
                                Image(systemName: "checkmark").font(.system(size: 15, weight: .semibold))
                                    .foregroundStyle(Palette.ok).frame(width: 48, height: 48)
                                Text(p.name).font(.system(size: 14)).foregroundStyle(Palette.text).padding(.leading, 4)
                                Spacer()
                                Text("保持済み").font(.system(size: 12)).foregroundStyle(Palette.ok)
                            } else {
                                let on = selected.contains(p.slug)
                                Checkbox(state: on ? .on : .off, label: "\(p.name)を選ぶ") { onSelect([p.slug], !on) }
                                Text(p.name).font(.system(size: 14)).foregroundStyle(Palette.text).padding(.leading, 4)
                                Spacer()
                                if let pub = published[p.slug] {
                                    Text("\(sizeLabel(pub.downloadBytes)) ／ \(sizeLabel(pub.diskBytes))")
                                        .font(.system(size: 13, weight: .semibold)).foregroundStyle(Palette.sub)
                                }
                            }
                        }
                        .frame(minHeight: 52)
                    }
                }
                .padding(.leading, 4).padding(.trailing, 16).padding(.bottom, 8)
            }
        }
    }
}
