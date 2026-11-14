import SwiftUI

@main
struct LimesApp: App {
    @State private var data: DataModel
    @State private var drive: DriveModel
    @Environment(\.scenePhase) private var scenePhase

    init() {
        let data = DataModel(settings: Settings())
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
    case drive, settings, download
}

/// The app has no map and three screens: driving, settings, download.
private struct RootView: View {
    let data: DataModel
    let drive: DriveModel
    @State private var screen = Screen.drive

    #if DEBUG
    /// `-debug_screen settings` (or `download`) as a launch argument opens
    /// that screen first, for screenshots and UI checks.
    init(data: DataModel, drive: DriveModel) {
        self.data = data
        self.drive = drive
        switch UserDefaults.standard.string(forKey: "debug_screen") {
        case "settings": _screen = State(initialValue: .settings)
        case "download": _screen = State(initialValue: .download)
        default: break
        }
    }
    #endif

    var body: some View {
        switch screen {
        case .drive:
            DriveScreen(data: data, drive: drive, onSettings: { screen = .settings })
        case .settings:
            SettingsScreen(data: data, onBack: { screen = .drive }, onDownload: { screen = .download })
        case .download:
            DownloadScreen(data: data, onBack: { screen = .settings })
        }
    }
}
