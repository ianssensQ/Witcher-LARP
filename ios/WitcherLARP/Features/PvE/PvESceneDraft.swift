import Foundation

struct PvESceneDraft: Identifiable, Equatable {
    let qr: QRObject
    let scenario: PVEScenario
    let reward: Reward?
    let player: PlayerProfile
    let source: QRInputSource
    let roll: Int
    let checkId: String
    let rollId: String
    let createdAt: Date

    var id: String { checkId }

    var statValue: Int {
        player.stats[scenario.primaryStat] ?? 0
    }

    var total: Int {
        roll + statValue
    }

    var result: String {
        if total >= scenario.dc {
            return "success"
        }
        if total >= scenario.dc - 2 {
            return "partial_success"
        }
        return "failure"
    }

    var resultLabel: String {
        switch result {
        case "success":
            return "Успех"
        case "partial_success":
            return "Частичный успех"
        case "failure":
            return "Провал"
        default:
            return result
        }
    }

    var statLabel: String {
        switch scenario.primaryStat.lowercased() {
        case "strength":
            return "Сила"
        case "agility":
            return "Ловкость"
        case "intellect":
            return "Интеллект"
        case "empathy":
            return "Эмпатия"
        case "will":
            return "Воля"
        default:
            return scenario.primaryStat
        }
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
            return "без награды"
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

    var eventPayload: [String: JSONValue] {
        let created = ISO8601DateFormatter().string(from: createdAt)
        let rollEntry: [String: JSONValue] = [
            "roll_id": .string(rollId),
            "check_id": .string(checkId),
            "source": .string("app_generated"),
            "created_at": .string(created),
            "player_id": .string(player.playerId),
            "qr_id": .string(qr.qrId),
            "scenario_id": .string(scenario.scenarioId),
            "die": .string("d20"),
            "roll": .int(roll),
            "roll_value": .int(roll),
            "stat": .string(scenario.primaryStat),
            "stat_value": .int(statValue),
            "modifiers": .array([]),
            "server_modifier_total": .int(0),
            "total": .int(total),
            "dc": .int(scenario.dc),
            "outcome": .string(result),
            "rolled_at": .string(created)
        ]
        return [
            "player_id": .string(player.playerId),
            "scenario_id": .string(scenario.scenarioId),
            "qr_id": .string(qr.qrId),
            "manual_code": .string(qr.manualCode),
            "check_id": .string(checkId),
            "act_id": .string(qr.actId),
            "unlock_source": .string("act1_default"),
            "roll_source": .string("app_generated"),
            "roll": .int(roll),
            "stat": .string(scenario.primaryStat),
            "stat_value": .int(statValue),
            "modifiers": .array([]),
            "server_modifiers": .array([]),
            "server_modifier_total": .int(0),
            "total": .int(total),
            "dc": .int(scenario.dc),
            "roll_log": .array([.object(rollEntry)]),
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
}
