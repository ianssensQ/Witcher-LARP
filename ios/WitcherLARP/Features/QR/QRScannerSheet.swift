import SwiftUI

struct QRScannerSheet: View {
    @EnvironmentObject private var model: AppModel
    @Environment(\.dismiss) private var dismiss
    @State private var manualCode = ""
    @State private var useCamera = true
    @State private var isSubmitting = false

    var body: some View {
        NavigationStack {
            VStack(spacing: 16) {
                Toggle("Камера", isOn: $useCamera)
                    .padding(.horizontal)

                if useCamera {
                    QRScannerView { code in
                        submit(code, source: .camera)
                    }
                    .clipShape(RoundedRectangle(cornerRadius: 8))
                    .padding()
                }

                TextField("Ручной QR-ID", text: $manualCode)
                    .textInputAutocapitalization(.characters)
                    .autocorrectionDisabled()
                    .padding()
                    .background(.thinMaterial)
                    .clipShape(RoundedRectangle(cornerRadius: 8))
                    .padding(.horizontal)

                Button("Подтвердить присутствие") {
                    submit(manualCode, source: .manual)
                }
                .buttonStyle(.borderedProminent)
                .disabled(manualCode.isEmpty || isSubmitting)

                if isSubmitting {
                    ProgressView()
                }

                Spacer()
            }
            .navigationTitle("QR")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Закрыть") { dismiss() }
                }
            }
        }
    }

    private func submit(_ code: String, source: QRInputSource) {
        let normalized = code.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !normalized.isEmpty, !isSubmitting else { return }
        isSubmitting = true
        Task {
            await model.lookupQRCode(normalized, source: source)
            await MainActor.run {
                isSubmitting = false
                dismiss()
            }
        }
    }
}
