import Foundation

struct PvESceneDraft: Identifiable, Equatable {
    let qr: QRObject
    let scenario: PVEScenario
    let reward: Reward?
    let player: PlayerProfile
    let source: QRInputSource
    let createdAt: Date
    var selectedChoiceIds: [String]
    var rollLog: [PVERollDraft]

    var id: String { "\(qr.qrId)-\(createdAt.timeIntervalSince1970)" }

    static func start(
        qr: QRObject,
        scenario: PVEScenario,
        reward: Reward?,
        player: PlayerProfile,
        source: QRInputSource
    ) -> PvESceneDraft {
        PvESceneDraft(
            qr: qr,
            scenario: scenario,
            reward: reward,
            player: player,
            source: source,
            createdAt: Date(),
            selectedChoiceIds: [],
            rollLog: []
        )
    }

    var missionText: String {
        if let text = scenario.missionText?.trimmingCharacters(in: .whitespacesAndNewlines), !text.isEmpty {
            return text
        }
        switch scenario.sceneType {
        case "monster_hunt":
            return "Следы у \(qr.manualCode) выводят к опасному логову. Нужно решить, как подойти к цели, а затем выдержать короткую схватку."
        case "investigation":
            return "На месте \(qr.manualCode) обнаружены улики. Их можно разобрать разными способами, но ошибка быстро заведет след в тупик."
        case "moral_choice":
            return "Сцена у \(qr.manualCode) требует решения перед свидетелями. Слова и выдержка важны не меньше оружия."
        case "puzzle_check":
            return "Перед вами закрытая загадка. Механизм реагирует на порядок действий и не прощает поспешности."
        case "sorceress_hook":
            return "В воздухе держится магическое напряжение. Нужно выбрать подход и стабилизировать сцену до всплеска."
        case "order_object":
            return "Объект заказа найден. Осталось получить доказательство и выйти без потери следа."
        case "artifact":
            return "Рядом с \(qr.manualCode) чувствуется редкая сила. Артефакт можно забрать только после проверки."
        default:
            return "Вы активировали сцену \(qr.manualCode). Выберите подход, затем пройдите три проверки."
        }
    }

    var choiceStages: [[PVEMissionChoice]] {
        [
            [
                PVEMissionChoice(choiceId: "approach_cautious", title: "Осмотреться"),
                PVEMissionChoice(choiceId: "approach_rushed", title: "Действовать резко"),
                PVEMissionChoice(choiceId: "approach_direct", title: "Держать темп")
            ],
            methodChoices
        ]
    }

    var currentChoiceStage: [PVEMissionChoice]? {
        guard selectedChoiceIds.count < choiceStages.count else { return nil }
        return choiceStages[selectedChoiceIds.count]
    }

    var isReadyForChecks: Bool {
        selectedChoiceIds.count >= choiceStages.count
    }

    var isComplete: Bool {
        rollLog.count >= checkStats.count
    }

    var checkStats: [String] {
        let primary = canonicalStat(scenario.primaryStat)
        let preferred: [String]
        switch scenario.sceneType {
        case "monster_hunt":
            preferred = [primary, "Ловкость", "Воля"]
        case "investigation", "puzzle_check":
            preferred = [primary, "Ловкость", "Воля"]
        case "moral_choice", "lord_hook":
            preferred = [primary, "Разум", "Воля"]
        case "sorceress_hook":
            preferred = [primary, "Разум", "Харизма"]
        case "order_object", "artifact":
            preferred = [primary, "Разум", "Ловкость"]
        default:
            preferred = [primary, "Сила", "Ловкость"]
        }
        var result: [String] = []
        for stat in preferred + Self.canonicalStats where !result.contains(stat) {
            result.append(stat)
            if result.count == 3 { break }
        }
        return result
    }

    var nextCheckStat: String? {
        guard isReadyForChecks, rollLog.count < checkStats.count else { return nil }
        return checkStats[rollLog.count]
    }

    var successCount: Int {
        rollLog.filter { $0.total(player: player) >= $0.dc }.count
    }

    var result: String {
        guard isComplete else { return "in_progress" }
        return successCount >= 2 ? "success" : "failure"
    }

