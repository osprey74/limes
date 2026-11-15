import SwiftUI

/// Shown at every launch: name, icon and a word on safe driving. A tap skips
/// it. The system's own launch screen before it is the gauge on the ground
/// color only (no text, as the HIG asks), so the gauge here sits at the same
/// place, the middle of the screen, and the rest appears around it.
struct LaunchScreen: View {
    var onDone: () -> Void

    @State private var progress: CGFloat = 0
    @Environment(\.verticalSizeClass) private var height

    private static let showFor: TimeInterval = 1.5

    var body: some View {
        // A phone on its side: little room under the gauge.
        let low = height == .compact
        ZStack {
            Palette.ground.ignoresSafeArea()

            // The image is the 108 grid of the icon; the gauge fills its inner 72 (128 pt here).
            Image("Gauge").resizable().frame(width: 192, height: 192)
                .overlay(alignment: .bottom) {
                    VStack(spacing: 0) {
                        Text("Limes").font(.system(size: 44, weight: .bold)).tracking(1.7).foregroundStyle(Palette.text)
                        Text("リメス").font(.system(size: 13)).tracking(2.6).foregroundStyle(Palette.muted)
                    }
                    .fixedSize()
                    .alignmentGuide(.bottom) { $0[.top] + (low ? 40 : 0) }
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .ignoresSafeArea()

            VStack(spacing: low ? 12 : 28) {
                Text(low ? "道路状況や実際の交通規制にあわせ、安全運転を心がけましょう" : "道路状況や実際の交通規制にあわせ、\n安全運転を心がけましょう")
                    .font(.system(size: 17, weight: .medium)).lineSpacing(9).multilineTextAlignment(.center)
                    .foregroundStyle(Palette.text)
                    .padding(.horizontal, 32)
                Capsule().fill(Palette.line)
                    .frame(width: 120, height: 3)
                    .overlay(alignment: .leading) {
                        Capsule().fill(Palette.muted).frame(width: 120 * progress)
                    }
            }
            .padding(.bottom, low ? 8 : 56)
            .frame(maxHeight: .infinity, alignment: .bottom)
        }
        .contentShape(Rectangle())
        .onTapGesture(perform: onDone)
        .accessibilityAddTraits(.isButton)
        .task {
            withAnimation(.linear(duration: Self.showFor)) { progress = 1 }
            try? await Task.sleep(for: .seconds(Self.showFor))
            if !Task.isCancelled { onDone() }
        }
    }
}
