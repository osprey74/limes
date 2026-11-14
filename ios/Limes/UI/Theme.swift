import SwiftUI

extension Color {
    /// 0xRRGGBB.
    init(hex: UInt32) {
        self.init(
            red: Double((hex >> 16) & 0xFF) / 255,
            green: Double((hex >> 8) & 0xFF) / 255,
            blue: Double(hex & 0xFF) / 255
        )
    }
}

/// Colors of the design canvas (dark ground, high-contrast text); the same
/// values as the Android app's `Palette`.
enum Palette {
    static let ground = Color(hex: 0x0B0D10)
    static let card = Color(hex: 0x15181D)
    static let inset = Color(hex: 0x1E2228)
    static let line = Color(hex: 0x23272E)
    static let border = Color(hex: 0x3A414B)
    static let text = Color(hex: 0xF2F4F7)
    static let sub = Color(hex: 0xC3C9D0)
    static let muted = Color(hex: 0x9AA3AE)
    static let faint = Color(hex: 0x6B7480)
    static let accent = Color(hex: 0xC8F169)
    static let ok = Color(hex: 0x34D3B8)
    static let waiting = Color(hex: 0xFFB020)
    static let danger = Color(hex: 0xFF6B6B)
    static let dangerText = Color(hex: 0xFF8A8A)

    /// One color per region, in display order.
    static let regions: [Color] = [
        Color(hex: 0xC8F169), Color(hex: 0x34D3B8), Color(hex: 0x8F7CFF), Color(hex: 0xFFB020),
        Color(hex: 0xF27FB0), Color(hex: 0x6FA8FF), Color(hex: 0xE8E1C4), Color(hex: 0xFF8A5C),
    ]
}

enum Shapes {
    static let card = RoundedRectangle(cornerRadius: 16, style: .continuous)
    static let button = RoundedRectangle(cornerRadius: 12, style: .continuous)
}

/// "2026-09.202611090651" -> "2026年9月版".
func versionLabel(_ version: String?) -> String {
    guard let month = version?.split(separator: ".").first else { return "版不明" }
    let parts = month.split(separator: "-")
    guard parts.count >= 2, let m = Int(parts[1]) else { return "版不明" }
    return "\(parts[0])年\(m)月版"
}
