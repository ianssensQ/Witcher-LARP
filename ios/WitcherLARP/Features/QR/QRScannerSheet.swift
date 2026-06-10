import SwiftUI

struct QRScannerSheet: View {
    @EnvironmentObject private var model: AppModel
    @Environment(\.dismiss) private var dismiss
    @State private var manualCode = ""
    @State private var useCamera = true

    var body: some View {
        NavigationStack {
            VStack(spacing: 16) {
                Toggle("Камера", isOn: $useCamera)
                    .padding(.horizontal)

                if useCamera {
                    QRScannerView { code in
                        model.appendQRAttempt(qrId: code, source: .camera)
                        dismiss()
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
                    model.appendQRAttempt(qrId: manualCode, source: .manual)
                    dismiss()
                }
                .buttonStyle(.borderedProminent)
                .disabled(manualCode.isEmpty)

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
}
