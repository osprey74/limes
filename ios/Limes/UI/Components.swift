import SwiftUI

/// Bytes as "36 MB" / "1.2 GB" (decimal units, as the stores show sizes).
func sizeLabel(_ bytes: Int64) -> String {
    let mb = Double(bytes) / 1_000_000
    return mb >= 1000 ? String(format: "%.1f GB", mb / 1000) : String(format: "%.0f MB", mb)
}

/// The "‹ 設定" style back button at the top of a screen.
struct BackButton: View {
    let label: String
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 4) {
                Image(systemName: "chevron.left").font(.system(size: 15, weight: .semibold))
                Text(label).font(.system(size: 15, weight: .medium))
            }
            .foregroundStyle(Palette.text)
            .padding(.leading, 10)
            .padding(.trailing, 14)
            .frame(height: 44)
            .background(Palette.card, in: Shapes.button)
        }
    }
}

/// A titled group of rows on a card.
struct CardSection<Trailing: View, Content: View>: View {
    let title: String
    @ViewBuilder var trailing: Trailing
    @ViewBuilder var content: Content

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(alignment: .bottom) {
                Text(title)
                    .font(.system(size: 13, weight: .medium))
                    .foregroundStyle(Palette.muted)
                    .frame(maxWidth: .infinity, alignment: .leading)
                trailing
            }
            .padding(.horizontal, 4)
            VStack(alignment: .leading, spacing: 0) { content }
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(Palette.card)
                .clipShape(Shapes.card)
        }
    }
}

extension CardSection where Trailing == EmptyView {
    init(_ title: String, @ViewBuilder content: () -> Content) {
        self.init(title: title, trailing: { EmptyView() }, content: content)
    }
}

/// A hairline between rows.
struct RowLine: View {
    var color = Palette.line

    var body: some View { color.frame(height: 1) }
}

/// A row on a card, with a divider above unless it is the first.
struct CardRow<Content: View>: View {
    var first = false
    var minHeight: CGFloat = 56
    var action: (() -> Void)?
    @ViewBuilder var content: Content

    var body: some View {
        VStack(spacing: 0) {
            if !first { RowLine() }
            let row = HStack(spacing: 12) { content }
                .padding(.horizontal, 16)
                .padding(.vertical, 10)
                .frame(maxWidth: .infinity, minHeight: minHeight, alignment: .leading)
                .contentShape(Rectangle())
            if let action {
                Button(action: action) { row }.buttonStyle(.plain)
            } else {
                row
            }
        }
    }
}

/// Label (and an optional note) with a switch.
struct ToggleRow: View {
    let label: String
    var note: String?
    @Binding var isOn: Bool
    var first = false

    var body: some View {
        CardRow(first: first) {
            Toggle(isOn: $isOn) {
                VStack(alignment: .leading, spacing: 2) {
                    Text(label).font(.system(size: 15)).foregroundStyle(Palette.text)
                    if let note {
                        Text(note).font(.system(size: 12)).lineSpacing(3).foregroundStyle(Palette.muted)
                    }
                }
            }
            .tint(Palette.accent)
        }
    }
}

/// A status with a dot, e.g. 最新 / 更新待ち.
struct StatusLabel: View {
    let text: String
    let color: Color

    var body: some View {
        HStack(spacing: 6) {
            Circle().fill(color).frame(width: 8, height: 8)
            Text(text).font(.system(size: 12)).foregroundStyle(color).lineLimit(1)
        }
    }
}

/// Outlined or filled text button of the design.
struct FlatButton: View {
    let text: String
    var filled: Color?
    var textColor: Color?
    var wide = false
    var height: CGFloat = 44
    var enabled = true
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            Text(text)
                .font(.system(size: 15, weight: filled != nil ? .bold : .medium))
                .foregroundStyle(enabled ? (textColor ?? (filled != nil ? Palette.ground : Palette.text)) : Palette.faint)
                .padding(.horizontal, 14)
                .frame(maxWidth: wide ? .infinity : nil, minHeight: height)
                .background {
                    if let filled {
                        Shapes.button.fill(enabled ? filled : Palette.line)
                    } else {
                        Shapes.button.strokeBorder(Palette.border, lineWidth: 1)
                    }
                }
                .contentShape(Shapes.button)
        }
        .buttonStyle(.plain)
        .disabled(!enabled)
    }
}

/// The down arrow of a row that opens, turned when open.
struct Chevron: View {
    let open: Bool

    var body: some View {
        Image(systemName: "chevron.down")
            .font(.system(size: 13, weight: .semibold))
            .foregroundStyle(Palette.muted)
            .rotationEffect(.degrees(open ? 180 : 0))
            .animation(.easeInOut(duration: 0.2), value: open)
            .frame(width: 20, height: 20)
    }
}

/// A scrolling settings-style page on the ground color.
struct Page<Content: View>: View {
    var spacing: CGFloat = 24
    @ViewBuilder var content: Content

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: spacing) { content }
                .padding(.horizontal, 16)
                .padding(.top, 16)
                .padding(.bottom, 40)
                .frame(maxWidth: 640)
                .frame(maxWidth: .infinity)
        }
        .background(Palette.ground.ignoresSafeArea())
    }
}
