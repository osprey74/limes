import SwiftUI

@main
struct LimesApp: App {
    @State private var data: DataModel
    @State private var drive: DriveModel
    @Environment(\.scenePhase) private var scenePhase

    init() {
        let data = DataModel(settings: Settings())
        data.access = Access(data: data)
        BackgroundUpdate.register(data)
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
            if phase == .background { BackgroundUpdate.schedule(data) }
        }
    }
}

private enum Screen {
    case launch, drive, settings, download, subscribe
}

/// The app has no map and four screens: driving, settings, download, plans,
/// after a word on safe driving at every launch.
private struct RootView: View {
    let data: DataModel
    let drive: DriveModel
    @State private var screen = Screen.launch

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

    /// `-debug_orientation left` (or `right`; `portrait` to turn it back) turns the
    /// screen on its side, which the simulator of a folding phone cannot be told
    /// to do from the command line.
    private func turn() {
        let mask: UIInterfaceOrientationMask? =
            switch UserDefaults.standard.string(forKey: "debug_orientation") {
            case "left": .landscapeLeft
            case "right": .landscapeRight
            case "portrait": .portrait
            default: nil
            }
        guard let mask else { return }
        for case let scene as UIWindowScene in UIApplication.shared.connectedScenes {
            scene.requestGeometryUpdate(.iOS(interfaceOrientations: mask))
        }
    }
    #endif

    private func openPlans(from: Screen) {
        plansFrom = from
        screen = .subscribe
    }

    var body: some View {
        AcrossSideBand {
            switch screen {
            case .launch:
                // With the trial over, the plans show once at launch, never while driving.
                LaunchScreen {
                    guard screen == .launch else { return }
                    if data.access.state == .expired { openPlans(from: .drive) } else { screen = .drive }
                }
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
        #if DEBUG
        .onAppear { turn() }
        #endif
    }
}