    var resultLabel: String {
        switch result {
        case "success":
            return "Победа"
        case "failure":
            return "Поражение"
        default:
            return "В процессе"
        }
    }

    var resultText: String {
        result == "success" ? scenario.successText : scenario.failureText
    }

    var rewardStatus: String {
        guard result == "success", let reward else { return "none" }
        return reward.approvalPolicy == "pending_master_approval" ? "pending_master_approval" : "auto"
    }

    var rewardStatusLabel: String {
        switch rewardStatus {
        case "auto":
            return "начислится после sync"
        case "pending_master_approval":
            return "заблокирована до проверки мастера"
        case "none":
            return result == "failure" ? "без награды; QR заблокируется на 30 минут" : "без награды"
        default:
            return rewardStatus
        }
    }

    var rewardLine: String {
        guard let reward, result == "success" else {
            return rewardStatusLabel
        }
        return "\(reward.gold)g · \(reward.xp) XP · \(rewardStatusLabel)"
    }

    var roll: Int {
        rollLog.first?.roll ?? 0
    }

    var statValue: Int {
        guard let stat = rollLog.first?.stat ?? checkStats.first else { return 0 }
        return player.stats[stat] ?? 0
    }

    var total: Int {
        rollLog.first?.total(player: player) ?? 0
    }

    var statLabel: String {
        rollLog.first?.stat ?? checkStats.first ?? scenario.primaryStat
    }

    var rollSummary: String {
        rollLog.map { roll in
            "\(roll.stat): d20 \(roll.roll) + \(roll.statValue(player: player)) + \(roll.modifierTotal) = \(roll.total(player: player))"
        }
        .joined(separator: "\n")
    }

    var lastRollSummary: String {
        guard let roll = rollLog.last else { return "" }
        return "\(roll.stat): d20 \(roll.roll) + \(roll.statValue(player: player)) + \(roll.modifierTotal) = \(roll.total(player: player))"
    }

    var eventPayload: [String: JSONValue] {
        let choiceValues = selectedChoiceIds.map { JSONValue.string($0) }
        return [
            "player_id": .string(player.playerId),
            "scenario_id": .string(scenario.scenarioId),
            "qr_id": .string(qr.qrId),
            "manual_code": .string(qr.manualCode),
            "act_id": .string(qr.actId),
            "unlock_source": .string("act1_default"),
            "pve_flow": .string("mission_v2"),
            "check_policy": .string("three_stat_checks"),
            "selected_choices": .array(choiceValues),
            "roll_source": .string("app_generated"),
            "roll_log": .array(rollLog.map { .object($0.eventPayload(draft: self)) }),
            "success_count": .int(successCount),
            "outcome": .string(result),
            "result": .string(result),
            "reward_id": .string(reward?.rewardId ?? scenario.rewardId),
            "reward_approval_policy": .string(reward?.approvalPolicy ?? "auto"),
            "reward_status": .string(rewardStatus),
            "qr_mode": .string(qr.qrMode),
            "physical_presence_confirmed": .bool(true),
            "source": .string(source.apiValue)
        ]
    }

    func selecting(choiceId: String) -> PvESceneDraft? {
        guard let stage = currentChoiceStage, stage.contains(where: { $0.choiceId == choiceId }) else {
            return nil
        }
        var updated = self
        updated.selectedChoiceIds.append(choiceId)
        return updated
    }

    func rollingNextCheck() -> PvESceneDraft? {
        guard let stat = nextCheckStat else { return nil }
        var updated = self
        updated.rollLog.append(PVERollDraft(
            checkIndex: rollLog.count + 1,
            stat: stat,
            roll: Int.random(in: 1...20),
            dc: scenario.dc,
            modifiers: choiceModifiers(for: stat),
            checkId: "ios-check-\(UUID().uuidString)",
            rollId: "ios-roll-\(UUID().uuidString)",
            createdAt: Date()
        ))
        return updated
    }

    func choiceModifiers(for stat: String) -> [PVEMissionModifier] {
        selectedChoiceIds.compactMap { choiceId in
            guard let value = Self.choiceEffects[choiceId]?[stat], value != 0 else { return nil }
            return PVEMissionModifier(source: "system", label: "choice:\(choiceId)", value: value)
        }
    }

