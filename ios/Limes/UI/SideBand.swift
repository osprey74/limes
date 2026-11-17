import SwiftUI

/// The band a folding phone keeps at one side of the screen for the clock and
/// the battery (iPhone Duo: the inner display on its side). It is outside the
/// safe area, so a screen laid out in the safe area sits off the middle of the
/// display. Only the top of the band is taken; the rest is free.
struct SideBand: Equatable {
    let edge: HorizontalEdge
    let width: CGFloat

    /// A narrow screen (the outer display, upright): the rows of a page reach
    /// the band, so what is at the top has to make room for the clock.
    let narrow: Bool

    /// How far down the band the camera and the clock reach, with a margin
    /// (measured on the outer display of iPhone Duo: the battery ring ends at
    /// 151 pt, at 162 pt while the location arrow is shown above the clock).
    static let clockHeight: CGFloat = 172
}

extension EnvironmentValues {
    /// The band the screen is drawn across, nil when there is none (or it is left alone).
    @Entry var sideBand: SideBand?
}

/// Lays its content out across the side band, so that it is centered on the
/// display. What would reach the top of the band, where the clock is, has to
/// keep clear of it (`sideBand` in the environment gives its width).
///
/// On a wide screen the pages (640 pt at most) and the driving screen stay
/// clear of the band on their own. On a narrow one (the outer display) the
/// top of each screen makes room for the clock (`PageHeader`, the driving
/// screen). A narrow screen on its side keeps the safe area: the camera and
/// the clock are elsewhere on the band there, and it has not been laid out.
struct AcrossSideBand<Content: View>: View {
    @ViewBuilder var content: Content

    var body: some View {
        GeometryReader { geo in
            let band = Self.band(geo)
            content
                .environment(\.sideBand, band)
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .ignoresSafeArea(.container, edges: band.map { $0.edge == .trailing ? .trailing : .leading } ?? [])
        }
    }

    /// One side kept clear and the other not: a phone on its side keeps both
    /// (the camera housing and its mirror image), which is not a band.
    private static func band(_ geo: GeometryProxy) -> SideBand? {
        let insets = geo.safeAreaInsets
        let edge: HorizontalEdge? =
            if insets.trailing >= 64, insets.trailing - insets.leading >= 40 {
                .trailing
            } else if insets.leading >= 64, insets.leading - insets.trailing >= 40 {
                .leading
            } else {
                nil
            }
        guard let edge else { return nil }
        let width = edge == .trailing ? insets.trailing : insets.leading
        let narrow = geo.size.width + width < 800
        if narrow, geo.size.width + width > geo.size.height { return nil }
        return SideBand(edge: edge, width: width, narrow: narrow)
    }
}
