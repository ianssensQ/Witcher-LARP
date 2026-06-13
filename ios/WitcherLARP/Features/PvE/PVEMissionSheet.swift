import SwiftUI

struct PVEMissionSheet: View {
    @EnvironmentObject private var model: AppModel
    let onClose: () -> Void

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    if let mission = model.activePVEMission {
                        missionContent(mission)
                    } else if let result = model.lastPvEResult {
                        resultContent(result)
                    } else {
                        emptyContent
                    }
                }
                .padding()
            }
            .navigationTitle(navigationTitle)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button(model.activePVEMission == nil ? "Готово" : "Журнал") {
                        onClose()
                    }
                }
            }
        }
    }
}

private extension PVEMissionSheet {
    var navigationTitle: String {
        model.activePVEMission == nil ? "Итог миссии" : "Миссия"
    }

    func missionContent(_ mission: PvESceneDraft) -> some View {
        VStack(alignment: .leading, spacing: 16) {
            missionHeader(mission)

            Text(mission.missionText)
                .font(.body)
                .fixedSize(horizontal: false, vertical: true)
                .missionCard()

            if let choices = mission.currentChoiceStage {
                choiceStage(choices, mission: mission)
            } else {
                checksStage(mission)
            }
        }
    }

    func missionHeader(_ mission: PvESceneDraft) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(mission.qr.manualCode)
                .font(.caption.bold())
                .foregroundStyle(.orange)
            Text(pveSceneTypeLabel(mission.scenario.sceneType))
                .font(.title2.bold())
            Text("Проверки: \(mission.checkStats.joined(separator: " · "))")
                .font(.footnote)
                .foregroundStyle(.secondary)
        }
        .missionCard()
    }

    func pveSceneTypeLabel(_ sceneType: String) -> String {
        switch sceneType {
        case "monster_hunt":
            return "Охота"
        case "investigation":
            return "Расследование"
        case "moral_choice":
            return "Выбор"
        case "puzzle_check":
            return "Загадка"
        case "sorceress_hook":
            return "Магический след"
        case "order_object":
            return "Объект заказа"
        case "artifact":
            return "Артефакт"
        case "lord_hook":
            return "Интерес лорда"
        default:
            return sceneType
        }
    }

    func choiceStage(_ choices: [PVEMissionChoice], mission: PvESceneDraft) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Выбор \(mission.selectedChoiceIds.count + 1) из \(mission.choiceStages.count)")
                .font(.headline)

            ForEach(choices) { choice in
                Button {
                    model.choosePVEOption(choice.choiceId)
                } label: {
                    Text(choice.title)
                        .font(.body.weight(.semibold))
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 6)
                }
                .buttonStyle(.bordered)
            }
        }
        .missionCard()
    }

    func checksStage(_ mission: PvESceneDraft) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Испытания")
                .font(.headline)

            if !mission.rollLog.isEmpty {
                Text(mission.rollSummary)
                    .font(.caption.monospacedDigit())
                    .foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            }

            if let stat = mission.nextCheckStat {
                Button {
                    model.rollNextPVECheck()
                } label: {
                    Label("Проверка: \(stat)", systemImage: "die.face.5")
                        .font(.body.weight(.semibold))
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 6)
                }
                .buttonStyle(.borderedProminent)
            }
        }
        .missionCard()
    }

    func resultContent(_ result: PvESceneDraft) -> some View {
        VStack(alignment: .leading, spacing: 16) {
            VStack(alignment: .leading, spacing: 8) {
                Text(result.resultLabel)
                    .font(.largeTitle.bold())
                Text(result.resultText)
                    .font(.body)
                    .fixedSize(horizontal: false, vertical: true)
            }
            .missionCard()

            VStack(alignment: .leading, spacing: 10) {
                Text("Броски")
                    .font(.headline)
                Text(result.rollSummary)
                    .font(.caption.monospacedDigit())
                    .foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            }
            .missionCard()

            VStack(alignment: .leading, spacing: 8) {
                Text("Награда")
                    .font(.headline)
                Text(result.rewardLine)
                    .font(.body)
            }
            .missionCard()

            Button {
                onClose()
            } label: {
                Text("Вернуться в журнал")
                    .frame(maxWidth: .infinity)
            }
            .buttonStyle(.borderedProminent)
        }
    }

    var emptyContent: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Миссия не открыта")
                .font(.headline)
            Text("Вернитесь в журнал и отсканируйте QR.")
                .font(.subheadline)
                .foregroundStyle(.secondary)
        }
        .missionCard()
    }
}

private extension View {
    func missionCard() -> some View {
        padding()
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(.thinMaterial)
            .clipShape(RoundedRectangle(cornerRadius: 8))
    }
}
