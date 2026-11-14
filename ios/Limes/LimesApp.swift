import SwiftUI

@main
struct LimesApp: App {
    @State private var data: DataModel
    @State private var drive: DriveModel
    @Environment(\.scenePhase) private var scenePhase

    init() {
        let data = DataModel(settings: Settings())
        data.access = Access(data: data)
        data.start()
        _data = State(initialValue: data)
        _drive = State(initialValue: DriveModel(data: data))
    }

    var body: some Scene {
        WindowGroup {
            RootView(data: data, drive: drive)
                .preferredColorScheme(.dark)
        }
        .onChange(of: scenePhase) { _, phase in
            if phase == .active { data.becameActive() }
        }
    }
}

private enum Screen {
    case drive, settings, download, subscribe
}

/// The app has no map and four screens: driving, settings, download, plans.
private struct RootView: View {
    let data: DataModel
    let drive: DriveModel
    @State private var screen = Screen.drive

    /// Where the plans were opened from, for their back button.
    @State private var plansFrom = Screen.drive

    #if DEBUG
    /// `-debug_screen settings` (or `download`, `subscribe`) as a launch argument opens
    /// that screen first, for screenshots and UI checks.
    init(data: DataModel, drive: DriveModel) {
        self.data = data
        self.drive = drive
        switch UserDefaults.standard.string(forKey: "debug_screen") {
        case "settings": _screen = State(initialValue: .settings)
        case "download": _screen = State(initialValue: .download)
        case "subscribe": _screen = State(initialValue: .subscribe)
        default: break
        }
    }
    #endif

    private func openPlans(from: Screen) {
        plansFrom = from
        screen = .subscribe
    }

    var body: some View {
        Group {
            switch screen {
            case .drive:
                DriveScreen(data: data, drive: drive, onSettings: { screen = .settings }, onSubscribe: { openPlans(from: .drive) })
            case .settings:
                SettingsScreen(
                    data: data, onBack: { screen = .drive }, onDownload: { screen = .download },
                    onSubscribe: { openPlans(from: .settings) }
                )
            case .download:
                DownloadScreen(data: data, onBack: { screen = .settings })
            case .subscribe:
                SubscribeScreen(
                    data: data, access: data.access,
                    backLabel: plansFrom == .settings ? "設定" : "走行画面",
                    onBack: { screen = plansFrom }
                )
            }
        }
        // With the trial over, the plans show once at launch, never while driving.
        .onAppear {
            if screen == .drive, data.access.state == .expired { openPlans(from: .drive) }
        }
    }
}