    private var methodChoices: [PVEMissionChoice] {
        switch scenario.sceneType {
        case "monster_hunt":
            return [
                PVEMissionChoice(choiceId: "method_silver", title: "Серебро"),
                PVEMissionChoice(choiceId: "method_trap", title: "Ловушка"),
                PVEMissionChoice(choiceId: "method_signs", title: "Знак")
            ]
        case "moral_choice", "lord_hook":
            return [
                PVEMissionChoice(choiceId: "method_parley", title: "Переговоры"),
                PVEMissionChoice(choiceId: "method_track", title: "Улики"),
                PVEMissionChoice(choiceId: "method_signs", title: "Знак")
            ]
        case "investigation", "puzzle_check", "artifact":
            return [
                PVEMissionChoice(choiceId: "method_track", title: "След"),
                PVEMissionChoice(choiceId: "method_trap", title: "Механизм"),
                PVEMissionChoice(choiceId: "method_signs", title: "Знак")
            ]
        default:
            return [
                PVEMissionChoice(choiceId: "method_track", title: "След"),
                PVEMissionChoice(choiceId: "method_parley", title: "Слова"),
                PVEMissionChoice(choiceId: "method_silver", title: "Сталь")
            ]
        }
    }

    private func canonicalStat(_ raw: String) -> String {
        switch raw.lowercased() {
        case "strength", "combat":
            return "Сила"
        case "agility", "dexterity":
            return "Ловкость"
        case "reason", "mind", "intellect", "lore":
            return "Разум"
        case "charisma", "empathy", "influence":
            return "Харизма"
        case "will", "magic":
            return "Воля"
        default:
            return Self.canonicalStats.contains(raw) ? raw : "Сила"
        }
    }

    private static let canonicalStats = ["Сила", "Ловкость", "Разум", "Харизма", "Воля"]

    private static let choiceEffects: [String: [String: Int]] = [
        "approach_cautious": ["Разум": 1, "Ловкость": 1],
        "approach_rushed": ["Сила": 1, "Разум": -1],
        "approach_direct": [:],
        "method_silver": ["Сила": 1],
        "method_trap": ["Ловкость": 1],
        "method_signs": ["Воля": 1],
        "method_track": ["Разум": 1],
        "method_parley": ["Харизма": 1]
    ]
}

struct PVEMissionChoice: Identifiable, Equatable {
    let choiceId: String
    let title: String

    var id: String { choiceId }
}

struct PVEMissionModifier: Equatable {
    let source: String
    let label: String
    let value: Int

    var json: [String: JSONValue] {
        [
            "source": .string(source),
            "label": .string(label),
            "value": .int(value)
        ]
    }
}

struct PVERollDraft: Identifiable, Equatable {
    let checkIndex: Int
    let stat: String
    let roll: Int
    let dc: Int
    let modifiers: [PVEMissionModifier]
    let checkId: String
    let rollId: String
    let createdAt: Date

    var id: String { rollId }

    var modifierTotal: Int {
        modifiers.reduce(0) { $0 + $1.value }
    }

    func statValue(player: PlayerProfile) -> Int {
        player.stats[stat] ?? 0
    }

    func total(player: PlayerProfile) -> Int {
        roll + statValue(player: player) + modifierTotal
    }

    func eventPayload(draft: PvESceneDraft) -> [String: JSONValue] {
        let created = ISO8601DateFormatter().string(from: createdAt)
        let total = total(player: draft.player)
        return [
            "roll_id": .string(rollId),
            "check_id": .string(checkId),
            "check_index": .int(checkIndex),
            "source": .string("app_generated"),
            "created_at": .string(created),
            "rolled_at": .string(created),
            "player_id": .string(draft.player.playerId),
            "qr_id": .string(draft.qr.qrId),
            "scenario_id": .string(draft.scenario.scenarioId),
            "die": .string("d20"),
            "roll": .int(roll),
            "roll_value": .int(roll),
            "stat": .string(stat),
            "stat_value": .int(statValue(player: draft.player)),
            "modifiers": .array(modifiers.map { .object($0.json) }),
            "server_modifier_total": .int(modifierTotal),
            "total": .int(total),
            "dc": .int(dc),
            "outcome": .string(total >= dc ? "success" : "failure")
        ]
    }
}
