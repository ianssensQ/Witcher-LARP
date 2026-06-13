import SwiftUI

struct LoginView: View {
    @EnvironmentObject private var model: AppModel
    @State private var playerCode = ""
    @State private var serverURLText = ""
    @State private var showDiagnostics = false

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            Spacer()

            Text("Ведьмачий дневник")
                .font(.largeTitle.bold())
                .foregroundStyle(.white)

            Text("Войди по коду персонажа, когда iPhone в локальной сети игры.")
                .font(.subheadline)
                .foregroundStyle(.secondary)

            Label(model.serverConnectionLabel, systemImage: model.serverIsReachable ? "checkmark.circle.fill" : "wifi.exclamationmark")
                .font(.subheadline.bold())
                .foregroundStyle(model.serverIsReachable ? .green : .orange)
                .padding()
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(.thinMaterial)
                .clipShape(RoundedRectangle(cornerRadius: 8))

            TextField("Код персонажа", text: $playerCode)
                .textInputAutocapitalization(.characters)
                .autocorrectionDisabled()
                .padding()
                .background(.thinMaterial)
                .clipShape(RoundedRectangle(cornerRadius: 8))

            Button {
                Task {
                    await model.login(playerCode: playerCode.trimmingCharacters(in: .whitespacesAndNewlines))
                }
            } label: {
                Text("Войти")
                    .frame(maxWidth: .infinity)
            }
            .buttonStyle(.borderedProminent)
            .disabled(playerCode.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)

            HStack {
                Button {
                    Task { await model.checkServerHealth() }
                } label: {
                    Label("Проверить связь", systemImage: "arrow.clockwise")
                }
                .buttonStyle(.bordered)

                Spacer()

                Button("Настройки") {
                    serverURLText = model.serverURL.absoluteString
                    showDiagnostics.toggle()
                }
                .buttonStyle(.borderless)
            }

            if let error = model.errorMessage {
                Label(error, systemImage: "exclamationmark.triangle.fill")
                    .font(.footnote)
                    .foregroundStyle(.red)
                    .padding()
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(.red.opacity(0.08))
                    .clipShape(RoundedRectangle(cornerRadius: 8))
            } else if let info = model.infoMessage {
                Label(info, systemImage: "info.circle")
                    .font(.footnote)
                    .foregroundStyle(.secondary)
            }

            Spacer()
        }
        .padding(24)
        .onAppear {
            playerCode = model.playerCode
            if !model.screenshotMode {
                Task { await model.checkServerHealth() }
            }
        }
        .sheet(isPresented: $showDiagnostics) {
            NavigationStack {
                Form {
                    Section("Мастерская настройка") {
                        TextField(AppModel.defaultServerURLString, text: $serverURLText)
                            .textInputAutocapitalization(.never)
                            .autocorrectionDisabled()
                        Button("Сохранить и проверить") {
                            if model.updateServerURL(from: serverURLText) {
                                serverURLText = model.serverURL.absoluteString
                                Task { await model.checkServerHealth() }
                            }
                        }
                    }

                    Section {
                        Button("Сбросить локальную сессию", role: .destructive) {
                            model.resetLocalSession()
                            playerCode = ""
                            showDiagnostics = false
                        }
                    } footer: {
                        Text("Сброс удаляет сохраненный код, данные игры и очередь с этого iPhone. Адрес сервера остается.")
                    }

                    #if DEBUG
                    Section("Debug") {
                        Button("Открыть демо экранов") {
                            model.loadDemoSnapshot()
                            showDiagnostics = false
                        }
                    }
                    #endif
                }
                .navigationTitle("Сервер игры")
            }
        }
    }
}
