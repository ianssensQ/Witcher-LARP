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

    var boardDescriptionText: String? {
        cleaned(scenario.boardDescription)
    }

    var scanRevealText: String? {
        cleaned(scenario.scanReveal)
    }

    var visualAssetName: String? {
        cleaned(scenario.visualAssetId)
    }

    var missionText: String {
        if let text = scanRevealText ?? cleaned(scenario.missionText) ?? boardDescriptionText {
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
        let configured = configuredChoices
        if !configured.isEmpty {
            return [configured]
        }
        return [
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
        rollLog.count >= encounterSteps.count
    }

    var checkStats: [String] {
        encounterSteps.map(\.stat)
    }

    var nextCheckStep: PVEEncounterStepDraft? {
        guard isReadyForChecks, rollLog.count < encounterSteps.count else { return nil }
        return encounterSteps[rollLog.count]
    }

    var nextCheckStat: String? {
        nextCheckStep?.stat
    }

    private var encounterSteps: [PVEEncounterStepDraft] {
        let configured = configuredEncounterSteps
        if !configured.isEmpty {
            var steps = Array(configured.prefix(3))
            let fallback = fallbackCheckStats
            while steps.count < 3 {
                let index = steps.count
                steps.append(PVEEncounterStepDraft(
                    stepId: "fallback-\(index + 1)",
                    title: "Испытание \(index + 1)",
                    stat: fallback[index],
                    dc: scenario.dc
                ))
            }
            return steps
        }
        return fallbackCheckStats.enumerated().map { index, stat in
            PVEEncounterStepDraft(
                stepId: "fallback-\(index + 1)",
                title: "Испытание \(index + 1)",
                stat: stat,
                dc: scenario.dc
            )
        }
    }

    private var fallbackCheckStats: [String] {
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

    var effectiveRewardApprovalPolicy: String {
        reward?.approvalPolicy ?? scenario.rewardApprovalPolicy ?? "auto"
    }

    var rewardStatus: String {
        guard result == "success" else { return "none" }
        switch effectiveRewardApprovalPolicy.lowercased() {
        case "pending_master_approval", "master_approval", "needs_master_review":
            return "pending_master_approval"
        default:
            return "auto"
        }
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
            "\(roll.stepTitle ?? roll.stat): d20 \(roll.roll) + \(roll.statValue(player: player)) + \(roll.modifierTotal) = \(roll.total(player: player))"
        }
        .joined(separator: "\n")
    }

    var lastRollSummary: String {
        guard let roll = rollLog.last else { return "" }
        return "\(roll.stepTitle ?? roll.stat): d20 \(roll.roll) + \(roll.statValue(player: player)) + \(roll.modifierTotal) = \(roll.total(player: player))"
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
            "reward_approval_policy": .string(effectiveRewardApprovalPolicy),
            "reward_status": .string(rewardStatus),
            "qr_mode": .string(qr.qrMode),
            "physical_presence_confirmed": .bool(true),
            "source": .string(source.apiValue),
            "choice_source": .string(configuredChoices.isEmpty ? "fallback" : "snapshot"),
            "encounter_source": .string(configuredEncounterSteps.isEmpty ? "fallback" : "snapshot"),
            "visual_asset_id": .string(visualAssetName ?? "")
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
        guard let step = nextCheckStep else { return nil }
        var updated = self
        updated.rollLog.append(PVERollDraft(
            checkIndex: rollLog.count + 1,
            stat: step.stat,
            roll: Int.random(in: 1...20),
            dc: step.dc,
            modifiers: choiceModifiers(for: step.stat),
            checkId: step.stepId.isEmpty ? "ios-check-\(UUID().uuidString)" : step.stepId,
            rollId: "ios-roll-\(UUID().uuidString)",
            stepTitle: step.title,
            createdAt: Date()
        ))
        return updated
    }

    func choiceModifiers(for stat: String) -> [PVEMissionModifier] {
        let configured = configuredChoiceModifiers(for: stat)
        if !configured.isEmpty {
            return configured
        }
        return selectedChoiceIds.compactMap { choiceId in
            guard let value = Self.choiceEffects[choiceId]?[stat], value != 0 else { return nil }
            return PVEMissionModifier(source: "system", label: "choice:\(choiceId)", value: value)
        }
    }

    private var configuredChoices: [PVEMissionChoice] {
        Self.jsonObjectArray(from: scenario.choiceOptionsJSON, nestedKeys: ["choices", "options"])
            .enumerated()
            .compactMap { index, object in
                let title = Self.stringValue(
                    object["title"] ?? object["label"] ?? object["text"] ?? object["name"]
                )
                guard let title, !title.isEmpty else { return nil }
                let choiceId = Self.stringValue(object["choice_id"] ?? object["id"])
                    ?? "choice_\(index + 1)"
                return PVEMissionChoice(choiceId: choiceId, title: title)
            }
    }

    private var configuredEncounterSteps: [PVEEncounterStepDraft] {
        Self.jsonObjectArray(from: scenario.encounterStepsJSON, nestedKeys: ["steps", "checks", "encounter_steps"])
            .enumerated()
            .compactMap { index, object in
                let stat = canonicalStat(
                    Self.stringValue(object["stat"] ?? object["primary_stat"] ?? object["check_stat"]) ?? scenario.primaryStat
                )
                let title = Self.stringValue(
                    object["title"] ?? object["label"] ?? object["text"] ?? object["description"]
                ) ?? "Испытание \(index + 1)"
                let stepId = Self.stringValue(object["step_id"] ?? object["check_id"] ?? object["id"])
                    ?? "snapshot-step-\(index + 1)"
                let dc = Self.intValue(object["dc"] ?? object["difficulty"]) ?? scenario.dc
                return PVEEncounterStepDraft(stepId: stepId, title: title, stat: stat, dc: dc)
            }
    }

    private func configuredChoiceModifiers(for stat: String) -> [PVEMissionModifier] {
        let objects = Self.jsonObjectArray(from: scenario.choiceOptionsJSON, nestedKeys: ["choices", "options"])
        var modifiers: [PVEMissionModifier] = []
        for choiceId in selectedChoiceIds {
            guard let object = objects.first(where: { object in
                let id = Self.stringValue(object["choice_id"] ?? object["id"])
                return id == choiceId
            }) else { continue }
            guard let modifierMap = (object["stat_modifiers"] ?? object["modifiers"]) as? [String: Any] else {
                continue
            }
            let value = modifierMap.first { key, _ in
                canonicalStat(key) == stat
            }.flatMap { Self.intValue($0.value) } ?? 0
            guard value != 0 else { continue }
            modifiers.append(PVEMissionModifier(source: "choice", label: "choice:\(choiceId)", value: value))
        }
        return modifiers
    }

    private func cleaned(_ raw: String?) -> String? {
        let value = raw?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        return value.isEmpty ? nil : value
    }

    private static func jsonObjectArray(from raw: String?, nestedKeys: [String]) -> [[String: Any]] {
        guard
            let raw,
            let data = raw.data(using: .utf8),
            let decoded = try? JSONSerialization.jsonObject(with: data)
        else { return [] }
        if let array = decoded as? [[String: Any]] {
            return array
        }
        if let object = decoded as? [String: Any] {
            for key in nestedKeys {
                if let array = object[key] as? [[String: Any]] {
                    return array
                }
            }
        }
        return []
    }

    private static func stringValue(_ value: Any?) -> String? {
        switch value {
        case let string as String:
            let trimmed = string.trimmingCharacters(in: .whitespacesAndNewlines)
            return trimmed.isEmpty ? nil : trimmed
        case let int as Int:
            return String(int)
        case let double as Double:
            return String(Int(double))
        default:
            return nil
        }
    }

    private static func intValue(_ value: Any?) -> Int? {
        switch value {
        case let int as Int:
            return int
        case let double as Double:
            return Int(double)
        case let string as String:
            return Int(string.trimmingCharacters(in: .whitespacesAndNewlines))
        default:
            return nil
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

struct PVEEncounterStepDraft: Equatable {
    let stepId: String
    let title: String
    let stat: String
    let dc: Int
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
    let stepTitle: String?
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
            "step_title": .string(stepTitle ?? ""),
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
