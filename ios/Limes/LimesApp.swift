import SwiftUI

@main
struct LimesApp: App {
    @State private var core = Core()

    var body: some Scene {
        WindowGroup {
            ContentView(core: core)
                .preferredColorScheme(.dark)
        }
    }
}
