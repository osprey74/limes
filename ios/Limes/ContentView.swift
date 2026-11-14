import SwiftUI

/// Placeholder until the screens are built: shows that the Rust core is
/// linked and answering.
struct ContentView: View {
    let core: Core

    var body: some View {
        VStack(spacing: 12) {
            Text("Limes")
                .font(.system(size: 44, weight: .bold))
            Text("リメス")
                .font(.footnote)
                .foregroundStyle(.secondary)
            Text(coreStatus)
                .font(.callout)
                .multilineTextAlignment(.center)
                .padding(.top, 24)
        }
        .padding()
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color(red: 0x0B / 255, green: 0x0D / 255, blue: 0x10 / 255))
    }

    private var coreStatus: String {
        if let error = core.storeError { return "コアの初期化に失敗しました\n\(error)" }
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = TimeZone(identifier: "Asia/Tokyo")!
        let c = calendar.dateComponents([.year, .month, .day, .hour, .minute], from: Date())
        let t = localTime(
            year: Int32(c.year!), month: UInt8(c.month!), day: UInt8(c.day!),
            hour: UInt8(c.hour!), minute: UInt8(c.minute!)
        )
        let weekday = ["月", "火", "水", "木", "金", "土", "日"][Int(t.weekday)]
        return "コア接続済み\n\(c.month!)月\(c.day!)日（\(weekday)）\(t.holiday ? "祝日" : "祝日でない")\n保持データ \(core.installed.count) 件"
    }
}

#Preview {
    ContentView(core: Core())
}
