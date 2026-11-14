import SwiftUI

private let staleAfter: TimeInterval = 5
private let signRed = Color(hex: 0xD7262E)

/// The ring when the confidence is low: the same red, faded toward white.
private let signRedFaded = Color(hex: 0xEB9297)
private let signBlue = Color(hex: 0x1D4E9E)

private let disclaimerShort = "表示される速度は公開データからの推定です。実際の最高速度は現地の標識・標示に従ってください。"

/// The estimated maximum speed of the road as a sign, next to the GPS speed.
struct DriveScreen: View {
    let data: DataModel
    let drive: DriveModel
    var onSettings: () -> Void
    var onSubscribe: () -> Void

    @Environment(\.scenePhase) private var scenePhase

    var body: some View {
        // Ticks every second so stale fixes (a tunnel) are noticed.
        TimelineView(.periodic(from: .now, by: 1)) { timeline in
            content(now: timeline.date)
        }
        .background(Palette.ground.ignoresSafeArea())
        .onAppear { resume() }
        .onDisappear { pause() }
        .onChange(of: scenePhase) { _, phase in
            if phase == .active { resume() } else { pause() }
        }
    }

    private func resume() {
        guard scenePhase == .active else { return }
        drive.start()
        UIApplication.shared.isIdleTimerDisabled = data.settings.keepAwake
    }

    private func pause() {
        drive.stop()
        UIApplication.shared.isIdleTimerDisabled = false
    }

    private func content(now: Date) -> some View {
        let state = drive.state
        let stale = state.fixAt.map { now.timeIntervalSince($0) > staleAfter } ?? true
        let note: String? =
            if !drive.permitted { "位置情報を許可すると速度を表示します" }
            else if data.installed.isEmpty { "データがありません。設定からダウンロードしてください" }
            else { nil }

        let locked = !data.access.state.entitled

        return GeometryReader { geo in
            let landscape = geo.size.width > geo.size.height
            VStack(spacing: 0) {
                topBar
                if landscape {
                    HStack(spacing: 0) {
                        limit(locked: locked, state: state, stale: stale, sign: 170, note: note)
                            .frame(maxWidth: .infinity, maxHeight: .infinity)
                        Palette.line.frame(width: 1).padding(.vertical, 8)
                        SpeedPanel(state: state, stale: stale, figure: 110)
                            .frame(maxWidth: .infinity, maxHeight: .infinity)
                    }
                    .padding(.horizontal, 32)
                } else {
                    limit(locked: locked, state: state, stale: stale, sign: 220, note: note)
                        .frame(maxWidth: .infinity, maxHeight: .infinity)
                    Palette.line.frame(height: 1).padding(.horizontal, 16)
                    SpeedPanel(state: state, stale: stale, figure: 140)
                        .frame(maxWidth: .infinity, maxHeight: .infinity)
                }
                Text(disclaimerShort)
                    .font(.system(size: 12))
                    .lineSpacing(5)
                    .foregroundStyle(Palette.muted)
                    .multilineTextAlignment(.center)
                    .fixedSize(horizontal: false, vertical: true)
                    .padding(.horizontal, 24)
                    .padding(.vertical, landscape ? 6 : 10)
            }
        }
    }

    @ViewBuilder
    private func limit(locked: Bool, state: DriveState, stale: Bool, sign: CGFloat, note: String?) -> some View {
        if locked {
            LockedPanel(onSubscribe: onSubscribe)
        } else {
            LimitPanel(state: state, stale: stale, sign: sign, note: note)
        }
    }

    private var topBar: some View {
        let version = data.installed.compactMap(\.version).max()
        return HStack {
            Color.clear.frame(width: 44, height: 44)
            Text(version.map { "データ \(versionLabel($0))" } ?? "データ未取得")
                .font(.system(size: 12))
                .foregroundStyle(Palette.muted)
                .frame(maxWidth: .infinity)
            Button(action: onSettings) {
                Image(systemName: "gearshape.fill")
                    .font(.system(size: 18))
                    .foregroundStyle(Palette.text)
                    .frame(width: 44, height: 44)
                    .background(Palette.card, in: Shapes.button)
            }
            .accessibilityLabel("設定を開く")
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 8)
    }
}

/// In place of the sign when there is no access; opening the plans is up to the driver.
private struct LockedPanel: View {
    var onSubscribe: () -> Void

    var body: some View {
        VStack(spacing: 14) {
            Text("最高速度の表示は有料プランの機能です")
                .font(.system(size: 18, weight: .bold)).foregroundStyle(Palette.text)
            Text("無料期間が終わりました。現在の速度はこのまま表示されます。")
                .font(.system(size: 14)).lineSpacing(6).foregroundStyle(Palette.muted)
            FlatButton(text: "有料プランを見る", action: onSubscribe)
        }
        .multilineTextAlignment(.center)
        .padding(.horizontal, 32)
    }
}

private struct LimitPanel: View {
    let state: DriveState
    let stale: Bool
    let sign: CGFloat
    let note: String?

