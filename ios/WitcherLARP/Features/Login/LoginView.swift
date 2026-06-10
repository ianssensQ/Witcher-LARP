import SwiftUI

struct LoginView: View {
    @EnvironmentObject private var model: AppModel
    @State private var playerCode = ""
    @State private var serverURLText = ""
    @State private var showDiagnostics = false

    var body: some View {
        VStack(alignment: .leading, spacing: 20) {
            Spacer()

            Text("Вход в игру")
                .font(.largeTitle.bold())
                .foregroundStyle(.white)

            TextField("Код персонажа", text: $playerCode)
                .textInputAutocapitalization(.characters)
                .autocorrectionDisabled()
                .padding()
                .background(.thinMaterial)
                .clipShape(RoundedRectangle(cornerRadius: 8))

            Button {
                Task { await model.login(playerCode: playerCode.trimmingCharacters(in: .whitespacesAndNewlines)) }
            } label: {
                Text("Войти")
                    .frame(maxWidth: .infinity)
            }
            .buttonStyle(.borderedProminent)
            .disabled(playerCode.isEmpty)

            Button("Диагностика сети") {
                serverURLText = model.serverURL.absoluteString
                showDiagnostics.toggle()
            }
            .buttonStyle(.borderless)

            if let error = model.errorMessage {
                Text(error)
                    .font(.footnote)
                    .foregroundStyle(.red)
            }

            Spacer()
        }
        .padding(24)
        .sheet(isPresented: $showDiagnostics) {
            NavigationStack {
                Form {
                    TextField("Server URL", text: $serverURLText)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                    Button("Save") {
                        if let url = URL(string: serverURLText) {
                            model.updateServerURL(url)
                        }
                        showDiagnostics = false
                    }
                }
                .navigationTitle("Local Server")
            }
        }
    }
}
