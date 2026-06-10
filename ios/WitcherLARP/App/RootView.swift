import SwiftUI

struct RootView: View {
    @EnvironmentObject private var model: AppModel

    var body: some View {
        Group {
            if model.snapshot == nil {
                LoginView()
            } else {
                HomeView()
            }
        }
        .background(Color(red: 0.07, green: 0.07, blue: 0.06))
    }
}
