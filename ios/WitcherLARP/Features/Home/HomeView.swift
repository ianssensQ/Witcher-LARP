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

                    if let quest = model.activePvEScenario {
                        questCard(quest)
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

    private func questCard(_ quest: PvEScenarioCard) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Label(
                    quest.contentLane == "anti_idle" ? "Быстрая сцена" : "Заказ",
                    systemImage: quest.contentLane == "anti_idle" ? "bolt" : "scroll"
                )
                .font(.caption.bold())
                .foregroundStyle(.secondary)

                Spacer()

                if let minutes = quest.estimatedMinutes {
                    Text("\(minutes) мин.")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }

            Text(quest.displayTitle)
                .font(.headline)

            if !quest.displayBrief.isEmpty {
                Text(quest.displayBrief)
                    .font(.subheadline)
            }

            if let trialPrompt = quest.trialPrompt {
                Text(trialPrompt)
                    .font(.callout)
            }

            if let choicePrompt = quest.choicePrompt {
                Text(choicePrompt)
                    .font(.callout)
            }

            if !quest.displayCheck.isEmpty {
                Label(quest.displayCheck, systemImage: "dice")
                    .font(.footnote)
            }

            if let victoryRule = quest.victoryRule {
                Label(victoryRule, systemImage: "checkmark.seal")
                    .font(.footnote)
            }

            if let reward = quest.rewardSummary {
                Label(reward, systemImage: "seal")
                    .font(.footnote)
            }

            if let rewardPolicy = quest.branchRewardPolicy {
                Text(rewardPolicy)
                    .font(.footnote)
                    .foregroundStyle(.secondary)
            }

            if let consequence = quest.worldEffect {
                Text(consequence)
                    .font(.footnote)
                    .foregroundStyle(.secondary)
            }
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
