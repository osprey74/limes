import SwiftUI

/// The band a folding phone keeps at one side of the screen, outside the safe
/// area, so a screen laid out in the safe area sits off the middle of the
/// display (iPhone Duo: the outer display, and the inner display on its side).
/// Only one end of the band is taken; the rest is free:
///
/// - upright, and on the inner display: the camera, the clock and the battery,
///   at the top;
/// - the outer display on its side: the camera alone, in a corner. No clock is
///   shown there. The corner is the lower one when the band is at the right,
///   the upper one when it is at the left.
struct SideBand: Equatable {
    let edge: HorizontalEdge
    let width: CGFloat

    /// A narrow screen (the outer display): the rows of a page reach the band,
    /// so what is at the taken end of it has to make room.
    let narrow: Bool

    /// The outer display on its side.
    let onSide: Bool

    /// How far down the band the camera and the clock reach, with a margin
    /// (measured on the outer display of iPhone Duo: the battery ring ends at
    /// 151 pt, at 162 pt while the location arrow is shown above the clock).
    static let clockHeight: CGFloat = 172

    /// How far from its corner the camera reaches on the outer display on its
    /// side (about 71 pt), with a margin.
    static let cameraHeight: CGFloat = 80

    /// How much of the top of the band is taken.
    var top: CGFloat {
        if !onSide { Self.clockHeight } else if edge == .leading { Self.cameraHeight } else { 0 }
    }

    /// How much of the bottom of the band is taken.
    var bottom: CGFloat { onSide && edge == .trailing ? Self.cameraHeight : 0 }
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
/// clear of the band on their own. On a narrow one (the outer display) each
/// screen makes room at the taken end of the band (`PageHeader`, `Page`, the
/// driving screen).
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
        let onSide = narrow && geo.size.width + width > geo.size.height
        return SideBand(edge: edge, width: width, narrow: narrow, onSide: onSide)
    }
}
