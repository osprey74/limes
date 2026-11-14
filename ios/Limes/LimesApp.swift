import SwiftUI

@main
struct LimesApp: App {
    @State private var core: Core
    @State private var drive: DriveModel

    init() {
        let core = Core()
        _core = State(initialValue: core)
        _drive = State(initialValue: DriveModel(engine: core.engine))
    }

    var body: some Scene {
        WindowGroup {
            // The settings screen is not built yet; its button does nothing.
            DriveScreen(core: core, drive: drive, onSettings: {})
                .preferredColorScheme(.dark)
        }
    }
}
