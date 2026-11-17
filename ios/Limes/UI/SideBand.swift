import SwiftUI

/// The band a folding phone keeps at one side of the screen for the clock and
/// the battery (iPhone Duo: the inner display on its side). It is outside the
/// safe area, so a screen laid out in the safe area sits off the middle of the
/// display. Only the top of the band is taken; the rest is free.
struct SideBand: Equatable {
    let edge: HorizontalEdge
    let width: CGFloat
}

extension EnvironmentValues {
    /// The band the screen is drawn across, nil when there is none (or it is left alone).
    @Entry var sideBand: SideBand?
}

/// Lays its content out across the side band, so that it is centered on the
/// display. What would reach the top of the band, where the clock is, has to
/// keep clear of it (`sideBand` in the environment gives its width).
///
/// Only on a wide screen: there the pages (640 pt at most) and the driving
/// screen stay clear of the band on their own. On a narrow one (the outer
/// display) the rows would run under the clock, so the safe area is kept.
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
        let band: SideBand? =
            if insets.trailing >= 64, insets.trailing - insets.leading >= 40 {
                SideBand(edge: .trailing, width: insets.trailing)
            } else if insets.leading >= 64, insets.leading - insets.trailing >= 40 {
                SideBand(edge: .leading, width: insets.leading)
            } else {
                nil
            }
        guard let band, geo.size.width + band.width >= 800 else { return nil }
        return band
    }
}
