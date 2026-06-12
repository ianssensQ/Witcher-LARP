import Foundation

struct PlayerSnapshot: Codable, Equatable {
    let snapshotVersion: Int
    let playerId: String
    let displayName: String
    let roleType: String
    let actId: String?
    let level: Int
    let xp: Int
    let gold: Int
    let reputationLabel: String
    let goals: [PlayerGoal]
    let pveScenarios: [PvEScenarioCard]?

    enum CodingKeys: String, CodingKey {
        case snapshotVersion = "snapshot_version"
        case playerId = "player_id"
        case displayName = "display_name"
        case roleType = "role_type"
        case actId = "act_id"
        case level
        case xp
        case gold
        case reputationLabel = "reputation_label"
        case goals
        case pveScenarios = "pve_scenarios"
    }
}

struct PlayerGoal: Codable, Equatable, Identifiable {
    let goalId: String
    let title: String
    let progressLabel: String?

    var id: String { goalId }

    enum CodingKeys: String, CodingKey {
        case goalId = "goal_id"
        case title
        case progressLabel = "progress_label"
    }
}

struct PvEScenarioCard: Codable, Equatable, Identifiable {
    let scenarioId: String
    let actId: String?
    let tier: String?
    let sceneType: String?
    let primaryStat: String?
    let dc: String?
    let combatProfileId: String?
    let rewardId: String?
    let scenarioTitle: String?
    let visibleHook: String?
    let playerBrief: String?
    let storySummary: String?
    let visualAssetId: String?
    let visualPrompt: String?
    let iconKey: String?
    let contentLane: String?
    let estimatedMinutes: String?
    let trialType: String?
    let trialPrompt: String?
    let statCheckLabel: String?
    let gearTags: String?
    let monsterTags: String?
    let successConsequence: String?
    let partialConsequence: String?
    let failureConsequence: String?
    let rewardSummary: String?
    let worldEffect: String?
    let questFlowVersion: String?
    let boardDescription: String?
    let scanReveal: String?
    let choicePrompt: String?
    let choiceOptionsJSON: String?
    let encounterStepsJSON: String?
    let victoryRule: String?
    let branchRewardPolicy: String?
    let reputationHint: String?
    let successText: String?
    let failureText: String?
    let timeoutOutcome: String?

    var id: String { scenarioId }
    var displayTitle: String { scenarioTitle ?? scenarioId }
    var displayBrief: String { scanReveal ?? playerBrief ?? boardDescription ?? visibleHook ?? "" }
    var displayCheck: String { statCheckLabel ?? [primaryStat, dc].compactMap { $0 }.joined(separator: " vs ") }

    var gearTagList: [String] {
        splitTags(gearTags)
    }

    var monsterTagList: [String] {
        splitTags(monsterTags)
    }

    enum CodingKeys: String, CodingKey {
        case scenarioId = "scenario_id"
        case actId = "act_id"
        case tier
        case sceneType = "scene_type"
        case primaryStat = "primary_stat"
        case dc
        case combatProfileId = "combat_profile_id"
        case rewardId = "reward_id"
        case scenarioTitle = "scenario_title"
        case visibleHook = "visible_hook"
        case playerBrief = "player_brief"
        case storySummary = "story_summary"
        case visualAssetId = "visual_asset_id"
        case visualPrompt = "visual_prompt"
        case iconKey = "icon_key"
        case contentLane = "content_lane"
        case estimatedMinutes = "estimated_minutes"
        case trialType = "trial_type"
        case trialPrompt = "trial_prompt"
        case statCheckLabel = "stat_check_label"
        case gearTags = "gear_tags"
        case monsterTags = "monster_tags"
        case successConsequence = "success_consequence"
        case partialConsequence = "partial_consequence"
        case failureConsequence = "failure_consequence"
        case rewardSummary = "reward_summary"
        case worldEffect = "world_effect"
        case questFlowVersion = "quest_flow_version"
        case boardDescription = "board_description"
        case scanReveal = "scan_reveal"
        case choicePrompt = "choice_prompt"
        case choiceOptionsJSON = "choice_options_json"
        case encounterStepsJSON = "encounter_steps_json"
        case victoryRule = "victory_rule"
        case branchRewardPolicy = "branch_reward_policy"
        case reputationHint = "reputation_hint"
        case successText = "success_text"
        case failureText = "failure_text"
        case timeoutOutcome = "timeout_outcome"
    }

    private func splitTags(_ value: String?) -> [String] {
        guard let value else { return [] }
        return value.split(separator: ";").map { String($0).trimmingCharacters(in: .whitespaces) }
    }
}
