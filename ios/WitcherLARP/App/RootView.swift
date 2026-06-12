import SwiftUI

struct RootView: View {
    @EnvironmentObject private var model: AppModel

    var body: some View {
        Group {
            if model.hasPlayableSession {
                HomeView()
            } else {
                LoginView()
            }
        }
        .background(Color(red: 0.07, green: 0.07, blue: 0.06))
        .task {
            guard !model.screenshotMode else { return }
            await model.checkServerHealth()
        }
    }
}
