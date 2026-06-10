import SwiftUI

struct HomeView: View {
    @EnvironmentObject private var model: AppModel
    @State private var showQR = false

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    if let snapshot = model.snapshot {
                        characterCard(snapshot)
                    }

                    Button {
                        showQR = true
                    } label: {
                        Label("QR / ручной код", systemImage: "qrcode.viewfinder")
                            .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.borderedProminent)

                    Button {
                        Task { await model.syncPendingEvents() }
                    } label: {
                        Label("Синхронизировать", systemImage: "arrow.triangle.2.circlepath")
                            .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.bordered)

                    queueCard
                }
                .padding()
            }
            .navigationTitle("Полевой журнал")
            .sheet(isPresented: $showQR) {
                QRScannerSheet()
            }
        }
    }

    private func characterCard(_ snapshot: PlayerSnapshot) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(snapshot.displayName)
                .font(.title2.bold())
            Text(snapshot.roleType)
                .font(.subheadline)
                .foregroundStyle(.secondary)
            HStack {
                Text("Ур. \(snapshot.level)")
                Text("\(snapshot.xp) XP")
                Text("\(snapshot.gold)g")
                Text(snapshot.reputationLabel)
            }
            .font(.footnote)
        }
        .padding()
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(.thinMaterial)
        .clipShape(RoundedRectangle(cornerRadius: 8))
    }

    private var queueCard: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Очередь событий")
                .font(.headline)
            Text("\(model.pendingEvents.count) ожидает sync")
            Text(model.syncState.rawValue)
                .font(.footnote)
                .foregroundStyle(.secondary)
        }
        .padding()
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(.thinMaterial)
        .clipShape(RoundedRectangle(cornerRadius: 8))
    }
}