    var body: some View {
        let road = stale ? nil : state.road
        VStack(spacing: 10) {
            Text(road.map(roadLabel) ?? " ")
                .font(.system(size: 22, weight: .bold))
                .foregroundStyle(Palette.text)
                .lineLimit(1)
                .minimumScaleFactor(0.7)
                .padding(.horizontal, 16)
            SpeedSign(speed: road.map { Int($0.speedKmh) }, faded: road?.confidence == .low, size: sign)
            ConfidencePill(road: road)
            if let note {
                Text(note)
                    .font(.system(size: 13))
                    .foregroundStyle(Palette.waiting)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, 16)
            }
        }
    }
}

/// Name, else the route number, else nothing to show.
private func roadLabel(_ road: RoadSpeed) -> String {
    if !road.roadName.trimmingCharacters(in: .whitespaces).isEmpty { return road.roadName }
    if !road.roadRef.trimmingCharacters(in: .whitespaces).isEmpty, road.highway.hasPrefix("trunk") {
        let first = road.roadRef.split(separator: ";", omittingEmptySubsequences: false).first ?? ""
        return "国道\(first)号"
    }
    return "道路名なし"
}

/// The regulatory sign: white disc, red ring (faded when the confidence is
/// low), blue figures. No road: a grey ring and a dash.
private struct SpeedSign: View {
    let speed: Int?
    let faded: Bool
    let size: CGFloat

    var body: some View {
        let ring = size * 20 / 220
        let figure = size * ((speed ?? 0) >= 100 ? 0.40 : 0.47)
        ZStack {
            if speed != nil { Circle().fill(.white) }
            Circle().strokeBorder(speed == nil ? Palette.border : (faded ? signRedFaded : signRed), lineWidth: ring)
            Text(speed.map(String.init) ?? "—")
                .font(.system(size: figure, weight: .bold))
                .tracking(-2)
                .foregroundStyle(speed != nil ? signBlue : Palette.faint)
        }
        .frame(width: size, height: size)
        .accessibilityElement()
        .accessibilityLabel(speed.map { "推定最高速度 \($0) キロ" } ?? "最高速度を判定できません")
    }
}

private struct ConfidencePill: View {
    let road: RoadSpeed?

    var body: some View {
        let (label, bars, source): (String, Int, String) =
            switch road?.confidence {
            case .high: ("高", 3, sourceText(road!))
            case .mid: ("中", 2, sourceText(road!))
            case .low: ("低", 1, "中央線の証拠なし（安全側で30）")
            case nil: ("—", 0, "道路を特定できません")
            }
        HStack(spacing: 10) {
            HStack(spacing: 3) {
                ForEach(0..<3, id: \.self) { i in
                    RoundedRectangle(cornerRadius: 3)
                        .fill(i < bars ? Palette.text : Palette.border)
                        .frame(width: 16, height: 6)
                }
            }
            Text("確度 \(label)")
                .font(.system(size: 14, weight: .medium))
                .foregroundStyle(Palette.text)
            Text(source)
                .font(.system(size: 13))
                .foregroundStyle(Palette.muted)
                .lineLimit(1)
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 8)
        .background(Palette.card, in: Capsule())
        .padding(.horizontal, 12)
        .accessibilityElement(children: .combine)
    }
}

/// Why this speed, in the words of the design (stage numbers from limes-core decide.rs).
private func sourceText(_ road: RoadSpeed) -> String {
    switch road.stage {
    case 1: "規制速度（JARTIC）"
    case 2: "高速自動車国道"
    case 3: "自動車専用道路"
    case 4: "中央分離帯あり"
    case 5: road.confidence == .high ? "中央線・車線（JARTIC）" : "中央線・車線から推定（写真・OSM）"
    case 7: "区画線なし（OSM）"
    default: road.reason
    }
}

private struct SpeedPanel: View {
    let state: DriveState
    let stale: Bool
    let figure: CGFloat

    var body: some View {
        let (text, color): (String, Color) =
            if stale { ("GPS 受信待ち", Palette.muted) }
            else if state.gps == .good { ("GPS 良好", Palette.ok) }
            else if state.gps == .fair { ("GPS 精度低下", Palette.waiting) }
            else { ("GPS 精度不足", Palette.waiting) }
        VStack(spacing: 4) {
            Text("現在の速度")
                .font(.system(size: 14))
                .foregroundStyle(Palette.muted)
            HStack(alignment: .lastTextBaseline, spacing: 8) {
                Text(stale ? "—" : String(state.speedKmh ?? 0))
                    .font(.system(size: figure, weight: .bold))
                    .monospacedDigit()
                    .tracking(-4)
                    .foregroundStyle(Palette.text)
                    .lineLimit(1)
                    .minimumScaleFactor(0.5)
                Text("km/h")
                    .font(.system(size: 24, weight: .semibold))
                    .foregroundStyle(Palette.muted)
            }
            .accessibilityElement(children: .combine)
            HStack(spacing: 6) {
                Circle().fill(color).frame(width: 8, height: 8)
                Text(text)
                    .font(.system(size: 13))
                    .foregroundStyle(Palette.muted)
            }
        }
        .padding(.horizontal, 16)
    }
}
