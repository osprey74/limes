import BackgroundTasks
import Foundation

/// The daily update while the app is not in use. iOS decides when (and
/// whether) it runs: typically when the phone is idle, often while charging.
/// A processing task rather than an app refresh, because a refresh gets about
/// half a minute, too short for the databases of several prefectures.
@MainActor
enum BackgroundUpdate {
    /// Also in Info.plist (BGTaskSchedulerPermittedIdentifiers).
    static let id = "com.osprey74.limes.update"

    /// Once, before the app has finished launching.
    static func register(_ data: DataModel) {
        BGTaskScheduler.shared.register(forTaskWithIdentifier: id, using: .main) { task in
            Task { @MainActor in
                let finished = await data.updateInBackground()
                schedule(data)
                task.setTaskCompleted(success: finished)
            }
            // Out of time: stop; what was installed so far stays.
            task.expirationHandler = {
                Task { @MainActor in data.stop() }
            }
        }
    }

    /// On leaving the front: ask for a run a day after the last check, or for
    /// none when there is nothing to update (auto update off, no prefecture
    /// kept, or the trial over).
    static func schedule(_ data: DataModel) {
        let settings = data.settings
        guard settings.autoUpdate, !settings.selected.isEmpty, data.access.state.entitled else {
            BGTaskScheduler.shared.cancel(taskRequestWithIdentifier: id)
            return
        }
        let request = BGProcessingTaskRequest(identifier: id)
        request.requiresNetworkConnectivity = true
        let now = Date()
        request.earliestBeginDate = max(now, (settings.lastChecked ?? now).addingTimeInterval(DataModel.checkEvery))
        // Refused where background tasks are unavailable (the simulator,
        // Background App Refresh turned off): the checks in the front remain.
        try? BGTaskScheduler.shared.submit(request)
    }
}
