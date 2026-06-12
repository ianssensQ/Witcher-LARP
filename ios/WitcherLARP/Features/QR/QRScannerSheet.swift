import Foundation
import SwiftUI

struct QRScannerSheet: View {
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        QRScannerFlowView(showsDismissControls: true) {
            dismiss()
        }
    }
}

struct QRScannerFlowView: View {
    @EnvironmentObject private var model: AppModel
    @State private var manualCode = ""
    @State private var useCamera = true
    @State private var inputSource: QRInputSource = .manual
    @State private var applyingScannedCode = false
    @FocusState private var manualCodeFocused: Bool
    private let showsDismissControls: Bool
    private let onDone: () -> Void

    init(showsDismissControls: Bool = false, onDone: @escaping () -> Void = {}) {
        self.showsDismissControls = showsDismissControls
        self.onDone = onDone
    }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    Toggle("Камера", isOn: $useCamera)

                    if useCamera {
                        QRScannerView { code in
                            handleScannedCode(code)
                        }
                        .frame(minHeight: 320)
                        .clipShape(RoundedRectangle(cornerRadius: 8))
                    }

                    TextField("Короткий код объекта", text: $manualCode)
                        .textInputAutocapitalization(.characters)
                        .autocorrectionDisabled()
                        .keyboardType(.asciiCapable)
                        .submitLabel(.done)
                        .focused($manualCodeFocused)
                        .padding()
                        .background(.thinMaterial)
                        .clipShape(RoundedRectangle(cornerRadius: 8))
                        .onSubmit {
                            submitManualCode()
                        }
                        .onChange(of: manualCode) { _ in
                            guard !applyingScannedCode else { return }
                            inputSource = .manual
                            model.lastQRLookup = nil
                        }

                    Button {
                        submitManualCode()
                    } label: {
                        Label("Применить код", systemImage: "checkmark.circle")
                            .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.borderedProminent)
                    .disabled(normalizedCode.isEmpty)

                    qrFeedback

                    if showsDismissControls {
                        Button("Готово") { onDone() }
                            .buttonStyle(.bordered)
                            .frame(maxWidth: .infinity)
                    }
                }
                .padding()
            }
            .navigationTitle("QR")
            .toolbar {
                if showsDismissControls {
                    ToolbarItem(placement: .cancellationAction) {
                        Button("Закрыть") { onDone() }
                    }
                }
                ToolbarItemGroup(placement: .keyboard) {
                    Spacer()
                    Button {
                        manualCodeFocused = false
                    } label: {
                        Image(systemName: "keyboard.chevron.compact.down")
                    }
                    .accessibilityLabel("Убрать клавиатуру")
                }
            }
        }
    }
}

private extension QRScannerFlowView {
    var normalizedCode: String {
        normalizeQRCode(manualCode)
    }

    var currentResult: PvESceneDraft? {
        guard let result = model.lastPvEResult, !normalizedCode.isEmpty else { return nil }
        return result.qr.qrId.uppercased() == normalizedCode || result.qr.manualCode.uppercased() == normalizedCode
            ? result
            : nil
    }

    @ViewBuilder
    var qrFeedback: some View {
        if let result = currentResult {
            VStack(alignment: .leading, spacing: 6) {
                Text(result.resultLabel)
                    .font(.headline)
                Text(result.result == "success" ? result.scenario.successText : result.scenario.failureText)
                    .font(.subheadline)
                Text("Награда: \(result.rewardLine)")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            .padding()
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(.thinMaterial)
            .clipShape(RoundedRectangle(cornerRadius: 8))
        } else if let error = qrSpecificError {
            Label(error, systemImage: "exclamationmark.triangle.fill")
                .font(.footnote)
                .foregroundStyle(.orange)
        } else if let notice = offlineNotice {
            Label(notice, systemImage: "iphone")
                .font(.footnote)
                .foregroundStyle(.secondary)
        } else if let info = qrInfoMessage {
            Label(info, systemImage: "checkmark.circle.fill")
                .font(.footnote)
                .foregroundStyle(.secondary)
        }
    }

    var qrSpecificError: String? {
        guard let error = model.errorMessage else { return nil }
        let lowercased = error.lowercased()
        let serverFragments = [
            "адрес сервера",
            "база или импорт",
            "fastapi",
            "wi-fi",
            "подключиться к серверу",
            "сервер игры"
        ]
        if serverFragments.contains(where: lowercased.contains) {
            return nil
        }
        return error
    }

    var qrInfoMessage: String? {
        guard let info = model.infoMessage else { return nil }
        let lowercased = info.lowercased()
        let serverFragments = [
            "адрес сервера",
            "игровой дневник",
            "сервер игры"
        ]
        if serverFragments.contains(where: lowercased.contains) {
            return nil
        }
        return info
    }

    var offlineNotice: String? {
        guard model.syncState == .syncError || (model.serverHealthChecked && !model.serverIsReachable) else {
            return nil
        }
        return "Оффлайн-режим: QR работает по данным на телефоне."
    }

    func handleScannedCode(_ rawCode: String) {
        let normalized = normalizeQRCode(rawCode)
        guard !normalized.isEmpty else { return }
        applyingScannedCode = true
        inputSource = .camera
        manualCode = normalized
        manualCodeFocused = false
        model.lastQRLookup = nil
        model.completePVE(code: normalized, source: .camera)
        DispatchQueue.main.async {
            applyingScannedCode = false
        }
    }

    func submitManualCode() {
        let normalized = normalizedCode
        guard !normalized.isEmpty else { return }
        manualCode = normalized
        inputSource = .manual
        manualCodeFocused = false
        model.lastQRLookup = nil
        model.completePVE(code: normalized, source: inputSource)
    }

    func normalizeQRCode(_ raw: String) -> String {
        let trimmed = raw.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return "" }

        if let components = URLComponents(string: trimmed) {
            let queryCode = components.queryItems?
                .first { ["code", "qr", "qr_id", "manual_code"].contains($0.name.lowercased()) }?
                .value
            if let queryCode, !queryCode.isEmpty {
                return normalizeQRCode(queryCode)
            }
        }

        let uppercased = trimmed.uppercased()
        let patterns = [
            #"QR-[A-Z0-9]+(?:-[A-Z0-9]+)*"#,
            #"QR_[A-Z0-9_]+"#
        ]
        for pattern in patterns {
            if let range = uppercased.range(of: pattern, options: .regularExpression) {
                return String(uppercased[range])
            }
        }
        return uppercased
    }
}
