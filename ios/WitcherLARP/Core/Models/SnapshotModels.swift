import Foundation

typealias SnapshotRow = [String: JSONValue]

struct PlayerSnapshot: Codable, Equatable {
    let snapshotVersion: String
    let generatedAt: String?
    let auth: SnapshotAuth?
    let player: PlayerProfile?
    let players: [PlayerProfile]
    let orders: [OrderSummary]
    let qrObjects: [QRObject]
    let pveScenarios: [PVEScenario]
    let mobs: [Mob]
    let rewards: [Reward]
    let items: [SnapshotRow]
    let materials: [SnapshotRow]
    let materialMarkets: [SnapshotRow]
    let materialDropRules: [SnapshotRow]
    let cards: [SnapshotRow]
    let potions: [SnapshotRow]
    let artifacts: [SnapshotRow]
    let gwentCards: [GwentCard]
    let gwentDecks: [GwentDeck]
    let assetOwnership: [SnapshotRow]
    let potionInventory: [SnapshotRow]
    let potionMarket: [SnapshotRow]
    let materialInventory: [SnapshotRow]
    let materialMarket: [SnapshotRow]
    let cardMarket: [SnapshotRow]
    let tradeTransfers: [SnapshotRow]
    let rewardApprovals: [SnapshotRow]
    let checks: SnapshotChecks
    let goals: SnapshotGoals
    let actUnlockCodes: [SnapshotRow]
    let actUnlockState: SnapshotRow

    var currentPlayer: PlayerProfile? {
        player ?? players.first
    }

    var visibleGoals: [PlayerGoal] {
        goals.personalGoals
    }

    init(
        snapshotVersion: String,
        generatedAt: String?,
        auth: SnapshotAuth?,
        player: PlayerProfile?,
        players: [PlayerProfile],
        orders: [OrderSummary],
        qrObjects: [QRObject],
        pveScenarios: [PVEScenario],
        mobs: [Mob],
        rewards: [Reward],
        items: [SnapshotRow],
        materials: [SnapshotRow],
        materialMarkets: [SnapshotRow],
        materialDropRules: [SnapshotRow],
        cards: [SnapshotRow],
        potions: [SnapshotRow],
        artifacts: [SnapshotRow],
        gwentCards: [GwentCard],
        gwentDecks: [GwentDeck],
        assetOwnership: [SnapshotRow],
        potionInventory: [SnapshotRow],
        potionMarket: [SnapshotRow],
        materialInventory: [SnapshotRow],
        materialMarket: [SnapshotRow],
        cardMarket: [SnapshotRow],
        tradeTransfers: [SnapshotRow],
        rewardApprovals: [SnapshotRow],
        checks: SnapshotChecks,
        goals: SnapshotGoals,
        actUnlockCodes: [SnapshotRow],
        actUnlockState: SnapshotRow
    ) {
        self.snapshotVersion = snapshotVersion
        self.generatedAt = generatedAt
        self.auth = auth
        self.player = player
        self.players = players
        self.orders = orders
        self.qrObjects = qrObjects
        self.pveScenarios = pveScenarios
        self.mobs = mobs
        self.rewards = rewards
        self.items = items
        self.materials = materials
        self.materialMarkets = materialMarkets
        self.materialDropRules = materialDropRules
        self.cards = cards
        self.potions = potions
        self.artifacts = artifacts
        self.gwentCards = gwentCards
        self.gwentDecks = gwentDecks
        self.assetOwnership = assetOwnership
        self.potionInventory = potionInventory
        self.potionMarket = potionMarket
        self.materialInventory = materialInventory
        self.materialMarket = materialMarket
        self.cardMarket = cardMarket
        self.tradeTransfers = tradeTransfers
        self.rewardApprovals = rewardApprovals
        self.checks = checks
        self.goals = goals
        self.actUnlockCodes = actUnlockCodes
        self.actUnlockState = actUnlockState
    }

    func updatingCurrentPlayer(_ updated: PlayerProfile) -> PlayerSnapshot {
        let updatedPlayers = players.map { $0.playerId == updated.playerId ? updated : $0 }
        let containsUpdated = updatedPlayers.contains { $0.playerId == updated.playerId }
        return PlayerSnapshot(
            snapshotVersion: snapshotVersion,
            generatedAt: generatedAt,
            auth: auth,
            player: currentPlayer?.playerId == updated.playerId ? updated : player,
            players: containsUpdated ? updatedPlayers : [updated] + updatedPlayers,
            orders: orders,
            qrObjects: qrObjects,
            pveScenarios: pveScenarios,
            mobs: mobs,
            rewards: rewards,
            items: items,
            materials: materials,
            materialMarkets: materialMarkets,
            materialDropRules: materialDropRules,
            cards: cards,
            potions: potions,
            artifacts: artifacts,
            gwentCards: gwentCards,
            gwentDecks: gwentDecks,
            assetOwnership: assetOwnership,
            potionInventory: potionInventory,
            potionMarket: potionMarket,
            materialInventory: materialInventory,
            materialMarket: materialMarket,
            cardMarket: cardMarket,
            tradeTransfers: tradeTransfers,
            rewardApprovals: rewardApprovals,
            checks: checks,
            goals: goals,
            actUnlockCodes: actUnlockCodes,
            actUnlockState: actUnlockState
        )
    }

    enum CodingKeys: String, CodingKey {
        case snapshotVersion = "snapshot_version"
        case generatedAt = "generated_at"
        case auth
        case player
        case players
        case orders
        case qrObjects = "qr_objects"
        case pveScenarios = "pve_scenarios"
        case mobs
        case rewards
        case items
        case materials
        case materialMarkets = "material_markets"
        case materialDropRules = "material_drop_rules"
        case cards
        case potions
        case artifacts
        case gwentCards = "gwent_cards"
        case gwentDecks = "gwent_decks"
        case assetOwnership = "asset_ownership"
        case potionInventory = "potion_inventory"
        case potionMarket = "potion_market"
        case materialInventory = "material_inventory"
        case materialMarket = "material_market"
        case cardMarket = "card_market"
        case tradeTransfers = "trade_transfers"
        case rewardApprovals = "reward_approvals"
        case checks
        case goals
        case actUnlockCodes = "act_unlock_codes"
        case actUnlockState = "act_unlock_state"
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        snapshotVersion = container.decodeFlexibleString(forKey: .snapshotVersion)
        generatedAt = container.decodeFlexibleStringIfPresent(forKey: .generatedAt)
        auth = try container.decodeIfPresent(SnapshotAuth.self, forKey: .auth)
        player = try container.decodeIfPresent(PlayerProfile.self, forKey: .player)
        players = (try? container.decode([PlayerProfile].self, forKey: .players)) ?? []
        orders = (try? container.decode([OrderSummary].self, forKey: .orders)) ?? []
        qrObjects = (try? container.decode([QRObject].self, forKey: .qrObjects)) ?? []
        pveScenarios = (try? container.decode([PVEScenario].self, forKey: .pveScenarios)) ?? []
        mobs = (try? container.decode([Mob].self, forKey: .mobs)) ?? []
        rewards = (try? container.decode([Reward].self, forKey: .rewards)) ?? []
        items = (try? container.decode([SnapshotRow].self, forKey: .items)) ?? []
        materials = (try? container.decode([SnapshotRow].self, forKey: .materials)) ?? []
        materialMarkets = (try? container.decode([SnapshotRow].self, forKey: .materialMarkets)) ?? []
        materialDropRules = (try? container.decode([SnapshotRow].self, forKey: .materialDropRules)) ?? []
        cards = (try? container.decode([SnapshotRow].self, forKey: .cards)) ?? []
        potions = (try? container.decode([SnapshotRow].self, forKey: .potions)) ?? []
        artifacts = (try? container.decode([SnapshotRow].self, forKey: .artifacts)) ?? []
        gwentCards = (try? container.decode([GwentCard].self, forKey: .gwentCards)) ?? []
        gwentDecks = (try? container.decode([GwentDeck].self, forKey: .gwentDecks)) ?? []
        assetOwnership = (try? container.decode([SnapshotRow].self, forKey: .assetOwnership)) ?? []
        potionInventory = (try? container.decode([SnapshotRow].self, forKey: .potionInventory)) ?? []
        potionMarket = (try? container.decode([SnapshotRow].self, forKey: .potionMarket)) ?? []
        materialInventory = (try? container.decode([SnapshotRow].self, forKey: .materialInventory)) ?? []
        materialMarket = (try? container.decode([SnapshotRow].self, forKey: .materialMarket)) ?? []
        cardMarket = (try? container.decode([SnapshotRow].self, forKey: .cardMarket)) ?? []
        tradeTransfers = (try? container.decode([SnapshotRow].self, forKey: .tradeTransfers)) ?? []
        rewardApprovals = (try? container.decode([SnapshotRow].self, forKey: .rewardApprovals)) ?? []
        checks = (try? container.decode(SnapshotChecks.self, forKey: .checks)) ?? SnapshotChecks()
        goals = (try? container.decode(SnapshotGoals.self, forKey: .goals)) ?? SnapshotGoals()
        actUnlockCodes = (try? container.decode([SnapshotRow].self, forKey: .actUnlockCodes)) ?? []
        actUnlockState = (try? container.decode(SnapshotRow.self, forKey: .actUnlockState)) ?? [:]
    }
}

struct SnapshotChecks: Codable, Equatable {
    let xpRules: [SnapshotRow]

    init(xpRules: [SnapshotRow] = []) {
        self.xpRules = xpRules
    }

    enum CodingKeys: String, CodingKey {
        case xpRules = "xp_rules"
    }
}

struct SnapshotAuth: Codable, Equatable {
    let scope: String
    let playerId: String
    let playerCodeId: String?

    enum CodingKeys: String, CodingKey {
        case scope
        case playerId = "player_id"
        case playerCodeId = "player_code_id"
    }
}

struct PlayerProfile: Codable, Equatable, Identifiable {
    let playerId: String
    let roleType: String
    let displayName: String
    let actId: String?
    let level: Int
    let xp: Int
    let gold: Int
    let challengeTokens: Int
    let reputationLabel: String
    let stats: [String: Int]
    let unspentStatPoints: Int

    var id: String { playerId }

    init(
        playerId: String,
        roleType: String,
        displayName: String,
        actId: String?,
        level: Int,
        xp: Int,
        gold: Int,
        challengeTokens: Int,
        reputationLabel: String,
        stats: [String: Int],
        unspentStatPoints: Int
    ) {
        self.playerId = playerId
        self.roleType = roleType
        self.displayName = displayName
        self.actId = actId
        self.level = level
        self.xp = xp
        self.gold = gold
        self.challengeTokens = challengeTokens
        self.reputationLabel = reputationLabel
        self.stats = stats
        self.unspentStatPoints = unspentStatPoints
    }

    func applyingStatDelta(_ stat: String, unspentStatPointsAfter: Int) -> PlayerProfile {
        var nextStats = stats
        nextStats[stat] = (nextStats[stat] ?? 0) + 1
        return PlayerProfile(
            playerId: playerId,
            roleType: roleType,
            displayName: displayName,
            actId: actId,
            level: level,
            xp: xp,
            gold: gold,
            challengeTokens: challengeTokens,
            reputationLabel: reputationLabel,
            stats: nextStats,
            unspentStatPoints: unspentStatPointsAfter
        )
    }

    enum CodingKeys: String, CodingKey {
        case playerId = "player_id"
        case roleType = "role_type"
        case displayName = "display_name"
        case actId = "act_id"
        case level
        case xp
        case gold
        case challengeTokens = "challenge_tokens"
        case reputationLabel = "reputation_label"
        case reputationState = "reputation_state"
        case statsJson = "stats_json"
        case stats
        case unspentStatPoints = "unspent_stat_points"
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        playerId = container.decodeFlexibleString(forKey: .playerId)
        roleType = container.decodeFlexibleString(forKey: .roleType)
        displayName = container.decodeFlexibleString(forKey: .displayName)
        actId = container.decodeFlexibleStringIfPresent(forKey: .actId)
        level = container.decodeFlexibleInt(forKey: .level, default: 1)
        xp = container.decodeFlexibleInt(forKey: .xp)
        gold = container.decodeFlexibleInt(forKey: .gold)
        challengeTokens = container.decodeFlexibleInt(forKey: .challengeTokens)
        let explicitReputation = container.decodeFlexibleStringIfPresent(forKey: .reputationLabel)
        let reputationState = (try? container.decodeIfPresent(SnapshotRow.self, forKey: .reputationState)) ?? nil
        reputationLabel = explicitReputation
            ?? reputationState?.string("canonical_label")
            ?? reputationState?.string("state_label")
            ?? reputationState?.string("player_descriptor")
            ?? "Нейтральный"
        let savedStats = (try? container.decodeIfPresent([String: Int].self, forKey: .stats)) ?? nil
        stats = PlayerProfile.decodeStats(container.decodeFlexibleStringIfPresent(forKey: .statsJson))
            .merging(savedStats ?? [:]) { _, local in local }
        unspentStatPoints = container.decodeFlexibleInt(forKey: .unspentStatPoints)
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(playerId, forKey: .playerId)
        try container.encode(roleType, forKey: .roleType)
        try container.encode(displayName, forKey: .displayName)
        try container.encodeIfPresent(actId, forKey: .actId)
        try container.encode(level, forKey: .level)
        try container.encode(xp, forKey: .xp)
        try container.encode(gold, forKey: .gold)
        try container.encode(challengeTokens, forKey: .challengeTokens)
        try container.encode(reputationLabel, forKey: .reputationLabel)
        try container.encode(stats, forKey: .stats)
        try container.encode(unspentStatPoints, forKey: .unspentStatPoints)
    }

    private static func decodeStats(_ raw: String?) -> [String: Int] {
        guard
            let raw,
            let data = raw.data(using: .utf8),
            let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any]
        else { return [:] }
        return object.reduce(into: [:]) { result, item in
            if let intValue = item.value as? Int {
                result[item.key] = intValue
            } else if let stringValue = item.value as? String, let intValue = Int(stringValue) {
                result[item.key] = intValue
            }
        }
    }
}

struct SnapshotGoals: Codable, Equatable {
    let personalGoals: [PlayerGoal]
    let goalTracks: [SnapshotRow]

    init(personalGoals: [PlayerGoal] = [], goalTracks: [SnapshotRow] = []) {
        self.personalGoals = personalGoals
        self.goalTracks = goalTracks
    }

    enum CodingKeys: String, CodingKey {
        case personalGoals = "personal_goals"
        case goalTracks = "goal_tracks"
    }
}

struct PlayerGoal: Codable, Equatable, Identifiable {
    let goalId: String
    let title: String
    let progressLabel: String?

    var id: String { goalId }

    enum CodingKeys: String, CodingKey {
        case goalId = "goal_id"
        case publicText = "public_text"
        case title
        case progressLabel = "progress_label"
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        goalId = container.decodeFlexibleString(forKey: .goalId)
        title = container.decodeFlexibleStringIfPresent(forKey: .title)
            ?? container.decodeFlexibleStringIfPresent(forKey: .publicText)
            ?? goalId
        progressLabel = container.decodeFlexibleStringIfPresent(forKey: .progressLabel)
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(goalId, forKey: .goalId)
        try container.encode(title, forKey: .title)
        try container.encodeIfPresent(progressLabel, forKey: .progressLabel)
    }
}

struct QRObject: Codable, Equatable, Identifiable {
    let qrId: String
    let manualCode: String
    let scenarioId: String
    let qrMode: String
    let actId: String
    let locationNodeId: String
    let physicalPresenceRequired: Bool

    var id: String { qrId }

    enum CodingKeys: String, CodingKey {
        case qrId = "qr_id"
        case manualCode = "manual_code"
        case scenarioId = "scenario_id"
        case qrMode = "qr_mode"
        case actId = "act_id"
        case locationNodeId = "location_node_id"
        case physicalPresenceRequired = "physical_presence_required"
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        qrId = container.decodeFlexibleString(forKey: .qrId)
        manualCode = container.decodeFlexibleString(forKey: .manualCode)
        scenarioId = container.decodeFlexibleString(forKey: .scenarioId)
        qrMode = container.decodeFlexibleString(forKey: .qrMode)
        actId = container.decodeFlexibleString(forKey: .actId)
        locationNodeId = container.decodeFlexibleString(forKey: .locationNodeId)
        physicalPresenceRequired = container.decodeFlexibleBool(forKey: .physicalPresenceRequired, default: true)
    }
}

struct PVEScenario: Codable, Equatable, Identifiable {
    let scenarioId: String
    let actId: String
    let tier: Int
    let sceneType: String
    let primaryStat: String
    let dc: Int
    let checkPolicy: String
    let combatProfileId: String
    let rewardId: String
    let missionText: String?
    let boardDescription: String?
    let scanReveal: String?
    let visualAssetId: String?
    let choiceOptionsJSON: String?
    let encounterStepsJSON: String?
    let rewardApprovalPolicy: String?
    let successText: String
    let failureText: String

    var id: String { scenarioId }

    enum CodingKeys: String, CodingKey {
        case scenarioId = "scenario_id"
        case actId = "act_id"
        case tier
        case sceneType = "scene_type"
        case primaryStat = "primary_stat"
        case dc
        case checkPolicy = "check_policy"
        case combatProfileId = "combat_profile_id"
        case rewardId = "reward_id"
        case missionText = "mission_text"
        case boardDescription = "board_description"
        case scanReveal = "scan_reveal"
        case visualAssetId = "visual_asset_id"
        case choiceOptionsJSON = "choice_options_json"
        case encounterStepsJSON = "encounter_steps_json"
        case rewardApprovalPolicy = "reward_approval_policy"
        case successText = "success_text"
        case failureText = "failure_text"
    }

    enum FallbackCodingKeys: String, CodingKey {
        case description
        case hook
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        let fallbackContainer = try decoder.container(keyedBy: FallbackCodingKeys.self)
        scenarioId = container.decodeFlexibleString(forKey: .scenarioId)
        actId = container.decodeFlexibleString(forKey: .actId)
        tier = container.decodeFlexibleInt(forKey: .tier, default: 1)
        sceneType = container.decodeFlexibleString(forKey: .sceneType)
        primaryStat = container.decodeFlexibleString(forKey: .primaryStat)
        dc = container.decodeFlexibleInt(forKey: .dc)
        checkPolicy = container.decodeFlexibleStringIfPresent(forKey: .checkPolicy) ?? "single_d20"
        combatProfileId = container.decodeFlexibleString(forKey: .combatProfileId)
        rewardId = container.decodeFlexibleString(forKey: .rewardId)
        boardDescription = container.decodeFlexibleStringIfPresent(forKey: .boardDescription)
        scanReveal = container.decodeFlexibleStringIfPresent(forKey: .scanReveal)
        visualAssetId = container.decodeFlexibleStringIfPresent(forKey: .visualAssetId)
        choiceOptionsJSON = container.decodeFlexibleStringIfPresent(forKey: .choiceOptionsJSON)
        encounterStepsJSON = container.decodeFlexibleStringIfPresent(forKey: .encounterStepsJSON)
        rewardApprovalPolicy = container.decodeFlexibleStringIfPresent(forKey: .rewardApprovalPolicy)
        missionText = container.decodeFlexibleStringIfPresent(forKey: .missionText)
            ?? scanReveal
            ?? boardDescription
            ?? fallbackContainer.decodeFlexibleStringIfPresent(forKey: .description)
            ?? fallbackContainer.decodeFlexibleStringIfPresent(forKey: .hook)
        successText = container.decodeFlexibleStringIfPresent(forKey: .successText) ?? "Успех"
        failureText = container.decodeFlexibleStringIfPresent(forKey: .failureText) ?? "Провал"
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(scenarioId, forKey: .scenarioId)
        try container.encode(actId, forKey: .actId)
        try container.encode(tier, forKey: .tier)
        try container.encode(sceneType, forKey: .sceneType)
        try container.encode(primaryStat, forKey: .primaryStat)
        try container.encode(dc, forKey: .dc)
        try container.encode(checkPolicy, forKey: .checkPolicy)
        try container.encode(combatProfileId, forKey: .combatProfileId)
        try container.encode(rewardId, forKey: .rewardId)
        try container.encodeIfPresent(missionText, forKey: .missionText)
        try container.encodeIfPresent(boardDescription, forKey: .boardDescription)
        try container.encodeIfPresent(scanReveal, forKey: .scanReveal)
        try container.encodeIfPresent(visualAssetId, forKey: .visualAssetId)
        try container.encodeIfPresent(choiceOptionsJSON, forKey: .choiceOptionsJSON)
        try container.encodeIfPresent(encounterStepsJSON, forKey: .encounterStepsJSON)
        try container.encodeIfPresent(rewardApprovalPolicy, forKey: .rewardApprovalPolicy)
        try container.encode(successText, forKey: .successText)
        try container.encode(failureText, forKey: .failureText)
    }
}

struct Mob: Codable, Equatable, Identifiable {
    let mobId: String
    let sceneDamage: Int
    let roundLimit: Int

    var id: String { mobId }

    enum CodingKeys: String, CodingKey {
        case mobId = "mob_id"
        case sceneDamage = "scene_damage"
        case roundLimit = "round_limit"
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        mobId = container.decodeFlexibleString(forKey: .mobId)
        sceneDamage = container.decodeFlexibleInt(forKey: .sceneDamage)
        roundLimit = container.decodeFlexibleInt(forKey: .roundLimit)
    }
}

struct Reward: Codable, Equatable, Identifiable {
    let rewardId: String
    let xp: Int
    let gold: Int
    let rarity: String
    let approvalPolicy: String

    var id: String { rewardId }

    enum CodingKeys: String, CodingKey {
        case rewardId = "reward_id"
        case xp
        case gold
        case rarity
        case approvalPolicy = "approval_policy"
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        rewardId = container.decodeFlexibleString(forKey: .rewardId)
        xp = container.decodeFlexibleInt(forKey: .xp)
        gold = container.decodeFlexibleInt(forKey: .gold)
        rarity = container.decodeFlexibleString(forKey: .rarity)
        approvalPolicy = container.decodeFlexibleString(forKey: .approvalPolicy)
    }
}

struct OrderSummary: Codable, Equatable, Identifiable {
    let orderId: String
    let lordId: String
    let targetPlayerId: String
    let acceptedByPlayerId: String
    let submittedByPlayerId: String
    let objectId: String
    let objectLabel: String
    let objectType: String
    let visibility: String
    let status: String
    let escrowRewardId: String
    let visibleHook: String
    let rewardLabel: String
    let rewardGold: Int
    let rewardXP: Int
    let proofQrId: String
    let scenarioId: String
    let locationLabel: String

    var id: String { orderId }
    var isAcceptable: Bool { ["published", "addressed_pending", "failed_retryable"].contains(status) }
    var isSubmittable: Bool { ["accepted", "in_progress", "claimed_at_prop", "submitted_pending_sync"].contains(status) }
    var effectiveProofQrId: String { proofQrId.isEmpty ? objectId : proofQrId }

    enum CodingKeys: String, CodingKey {
        case orderId = "order_id"
        case lordId = "lord_id"
        case targetPlayerId = "target_player_id"
        case acceptedByPlayerId = "accepted_by_player_id"
        case submittedByPlayerId = "submitted_by_player_id"
        case objectId = "object_id"
        case objectLabel = "object_label"
        case objectType = "object_type"
        case visibility
        case status
        case escrowRewardId = "escrow_reward_id"
        case visibleHook = "visible_hook"
        case rewardLabel = "reward_label"
        case rewardGold = "reward_gold"
        case rewardXP = "reward_xp"
        case proofQrId = "proof_qr_id"
        case scenarioId = "scenario_id"
        case locationLabel = "location_label"
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        orderId = container.decodeFlexibleString(forKey: .orderId)
        lordId = container.decodeFlexibleString(forKey: .lordId)
        targetPlayerId = container.decodeFlexibleString(forKey: .targetPlayerId)
        acceptedByPlayerId = container.decodeFlexibleString(forKey: .acceptedByPlayerId)
        submittedByPlayerId = container.decodeFlexibleString(forKey: .submittedByPlayerId)
        objectId = container.decodeFlexibleString(forKey: .objectId)
        objectLabel = container.decodeFlexibleStringIfPresent(forKey: .objectLabel) ?? objectId
        objectType = container.decodeFlexibleStringIfPresent(forKey: .objectType) ?? "unknown"
        visibility = container.decodeFlexibleString(forKey: .visibility)
        status = container.decodeFlexibleString(forKey: .status)
        escrowRewardId = container.decodeFlexibleString(forKey: .escrowRewardId)
        visibleHook = container.decodeFlexibleStringIfPresent(forKey: .visibleHook) ?? ""
        rewardLabel = container.decodeFlexibleStringIfPresent(forKey: .rewardLabel) ?? ""
        rewardGold = container.decodeFlexibleInt(forKey: .rewardGold)
        rewardXP = container.decodeFlexibleInt(forKey: .rewardXP)
        proofQrId = container.decodeFlexibleStringIfPresent(forKey: .proofQrId) ?? ""
        scenarioId = container.decodeFlexibleStringIfPresent(forKey: .scenarioId) ?? ""
        locationLabel = container.decodeFlexibleStringIfPresent(forKey: .locationLabel) ?? ""
    }
}

struct GwentCard: Codable, Equatable, Identifiable {
    let cardId: String
    let faction: String
    let row: String
    let type: String
    let strength: Int
    let effect: String
    let rarity: String
    let abilityTags: [String]
    let nameGroup: String
    let bondGroup: String
    let musterGroup: String
    let displayName: String
    let effectText: String
    let deckLimit: Int
    let sourceSet: String

    var id: String { cardId }

    enum CodingKeys: String, CodingKey {
        case cardId = "card_id"
        case faction
        case row
        case type
        case strength
        case effect
        case rarity
        case abilityTags = "ability_tags"
        case nameGroup = "name_group"
        case bondGroup = "bond_group"
        case musterGroup = "muster_group"
        case displayName = "display_name"
        case effectText = "effect_text"
        case deckLimit = "deck_limit"
        case sourceSet = "source_set"
    }

    init(
        cardId: String,
        faction: String,
        row: String,
        type: String,
        strength: Int,
        effect: String,
        rarity: String,
        abilityTags: [String],
        nameGroup: String,
        bondGroup: String,
        musterGroup: String,
        displayName: String,
        effectText: String,
        deckLimit: Int,
        sourceSet: String
    ) {
        self.cardId = cardId
        self.faction = faction
        self.row = row
        self.type = type
        self.strength = strength
        self.effect = effect
        self.rarity = rarity
        self.abilityTags = abilityTags
        self.nameGroup = nameGroup
        self.bondGroup = bondGroup
        self.musterGroup = musterGroup
        self.displayName = displayName
        self.effectText = effectText
        self.deckLimit = deckLimit
        self.sourceSet = sourceSet
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        cardId = container.decodeFlexibleString(forKey: .cardId)
        faction = container.decodeFlexibleString(forKey: .faction)
        row = container.decodeFlexibleString(forKey: .row)
        type = container.decodeFlexibleString(forKey: .type)
        strength = container.decodeFlexibleInt(forKey: .strength)
        effect = container.decodeFlexibleString(forKey: .effect)
        rarity = container.decodeFlexibleString(forKey: .rarity)
        if let tags = try? container.decodeIfPresent([String].self, forKey: .abilityTags) {
            abilityTags = tags
        } else {
            abilityTags = GwentCard.splitIds(container.decodeFlexibleStringIfPresent(forKey: .abilityTags))
        }
        nameGroup = container.decodeFlexibleStringIfPresent(forKey: .nameGroup) ?? ""
        bondGroup = container.decodeFlexibleStringIfPresent(forKey: .bondGroup) ?? ""
        musterGroup = container.decodeFlexibleStringIfPresent(forKey: .musterGroup) ?? ""
        displayName = container.decodeFlexibleStringIfPresent(forKey: .displayName) ?? ""
        effectText = container.decodeFlexibleStringIfPresent(forKey: .effectText) ?? ""
        deckLimit = container.decodeFlexibleIntIfPresent(forKey: .deckLimit) ?? 1
        sourceSet = container.decodeFlexibleStringIfPresent(forKey: .sourceSet) ?? ""
    }

    private static func splitIds(_ raw: String?) -> [String] {
        (raw ?? "")
            .split(separator: ";")
            .map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
            .filter { !$0.isEmpty }
    }
}

enum GwentStaticCatalog {
    private struct StaticCard {
        let faction: String
        let row: String
        let type: String
        let strength: Int
        let effect: String
        let rarity: String
        let abilityTags: String
        let nameGroup: String
        let bondGroup: String
        let musterGroup: String
        let displayName: String
        let deckLimit: Int
        let sourceSet: String
    }

    private static let cards: [String: StaticCard] = [
        "gwent_leader_foltest_king": StaticCard(faction: "northern", row: "leader", type: "leader", strength: 0, effect: "leader_foltest_fog", rarity: "Leader", abilityTags: "", nameGroup: "gwent_leader_foltest_king", bondGroup: "", musterGroup: "", displayName: "Фольтест: Король Темерии", deckLimit: 1, sourceSet: "witcher3_base"),
        "gwent_leader_wolf": StaticCard(faction: "northern", row: "leader", type: "leader", strength: 0, effect: "leader_foltest_clear_weather", rarity: "Leader", abilityTags: "", nameGroup: "gwent_leader_wolf", bondGroup: "", musterGroup: "", displayName: "Фольтест: Предводитель Севера", deckLimit: 1, sourceSet: "witcher3_base"),
        "gwent_leader_foltest_siegemaster": StaticCard(faction: "northern", row: "leader", type: "leader", strength: 0, effect: "leader_foltest_siege_horn", rarity: "Leader", abilityTags: "", nameGroup: "gwent_leader_foltest_siegemaster", bondGroup: "", musterGroup: "", displayName: "Фольтест: Мастер осады", deckLimit: 1, sourceSet: "witcher3_base"),
        "gwent_leader_foltest_steel_forged": StaticCard(faction: "northern", row: "leader", type: "leader", strength: 0, effect: "leader_foltest_siege_scorch", rarity: "Leader", abilityTags: "", nameGroup: "gwent_leader_foltest_steel_forged", bondGroup: "", musterGroup: "", displayName: "Фольтест: Закаленный сталью", deckLimit: 1, sourceSet: "witcher3_base"),
        "gwent_leader_emhyr_emperor": StaticCard(faction: "nilfgaard", row: "leader", type: "leader", strength: 0, effect: "leader_emhyr_spy_hand", rarity: "Leader", abilityTags: "", nameGroup: "gwent_leader_emhyr_emperor", bondGroup: "", musterGroup: "", displayName: "Эмгыр вар Эмрейс: Император Нильфгаарда", deckLimit: 1, sourceSet: "witcher3_base"),
        "gwent_leader_emhyr_imperial": StaticCard(faction: "nilfgaard", row: "leader", type: "leader", strength: 0, effect: "leader_emhyr_rain", rarity: "Leader", abilityTags: "", nameGroup: "gwent_leader_emhyr_imperial", bondGroup: "", musterGroup: "", displayName: "Эмгыр вар Эмрейс: Его императорское величество", deckLimit: 1, sourceSet: "witcher3_base"),
        "gwent_leader_nilfgaard": StaticCard(faction: "nilfgaard", row: "leader", type: "leader", strength: 0, effect: "leader_emhyr_graveyard_theft", rarity: "Leader", abilityTags: "", nameGroup: "gwent_leader_nilfgaard", bondGroup: "", musterGroup: "", displayName: "Эмгыр вар Эмрейс: Неумолимый", deckLimit: 1, sourceSet: "witcher3_base"),
        "gwent_leader_emhyr_white_flame": StaticCard(faction: "nilfgaard", row: "leader", type: "leader", strength: 0, effect: "leader_emhyr_cancel_leader", rarity: "Leader", abilityTags: "", nameGroup: "gwent_leader_emhyr_white_flame", bondGroup: "", musterGroup: "", displayName: "Эмгыр вар Эмрейс: Белое Пламя", deckLimit: 1, sourceSet: "witcher3_base"),
        "gwent_leader_francesca_daisy": StaticCard(faction: "scoiatael", row: "leader", type: "leader", strength: 0, effect: "leader_francesca_draw", rarity: "Leader", abilityTags: "", nameGroup: "gwent_leader_francesca_daisy", bondGroup: "", musterGroup: "", displayName: "Францеска Финдабаир: Маргаритка из Долин", deckLimit: 1, sourceSet: "witcher3_base"),
        "gwent_leader_francesca_pureblood": StaticCard(faction: "scoiatael", row: "leader", type: "leader", strength: 0, effect: "leader_francesca_frost", rarity: "Leader", abilityTags: "", nameGroup: "gwent_leader_francesca_pureblood", bondGroup: "", musterGroup: "", displayName: "Францеска Финдабаир: Чистокровная эльфка", deckLimit: 1, sourceSet: "witcher3_base"),
        "gwent_leader_francesca_queen": StaticCard(faction: "scoiatael", row: "leader", type: "leader", strength: 0, effect: "leader_francesca_melee_scorch", rarity: "Leader", abilityTags: "", nameGroup: "gwent_leader_francesca_queen", bondGroup: "", musterGroup: "", displayName: "Францеска Финдабаир: Королева Дол Блатанны", deckLimit: 1, sourceSet: "witcher3_base"),
        "gwent_leader_scoiatael": StaticCard(faction: "scoiatael", row: "leader", type: "leader", strength: 0, effect: "leader_francesca_ranged_horn", rarity: "Leader", abilityTags: "", nameGroup: "gwent_leader_scoiatael", bondGroup: "", musterGroup: "", displayName: "Францеска Финдабаир: Прекрасная", deckLimit: 1, sourceSet: "witcher3_base"),
        "gwent_leader_eredin_bringer": StaticCard(faction: "monsters", row: "leader", type: "leader", strength: 0, effect: "leader_eredin_graveyard_return", rarity: "Leader", abilityTags: "", nameGroup: "gwent_leader_eredin_bringer", bondGroup: "", musterGroup: "", displayName: "Эредин: Несущий смерть", deckLimit: 1, sourceSet: "witcher3_base"),
        "gwent_leader_monsters": StaticCard(faction: "monsters", row: "leader", type: "leader", strength: 0, effect: "leader_eredin_melee_horn", rarity: "Leader", abilityTags: "", nameGroup: "gwent_leader_monsters", bondGroup: "", musterGroup: "", displayName: "Эредин: Командир Красных Всадников", deckLimit: 1, sourceSet: "witcher3_base"),
        "gwent_leader_eredin_destroyer": StaticCard(faction: "monsters", row: "leader", type: "leader", strength: 0, effect: "leader_eredin_discard_draw", rarity: "Leader", abilityTags: "", nameGroup: "gwent_leader_eredin_destroyer", bondGroup: "", musterGroup: "", displayName: "Эредин: Разрушитель миров", deckLimit: 1, sourceSet: "witcher3_base"),
        "gwent_leader_eredin_king": StaticCard(faction: "monsters", row: "leader", type: "leader", strength: 0, effect: "leader_eredin_weather", rarity: "Leader", abilityTags: "", nameGroup: "gwent_leader_eredin_king", bondGroup: "", musterGroup: "", displayName: "Эредин: Король Дикой Охоты", deckLimit: 1, sourceSet: "witcher3_base"),
        "gwent_unit_13": StaticCard(faction: "northern", row: "siege", type: "unit", strength: 6, effect: "none", rarity: "Common", abilityTags: "", nameGroup: "gwent_unit_13", bondGroup: "", musterGroup: "", displayName: "Баллиста", deckLimit: 1, sourceSet: "witcher3_base"),
        "gwent_unit_03": StaticCard(faction: "northern", row: "melee", type: "unit", strength: 4, effect: "tight_bond", rarity: "Common", abilityTags: "", nameGroup: "blue_stripes_commando", bondGroup: "blue_stripes_commando", musterGroup: "", displayName: "Боец Синих Полос", deckLimit: 1, sourceSet: "witcher3_base"),
        "nr_blue_stripes_commando_2": StaticCard(faction: "northern", row: "melee", type: "unit", strength: 4, effect: "tight_bond", rarity: "Common", abilityTags: "", nameGroup: "blue_stripes_commando", bondGroup: "blue_stripes_commando", musterGroup: "", displayName: "Боец Синих Полос", deckLimit: 1, sourceSet: "witcher3_base"),
        "nr_blue_stripes_commando_3": StaticCard(faction: "northern", row: "melee", type: "unit", strength: 4, effect: "tight_bond", rarity: "Common", abilityTags: "", nameGroup: "blue_stripes_commando", bondGroup: "blue_stripes_commando", musterGroup: "", displayName: "Боец Синих Полос", deckLimit: 1, sourceSet: "witcher3_base"),
        "gwent_unit_16": StaticCard(faction: "northern", row: "siege", type: "unit", strength: 8, effect: "tight_bond", rarity: "Common", abilityTags: "", nameGroup: "catapult", bondGroup: "catapult", musterGroup: "", displayName: "Катапульта", deckLimit: 1, sourceSet: "witcher3_base"),
        "nr_catapult_2": StaticCard(faction: "northern", row: "siege", type: "unit", strength: 8, effect: "tight_bond", rarity: "Common", abilityTags: "", nameGroup: "catapult", bondGroup: "catapult", musterGroup: "", displayName: "Катапульта", deckLimit: 1, sourceSet: "witcher3_base"),
        "gwent_unit_12": StaticCard(faction: "northern", row: "ranged", type: "unit", strength: 5, effect: "tight_bond", rarity: "Common", abilityTags: "", nameGroup: "crinfrid_reavers_dragon_hunter", bondGroup: "crinfrid_reavers_dragon_hunter", musterGroup: "", displayName: "Охотник на драконов из Кринфрида", deckLimit: 1, sourceSet: "witcher3_base"),
        "nr_crinfrid_reavers_dragon_hunter_2": StaticCard(faction: "northern", row: "ranged", type: "unit", strength: 5, effect: "tight_bond", rarity: "Common", abilityTags: "", nameGroup: "crinfrid_reavers_dragon_hunter", bondGroup: "crinfrid_reavers_dragon_hunter", musterGroup: "", displayName: "Охотник на драконов из Кринфрида", deckLimit: 1, sourceSet: "witcher3_base"),
        "nr_crinfrid_reavers_dragon_hunter_3": StaticCard(faction: "northern", row: "ranged", type: "unit", strength: 5, effect: "tight_bond", rarity: "Common", abilityTags: "", nameGroup: "crinfrid_reavers_dragon_hunter", bondGroup: "crinfrid_reavers_dragon_hunter", musterGroup: "", displayName: "Охотник на драконов из Кринфрида", deckLimit: 1, sourceSet: "witcher3_base"),
        "gwent_unit_10": StaticCard(faction: "northern", row: "ranged", type: "unit", strength: 6, effect: "none", rarity: "Common", abilityTags: "", nameGroup: "gwent_unit_10", bondGroup: "", musterGroup: "", displayName: "Детмольд", deckLimit: 1, sourceSet: "witcher3_base"),
        "gwent_unit_09": StaticCard(faction: "northern", row: "siege", type: "unit", strength: 5, effect: "medic", rarity: "Uncommon", abilityTags: "", nameGroup: "gwent_unit_09", bondGroup: "", musterGroup: "", displayName: "Лекарь Бурой Хоругви", deckLimit: 1, sourceSet: "witcher3_base"),
        "nr_esterad_thyssen": StaticCard(faction: "northern", row: "melee", type: "unit", strength: 10, effect: "hero", rarity: "Hero", abilityTags: "", nameGroup: "nr_esterad_thyssen", bondGroup: "", musterGroup: "", displayName: "Эстерад Тиссен", deckLimit: 1, sourceSet: "witcher3_base"),
        "nr_john_natalis": StaticCard(faction: "northern", row: "melee", type: "unit", strength: 10, effect: "hero", rarity: "Hero", abilityTags: "", nameGroup: "nr_john_natalis", bondGroup: "", musterGroup: "", displayName: "Ян Наталис", deckLimit: 1, sourceSet: "witcher3_base"),
        "gwent_unit_05": StaticCard(faction: "northern", row: "siege", type: "unit", strength: 1, effect: "morale", rarity: "Common", abilityTags: "", nameGroup: "nr_kaedweni_siege_expert", bondGroup: "", musterGroup: "", displayName: "Каэдвенский осадный мастер", deckLimit: 1, sourceSet: "witcher3_base"),
        "nr_kaedweni_siege_expert_2": StaticCard(faction: "northern", row: "siege", type: "unit", strength: 1, effect: "morale", rarity: "Common", abilityTags: "", nameGroup: "nr_kaedweni_siege_expert", bondGroup: "", musterGroup: "", displayName: "Каэдвенский осадный мастер", deckLimit: 1, sourceSet: "witcher3_base"),
        "nr_kaedweni_siege_expert_3": StaticCard(faction: "northern", row: "siege", type: "unit", strength: 1, effect: "morale", rarity: "Common", abilityTags: "", nameGroup: "nr_kaedweni_siege_expert", bondGroup: "", musterGroup: "", displayName: "Каэдвенский осадный мастер", deckLimit: 1, sourceSet: "witcher3_base"),
        "gwent_unit_07": StaticCard(faction: "northern", row: "ranged", type: "unit", strength: 5, effect: "none", rarity: "Common", abilityTags: "", nameGroup: "gwent_unit_07", bondGroup: "", musterGroup: "", displayName: "Кейра Мец", deckLimit: 1, sourceSet: "witcher3_base"),
        "nr_philippa_eilhart": StaticCard(faction: "northern", row: "ranged", type: "unit", strength: 10, effect: "hero", rarity: "Hero", abilityTags: "", nameGroup: "nr_philippa_eilhart", bondGroup: "", musterGroup: "", displayName: "Филиппа Эйльхарт", deckLimit: 1, sourceSet: "witcher3_base"),
        "nr_poor_fucking_infantry_1": StaticCard(faction: "northern", row: "melee", type: "unit", strength: 1, effect: "tight_bond", rarity: "Common", abilityTags: "", nameGroup: "poor_fucking_infantry", bondGroup: "poor_fucking_infantry", musterGroup: "", displayName: "Проклятая пехота", deckLimit: 1, sourceSet: "witcher3_base"),
        "nr_poor_fucking_infantry_2": StaticCard(faction: "northern", row: "melee", type: "unit", strength: 1, effect: "tight_bond", rarity: "Common", abilityTags: "", nameGroup: "poor_fucking_infantry", bondGroup: "poor_fucking_infantry", musterGroup: "", displayName: "Проклятая пехота", deckLimit: 1, sourceSet: "witcher3_base"),
        "nr_poor_fucking_infantry_3": StaticCard(faction: "northern", row: "melee", type: "unit", strength: 1, effect: "tight_bond", rarity: "Common", abilityTags: "", nameGroup: "poor_fucking_infantry", bondGroup: "poor_fucking_infantry", musterGroup: "", displayName: "Проклятая пехота", deckLimit: 1, sourceSet: "witcher3_base"),
        "gwent_unit_06": StaticCard(faction: "northern", row: "melee", type: "unit", strength: 5, effect: "spy", rarity: "Uncommon", abilityTags: "", nameGroup: "gwent_unit_06", bondGroup: "", musterGroup: "", displayName: "Принц Стеннис", deckLimit: 1, sourceSet: "witcher3_base"),
        "gwent_unit_01": StaticCard(faction: "northern", row: "melee", type: "unit", strength: 1, effect: "none", rarity: "Common", abilityTags: "", nameGroup: "gwent_unit_01", bondGroup: "", musterGroup: "", displayName: "Реданский пехотинец", deckLimit: 1, sourceSet: "witcher3_base"),
        "gwent_unit_08": StaticCard(faction: "northern", row: "ranged", type: "unit", strength: 4, effect: "none", rarity: "Common", abilityTags: "", nameGroup: "gwent_unit_08", bondGroup: "", musterGroup: "", displayName: "Сабрина Глевиссиг", deckLimit: 1, sourceSet: "witcher3_base"),
        "nr_sheldon_skaggs": StaticCard(faction: "northern", row: "ranged", type: "unit", strength: 4, effect: "none", rarity: "Common", abilityTags: "", nameGroup: "nr_sheldon_skaggs", bondGroup: "", musterGroup: "", displayName: "Шелдон Скаггс", deckLimit: 1, sourceSet: "witcher3_base"),
        "gwent_unit_11": StaticCard(faction: "northern", row: "siege", type: "unit", strength: 6, effect: "none", rarity: "Common", abilityTags: "", nameGroup: "gwent_unit_11", bondGroup: "", musterGroup: "", displayName: "Осадная башня", deckLimit: 1, sourceSet: "witcher3_base"),
        "gwent_unit_02": StaticCard(faction: "northern", row: "melee", type: "unit", strength: 5, effect: "none", rarity: "Common", abilityTags: "", nameGroup: "gwent_unit_02", bondGroup: "", musterGroup: "", displayName: "Зигфрид из Денесле", deckLimit: 1, sourceSet: "witcher3_base"),
        "nr_sigismund_dijkstra": StaticCard(faction: "northern", row: "melee", type: "unit", strength: 4, effect: "spy", rarity: "Uncommon", abilityTags: "", nameGroup: "nr_sigismund_dijkstra", bondGroup: "", musterGroup: "", displayName: "Сигизмунд Дийкстра", deckLimit: 1, sourceSet: "witcher3_base"),
        "nr_sile_de_tansarville": StaticCard(faction: "northern", row: "ranged", type: "unit", strength: 5, effect: "none", rarity: "Common", abilityTags: "", nameGroup: "nr_sile_de_tansarville", bondGroup: "", musterGroup: "", displayName: "Шеала де Тансервилль", deckLimit: 1, sourceSet: "witcher3_base"),
        "nr_thaler": StaticCard(faction: "northern", row: "siege", type: "unit", strength: 1, effect: "spy", rarity: "Uncommon", abilityTags: "", nameGroup: "nr_thaler", bondGroup: "", musterGroup: "", displayName: "Талер", deckLimit: 1, sourceSet: "witcher3_base"),
        "gwent_unit_14": StaticCard(faction: "northern", row: "siege", type: "unit", strength: 6, effect: "none", rarity: "Common", abilityTags: "", nameGroup: "nr_trebuchet", bondGroup: "", musterGroup: "", displayName: "Требушет", deckLimit: 1, sourceSet: "witcher3_base"),
        "nr_trebuchet_2": StaticCard(faction: "northern", row: "siege", type: "unit", strength: 6, effect: "none", rarity: "Common", abilityTags: "", nameGroup: "nr_trebuchet", bondGroup: "", musterGroup: "", displayName: "Требушет", deckLimit: 1, sourceSet: "witcher3_base"),
        "nr_vernon_roche": StaticCard(faction: "northern", row: "melee", type: "unit", strength: 10, effect: "hero", rarity: "Hero", abilityTags: "", nameGroup: "nr_vernon_roche", bondGroup: "", musterGroup: "", displayName: "Вернон Роше", deckLimit: 1, sourceSet: "witcher3_base"),
        "nr_ves": StaticCard(faction: "northern", row: "melee", type: "unit", strength: 5, effect: "none", rarity: "Common", abilityTags: "", nameGroup: "nr_ves", bondGroup: "", musterGroup: "", displayName: "Вес", deckLimit: 1, sourceSet: "witcher3_base"),
        "nr_yarpen_zigrin": StaticCard(faction: "northern", row: "melee", type: "unit", strength: 2, effect: "none", rarity: "Common", abilityTags: "", nameGroup: "nr_yarpen_zigrin", bondGroup: "", musterGroup: "", displayName: "Ярпен Зигрин", deckLimit: 1, sourceSet: "witcher3_base"),
        "ng_albrich": StaticCard(faction: "nilfgaard", row: "ranged", type: "unit", strength: 2, effect: "none", rarity: "Common", abilityTags: "", nameGroup: "ng_albrich", bondGroup: "", musterGroup: "", displayName: "Альбрых", deckLimit: 1, sourceSet: "witcher3_base"),
        "ng_assire_var_anahid": StaticCard(faction: "nilfgaard", row: "ranged", type: "unit", strength: 6, effect: "none", rarity: "Common", abilityTags: "", nameGroup: "ng_assire_var_anahid", bondGroup: "", musterGroup: "", displayName: "Ассирэ вар Анагыд", deckLimit: 1, sourceSet: "witcher3_base"),
        "ng_black_infantry_archer_1": StaticCard(faction: "nilfgaard", row: "ranged", type: "unit", strength: 10, effect: "none", rarity: "Common", abilityTags: "", nameGroup: "ng_black_infantry_archer", bondGroup: "", musterGroup: "", displayName: "Лучник Черной пехоты", deckLimit: 1, sourceSet: "witcher3_base"),
        "ng_black_infantry_archer_2": StaticCard(faction: "nilfgaard", row: "ranged", type: "unit", strength: 10, effect: "none", rarity: "Common", abilityTags: "", nameGroup: "ng_black_infantry_archer", bondGroup: "", musterGroup: "", displayName: "Лучник Черной пехоты", deckLimit: 1, sourceSet: "witcher3_base"),
        "ng_cahir": StaticCard(faction: "nilfgaard", row: "melee", type: "unit", strength: 6, effect: "none", rarity: "Common", abilityTags: "", nameGroup: "ng_cahir", bondGroup: "", musterGroup: "", displayName: "Кагыр Маур Дыффин аэп Кеаллах", deckLimit: 1, sourceSet: "witcher3_base"),
        "ng_cynthia": StaticCard(faction: "nilfgaard", row: "ranged", type: "unit", strength: 4, effect: "none", rarity: "Common", abilityTags: "", nameGroup: "ng_cynthia", bondGroup: "", musterGroup: "", displayName: "Цинтия", deckLimit: 1, sourceSet: "witcher3_base"),
        "ng_etolian_auxiliary_archers_1": StaticCard(faction: "nilfgaard", row: "ranged", type: "unit", strength: 1, effect: "medic", rarity: "Common", abilityTags: "", nameGroup: "ng_etolian_auxiliary_archers", bondGroup: "", musterGroup: "", displayName: "Этолийские вспомогательные лучники", deckLimit: 1, sourceSet: "witcher3_base"),
        "ng_etolian_auxiliary_archers_2": StaticCard(faction: "nilfgaard", row: "ranged", type: "unit", strength: 1, effect: "medic", rarity: "Common", abilityTags: "", nameGroup: "ng_etolian_auxiliary_archers", bondGroup: "", musterGroup: "", displayName: "Этолийские вспомогательные лучники", deckLimit: 1, sourceSet: "witcher3_base"),
        "ng_fringilla_vigo": StaticCard(faction: "nilfgaard", row: "ranged", type: "unit", strength: 6, effect: "none", rarity: "Common", abilityTags: "", nameGroup: "ng_fringilla_vigo", bondGroup: "", musterGroup: "", displayName: "Фрингилья Виго", deckLimit: 1, sourceSet: "witcher3_base"),
        "ng_heavy_zerrikanian_fire_scorpion": StaticCard(faction: "nilfgaard", row: "siege", type: "unit", strength: 10, effect: "none", rarity: "Common", abilityTags: "", nameGroup: "ng_heavy_zerrikanian_fire_scorpion", bondGroup: "", musterGroup: "", displayName: "Тяжелый зэрриканский огненный скорпион", deckLimit: 1, sourceSet: "witcher3_base"),
        "ng_impera_brigade_guard_1": StaticCard(faction: "nilfgaard", row: "melee", type: "unit", strength: 3, effect: "tight_bond", rarity: "Common", abilityTags: "", nameGroup: "impera_brigade_guard", bondGroup: "impera_brigade_guard", musterGroup: "", displayName: "Гвардеец бригады Импера", deckLimit: 1, sourceSet: "witcher3_base"),
        "ng_impera_brigade_guard_2": StaticCard(faction: "nilfgaard", row: "melee", type: "unit", strength: 3, effect: "tight_bond", rarity: "Common", abilityTags: "", nameGroup: "impera_brigade_guard", bondGroup: "impera_brigade_guard", musterGroup: "", displayName: "Гвардеец бригады Импера", deckLimit: 1, sourceSet: "witcher3_base"),
        "ng_impera_brigade_guard_3": StaticCard(faction: "nilfgaard", row: "melee", type: "unit", strength: 3, effect: "tight_bond", rarity: "Common", abilityTags: "", nameGroup: "impera_brigade_guard", bondGroup: "impera_brigade_guard", musterGroup: "", displayName: "Гвардеец бригады Импера", deckLimit: 1, sourceSet: "witcher3_base"),
        "ng_impera_brigade_guard_4": StaticCard(faction: "nilfgaard", row: "melee", type: "unit", strength: 3, effect: "tight_bond", rarity: "Common", abilityTags: "", nameGroup: "impera_brigade_guard", bondGroup: "impera_brigade_guard", musterGroup: "", displayName: "Гвардеец бригады Импера", deckLimit: 1, sourceSet: "witcher3_base"),
        "ng_letho_of_gulet": StaticCard(faction: "nilfgaard", row: "melee", type: "unit", strength: 10, effect: "hero", rarity: "Hero", abilityTags: "", nameGroup: "ng_letho_of_gulet", bondGroup: "", musterGroup: "", displayName: "Лето из Гулеты", deckLimit: 1, sourceSet: "witcher3_base"),
        "ng_menno_coehoorn": StaticCard(faction: "nilfgaard", row: "melee", type: "unit", strength: 10, effect: "hero", rarity: "Hero", abilityTags: "medic", nameGroup: "ng_menno_coehoorn", bondGroup: "", musterGroup: "", displayName: "Менно Коегоорн", deckLimit: 1, sourceSet: "witcher3_base"),
        "ng_morteisen": StaticCard(faction: "nilfgaard", row: "melee", type: "unit", strength: 3, effect: "none", rarity: "Common", abilityTags: "", nameGroup: "ng_morteisen", bondGroup: "", musterGroup: "", displayName: "Мортейзен", deckLimit: 1, sourceSet: "witcher3_base"),
        "ng_morvran_voorhis": StaticCard(faction: "nilfgaard", row: "siege", type: "unit", strength: 10, effect: "hero", rarity: "Hero", abilityTags: "", nameGroup: "ng_morvran_voorhis", bondGroup: "", musterGroup: "", displayName: "Морвран Воорхис", deckLimit: 1, sourceSet: "witcher3_base"),
        "ng_nausicaa_cavalry_rider_1": StaticCard(faction: "nilfgaard", row: "melee", type: "unit", strength: 2, effect: "tight_bond", rarity: "Common", abilityTags: "", nameGroup: "nausicaa_cavalry_rider", bondGroup: "nausicaa_cavalry_rider", musterGroup: "", displayName: "Всадник кавалерии Наузикаа", deckLimit: 1, sourceSet: "witcher3_base"),
        "ng_nausicaa_cavalry_rider_2": StaticCard(faction: "nilfgaard", row: "melee", type: "unit", strength: 2, effect: "tight_bond", rarity: "Common", abilityTags: "", nameGroup: "nausicaa_cavalry_rider", bondGroup: "nausicaa_cavalry_rider", musterGroup: "", displayName: "Всадник кавалерии Наузикаа", deckLimit: 1, sourceSet: "witcher3_base"),
        "ng_nausicaa_cavalry_rider_3": StaticCard(faction: "nilfgaard", row: "melee", type: "unit", strength: 2, effect: "tight_bond", rarity: "Common", abilityTags: "", nameGroup: "nausicaa_cavalry_rider", bondGroup: "nausicaa_cavalry_rider", musterGroup: "", displayName: "Всадник кавалерии Наузикаа", deckLimit: 1, sourceSet: "witcher3_base"),
        "ng_puttkammer": StaticCard(faction: "nilfgaard", row: "ranged", type: "unit", strength: 3, effect: "none", rarity: "Common", abilityTags: "", nameGroup: "ng_puttkammer", bondGroup: "", musterGroup: "", displayName: "Путткамер", deckLimit: 1, sourceSet: "witcher3_base"),
        "ng_rainfarn": StaticCard(faction: "nilfgaard", row: "melee", type: "unit", strength: 4, effect: "none", rarity: "Common", abilityTags: "", nameGroup: "ng_rainfarn", bondGroup: "", musterGroup: "", displayName: "Райнфарн", deckLimit: 1, sourceSet: "witcher3_base"),
        "ng_renuald_aep_matsen": StaticCard(faction: "nilfgaard", row: "ranged", type: "unit", strength: 5, effect: "none", rarity: "Common", abilityTags: "", nameGroup: "ng_renuald_aep_matsen", bondGroup: "", musterGroup: "", displayName: "Ренуальд аэп Матсен", deckLimit: 1, sourceSet: "witcher3_base"),
        "ng_rotten_mangonel": StaticCard(faction: "nilfgaard", row: "siege", type: "unit", strength: 3, effect: "none", rarity: "Common", abilityTags: "", nameGroup: "ng_rotten_mangonel", bondGroup: "", musterGroup: "", displayName: "Гнилая мангонель", deckLimit: 1, sourceSet: "witcher3_base"),
        "gwent_unit_21": StaticCard(faction: "nilfgaard", row: "melee", type: "unit", strength: 7, effect: "spy", rarity: "Uncommon", abilityTags: "", nameGroup: "gwent_unit_21", bondGroup: "", musterGroup: "", displayName: "Шилярд Фиц-Эстерлен", deckLimit: 1, sourceSet: "witcher3_base"),
        "ng_siege_engineer_1": StaticCard(faction: "nilfgaard", row: "siege", type: "unit", strength: 6, effect: "none", rarity: "Common", abilityTags: "", nameGroup: "ng_siege_engineer", bondGroup: "", musterGroup: "", displayName: "Осадный инженер", deckLimit: 1, sourceSet: "witcher3_base"),
        "ng_siege_engineer_2": StaticCard(faction: "nilfgaard", row: "siege", type: "unit", strength: 6, effect: "none", rarity: "Common", abilityTags: "", nameGroup: "ng_siege_engineer", bondGroup: "", musterGroup: "", displayName: "Осадный инженер", deckLimit: 1, sourceSet: "witcher3_base"),
        "gwent_unit_22": StaticCard(faction: "nilfgaard", row: "siege", type: "unit", strength: 0, effect: "medic", rarity: "Uncommon", abilityTags: "", nameGroup: "gwent_unit_22", bondGroup: "", musterGroup: "", displayName: "Осадный техник", deckLimit: 1, sourceSet: "witcher3_base"),
        "ng_stefan_skellen": StaticCard(faction: "nilfgaard", row: "melee", type: "unit", strength: 9, effect: "spy", rarity: "Uncommon", abilityTags: "", nameGroup: "ng_stefan_skellen", bondGroup: "", musterGroup: "", displayName: "Стефан Скеллен", deckLimit: 1, sourceSet: "witcher3_base"),
        "ng_sweers": StaticCard(faction: "nilfgaard", row: "ranged", type: "unit", strength: 2, effect: "none", rarity: "Common", abilityTags: "", nameGroup: "ng_sweers", bondGroup: "", musterGroup: "", displayName: "Свирс", deckLimit: 1, sourceSet: "witcher3_base"),
        "ng_tibor_eggebracht": StaticCard(faction: "nilfgaard", row: "ranged", type: "unit", strength: 10, effect: "hero", rarity: "Hero", abilityTags: "", nameGroup: "ng_tibor_eggebracht", bondGroup: "", musterGroup: "", displayName: "Тибор Эггебрахт", deckLimit: 1, sourceSet: "witcher3_base"),
        "ng_vanhemar": StaticCard(faction: "nilfgaard", row: "ranged", type: "unit", strength: 4, effect: "none", rarity: "Common", abilityTags: "", nameGroup: "ng_vanhemar", bondGroup: "", musterGroup: "", displayName: "Вангемар", deckLimit: 1, sourceSet: "witcher3_base"),
        "ng_vattier_de_rideaux": StaticCard(faction: "nilfgaard", row: "melee", type: "unit", strength: 4, effect: "spy", rarity: "Uncommon", abilityTags: "", nameGroup: "ng_vattier_de_rideaux", bondGroup: "", musterGroup: "", displayName: "Ватье де Ридо", deckLimit: 1, sourceSet: "witcher3_base"),
        "ng_vreemde": StaticCard(faction: "nilfgaard", row: "melee", type: "unit", strength: 2, effect: "none", rarity: "Common", abilityTags: "", nameGroup: "ng_vreemde", bondGroup: "", musterGroup: "", displayName: "Вреемде", deckLimit: 1, sourceSet: "witcher3_base"),
        "ng_young_emissary_1": StaticCard(faction: "nilfgaard", row: "melee", type: "unit", strength: 5, effect: "tight_bond", rarity: "Common", abilityTags: "", nameGroup: "young_emissary", bondGroup: "young_emissary", musterGroup: "", displayName: "Молодой посол", deckLimit: 1, sourceSet: "witcher3_base"),
        "ng_young_emissary_2": StaticCard(faction: "nilfgaard", row: "melee", type: "unit", strength: 5, effect: "tight_bond", rarity: "Common", abilityTags: "", nameGroup: "young_emissary", bondGroup: "young_emissary", musterGroup: "", displayName: "Молодой посол", deckLimit: 1, sourceSet: "witcher3_base"),
        "ng_zerrikanian_fire_scorpion": StaticCard(faction: "nilfgaard", row: "siege", type: "unit", strength: 5, effect: "none", rarity: "Common", abilityTags: "", nameGroup: "ng_zerrikanian_fire_scorpion", bondGroup: "", musterGroup: "", displayName: "Зэрриканский огненный скорпион", deckLimit: 1, sourceSet: "witcher3_base"),
        "gwent_unit_17": StaticCard(faction: "scoiatael", row: "melee", type: "unit", strength: 6, effect: "agile", rarity: "Common", abilityTags: "", nameGroup: "gwent_unit_17", bondGroup: "", musterGroup: "", displayName: "Барклай Эльс", deckLimit: 1, sourceSet: "witcher3_base"),
        "sc_ciaran": StaticCard(faction: "scoiatael", row: "melee", type: "unit", strength: 3, effect: "agile", rarity: "Common", abilityTags: "", nameGroup: "sc_ciaran", bondGroup: "", musterGroup: "", displayName: "Киаран аэп Эасниллен", deckLimit: 1, sourceSet: "witcher3_base"),
        "sc_dennis_cranmer": StaticCard(faction: "scoiatael", row: "melee", type: "unit", strength: 6, effect: "none", rarity: "Common", abilityTags: "", nameGroup: "sc_dennis_cranmer", bondGroup: "", musterGroup: "", displayName: "Деннис Кранмер", deckLimit: 1, sourceSet: "witcher3_base"),
        "sc_dol_blathanna_archer": StaticCard(faction: "scoiatael", row: "ranged", type: "unit", strength: 4, effect: "none", rarity: "Common", abilityTags: "", nameGroup: "sc_dol_blathanna_archer", bondGroup: "", musterGroup: "", displayName: "Лучник Дол Блатанны", deckLimit: 1, sourceSet: "witcher3_base"),
        "sc_dol_blathanna_scout_1": StaticCard(faction: "scoiatael", row: "melee", type: "unit", strength: 6, effect: "agile", rarity: "Common", abilityTags: "", nameGroup: "sc_dol_blathanna_scout", bondGroup: "", musterGroup: "", displayName: "Разведчик Дол Блатанны", deckLimit: 1, sourceSet: "witcher3_base"),
        "sc_dol_blathanna_scout_2": StaticCard(faction: "scoiatael", row: "melee", type: "unit", strength: 6, effect: "agile", rarity: "Common", abilityTags: "", nameGroup: "sc_dol_blathanna_scout", bondGroup: "", musterGroup: "", displayName: "Разведчик Дол Блатанны", deckLimit: 1, sourceSet: "witcher3_base"),
        "sc_dol_blathanna_scout_3": StaticCard(faction: "scoiatael", row: "melee", type: "unit", strength: 6, effect: "agile", rarity: "Common", abilityTags: "", nameGroup: "sc_dol_blathanna_scout", bondGroup: "", musterGroup: "", displayName: "Разведчик Дол Блатанны", deckLimit: 1, sourceSet: "witcher3_base"),
        "gwent_unit_18": StaticCard(faction: "scoiatael", row: "melee", type: "unit", strength: 3, effect: "muster", rarity: "Common", abilityTags: "", nameGroup: "sc_dwarven_skirmisher", bondGroup: "", musterGroup: "dwarven_skirmisher", displayName: "Краснолюд-застрельщик", deckLimit: 1, sourceSet: "witcher3_base"),
        "sc_dwarven_skirmisher_2": StaticCard(faction: "scoiatael", row: "melee", type: "unit", strength: 3, effect: "muster", rarity: "Common", abilityTags: "", nameGroup: "sc_dwarven_skirmisher", bondGroup: "", musterGroup: "dwarven_skirmisher", displayName: "Краснолюд-застрельщик", deckLimit: 1, sourceSet: "witcher3_base"),
        "sc_dwarven_skirmisher_3": StaticCard(faction: "scoiatael", row: "melee", type: "unit", strength: 3, effect: "muster", rarity: "Common", abilityTags: "", nameGroup: "sc_dwarven_skirmisher", bondGroup: "", musterGroup: "dwarven_skirmisher", displayName: "Краснолюд-застрельщик", deckLimit: 1, sourceSet: "witcher3_base"),
        "sc_eithne": StaticCard(faction: "scoiatael", row: "ranged", type: "unit", strength: 10, effect: "hero", rarity: "Hero", abilityTags: "", nameGroup: "sc_eithne", bondGroup: "", musterGroup: "", displayName: "Эитнэ", deckLimit: 1, sourceSet: "witcher3_base"),
        "sc_elven_skirmisher_1": StaticCard(faction: "scoiatael", row: "ranged", type: "unit", strength: 2, effect: "muster", rarity: "Common", abilityTags: "", nameGroup: "sc_elven_skirmisher", bondGroup: "", musterGroup: "elven_skirmisher", displayName: "Эльф-застрельщик", deckLimit: 1, sourceSet: "witcher3_base"),
        "sc_elven_skirmisher_2": StaticCard(faction: "scoiatael", row: "ranged", type: "unit", strength: 2, effect: "muster", rarity: "Common", abilityTags: "", nameGroup: "sc_elven_skirmisher", bondGroup: "", musterGroup: "elven_skirmisher", displayName: "Эльф-застрельщик", deckLimit: 1, sourceSet: "witcher3_base"),
        "sc_elven_skirmisher_3": StaticCard(faction: "scoiatael", row: "ranged", type: "unit", strength: 2, effect: "muster", rarity: "Common", abilityTags: "", nameGroup: "sc_elven_skirmisher", bondGroup: "", musterGroup: "elven_skirmisher", displayName: "Эльф-застрельщик", deckLimit: 1, sourceSet: "witcher3_base"),
        "sc_filavandrel": StaticCard(faction: "scoiatael", row: "melee", type: "unit", strength: 6, effect: "agile", rarity: "Common", abilityTags: "", nameGroup: "sc_filavandrel", bondGroup: "", musterGroup: "", displayName: "Филавандрель аэн Фидаиль", deckLimit: 1, sourceSet: "witcher3_base"),
        "sc_havekar_healer_1": StaticCard(faction: "scoiatael", row: "ranged", type: "unit", strength: 0, effect: "medic", rarity: "Common", abilityTags: "", nameGroup: "sc_havekar_healer", bondGroup: "", musterGroup: "", displayName: "Гавенкар-лекарь", deckLimit: 1, sourceSet: "witcher3_base"),
        "sc_havekar_healer_2": StaticCard(faction: "scoiatael", row: "ranged", type: "unit", strength: 0, effect: "medic", rarity: "Common", abilityTags: "", nameGroup: "sc_havekar_healer", bondGroup: "", musterGroup: "", displayName: "Гавенкар-лекарь", deckLimit: 1, sourceSet: "witcher3_base"),
        "sc_havekar_healer_3": StaticCard(faction: "scoiatael", row: "ranged", type: "unit", strength: 0, effect: "medic", rarity: "Common", abilityTags: "", nameGroup: "sc_havekar_healer", bondGroup: "", musterGroup: "", displayName: "Гавенкар-лекарь", deckLimit: 1, sourceSet: "witcher3_base"),
        "sc_havekar_smuggler_1": StaticCard(faction: "scoiatael", row: "melee", type: "unit", strength: 5, effect: "muster", rarity: "Common", abilityTags: "", nameGroup: "sc_havekar_smuggler", bondGroup: "", musterGroup: "havekar_smuggler", displayName: "Гавенкар-контрабандист", deckLimit: 1, sourceSet: "witcher3_base"),
        "sc_havekar_smuggler_2": StaticCard(faction: "scoiatael", row: "melee", type: "unit", strength: 5, effect: "muster", rarity: "Common", abilityTags: "", nameGroup: "sc_havekar_smuggler", bondGroup: "", musterGroup: "havekar_smuggler", displayName: "Гавенкар-контрабандист", deckLimit: 1, sourceSet: "witcher3_base"),
        "sc_havekar_smuggler_3": StaticCard(faction: "scoiatael", row: "melee", type: "unit", strength: 5, effect: "muster", rarity: "Common", abilityTags: "", nameGroup: "sc_havekar_smuggler", bondGroup: "", musterGroup: "havekar_smuggler", displayName: "Гавенкар-контрабандист", deckLimit: 1, sourceSet: "witcher3_base"),
        "sc_ida_emean": StaticCard(faction: "scoiatael", row: "ranged", type: "unit", strength: 6, effect: "none", rarity: "Common", abilityTags: "", nameGroup: "sc_ida_emean", bondGroup: "", musterGroup: "", displayName: "Ида Эмеан аэп Сивней", deckLimit: 1, sourceSet: "witcher3_base"),
        "sc_iorveth": StaticCard(faction: "scoiatael", row: "ranged", type: "unit", strength: 10, effect: "hero", rarity: "Hero", abilityTags: "", nameGroup: "sc_iorveth", bondGroup: "", musterGroup: "", displayName: "Иорвет", deckLimit: 1, sourceSet: "witcher3_base"),
        "rare_gwent_01": StaticCard(faction: "scoiatael", row: "melee", type: "unit", strength: 10, effect: "hero", rarity: "Hero", abilityTags: "morale", nameGroup: "rare_gwent_01", bondGroup: "", musterGroup: "", displayName: "Изенгрим Фаоильтиарна", deckLimit: 1, sourceSet: "witcher3_base"),
        "sc_mahakaman_defender_1": StaticCard(faction: "scoiatael", row: "melee", type: "unit", strength: 5, effect: "none", rarity: "Common", abilityTags: "", nameGroup: "sc_mahakaman_defender", bondGroup: "", musterGroup: "", displayName: "Защитник Махакам", deckLimit: 1, sourceSet: "witcher3_base"),
        "sc_mahakaman_defender_2": StaticCard(faction: "scoiatael", row: "melee", type: "unit", strength: 5, effect: "none", rarity: "Common", abilityTags: "", nameGroup: "sc_mahakaman_defender", bondGroup: "", musterGroup: "", displayName: "Защитник Махакам", deckLimit: 1, sourceSet: "witcher3_base"),
        "sc_mahakaman_defender_3": StaticCard(faction: "scoiatael", row: "melee", type: "unit", strength: 5, effect: "none", rarity: "Common", abilityTags: "", nameGroup: "sc_mahakaman_defender", bondGroup: "", musterGroup: "", displayName: "Защитник Махакам", deckLimit: 1, sourceSet: "witcher3_base"),
        "sc_mahakaman_defender_4": StaticCard(faction: "scoiatael", row: "melee", type: "unit", strength: 5, effect: "none", rarity: "Common", abilityTags: "", nameGroup: "sc_mahakaman_defender", bondGroup: "", musterGroup: "", displayName: "Защитник Махакам", deckLimit: 1, sourceSet: "witcher3_base"),
        "sc_mahakaman_defender_5": StaticCard(faction: "scoiatael", row: "melee", type: "unit", strength: 5, effect: "none", rarity: "Common", abilityTags: "", nameGroup: "sc_mahakaman_defender", bondGroup: "", musterGroup: "", displayName: "Защитник Махакам", deckLimit: 1, sourceSet: "witcher3_base"),
        "sc_milva": StaticCard(faction: "scoiatael", row: "ranged", type: "unit", strength: 10, effect: "morale", rarity: "Uncommon", abilityTags: "", nameGroup: "sc_milva", bondGroup: "", musterGroup: "", displayName: "Мильва", deckLimit: 1, sourceSet: "witcher3_base"),
        "sc_riordain": StaticCard(faction: "scoiatael", row: "ranged", type: "unit", strength: 1, effect: "none", rarity: "Common", abilityTags: "", nameGroup: "sc_riordain", bondGroup: "", musterGroup: "", displayName: "Риордаин", deckLimit: 1, sourceSet: "witcher3_base"),
        "sc_saesenthessis": StaticCard(faction: "scoiatael", row: "ranged", type: "unit", strength: 10, effect: "hero", rarity: "Hero", abilityTags: "", nameGroup: "sc_saesenthessis", bondGroup: "", musterGroup: "", displayName: "Саэсентессис", deckLimit: 1, sourceSet: "witcher3_base"),
        "sc_toruviel": StaticCard(faction: "scoiatael", row: "ranged", type: "unit", strength: 2, effect: "none", rarity: "Common", abilityTags: "", nameGroup: "sc_toruviel", bondGroup: "", musterGroup: "", displayName: "Торувьель", deckLimit: 1, sourceSet: "witcher3_base"),
        "sc_vrihedd_brigade_recruit": StaticCard(faction: "scoiatael", row: "ranged", type: "unit", strength: 4, effect: "none", rarity: "Common", abilityTags: "", nameGroup: "sc_vrihedd_brigade_recruit", bondGroup: "", musterGroup: "", displayName: "Новобранец бригады Врихедд", deckLimit: 1, sourceSet: "witcher3_base"),
        "sc_vrihedd_brigade_veteran_1": StaticCard(faction: "scoiatael", row: "melee", type: "unit", strength: 5, effect: "agile", rarity: "Common", abilityTags: "", nameGroup: "sc_vrihedd_brigade_veteran", bondGroup: "", musterGroup: "", displayName: "Ветеран бригады Врихедд", deckLimit: 1, sourceSet: "witcher3_base"),
        "sc_vrihedd_brigade_veteran_2": StaticCard(faction: "scoiatael", row: "melee", type: "unit", strength: 5, effect: "agile", rarity: "Common", abilityTags: "", nameGroup: "sc_vrihedd_brigade_veteran", bondGroup: "", musterGroup: "", displayName: "Ветеран бригады Врихедд", deckLimit: 1, sourceSet: "witcher3_base"),
        "sc_yaevinn": StaticCard(faction: "scoiatael", row: "melee", type: "unit", strength: 6, effect: "agile", rarity: "Common", abilityTags: "", nameGroup: "sc_yaevinn", bondGroup: "", musterGroup: "", displayName: "Яевинн", deckLimit: 1, sourceSet: "witcher3_base"),
        "mo_arachas_1": StaticCard(faction: "monsters", row: "melee", type: "unit", strength: 4, effect: "muster", rarity: "Common", abilityTags: "", nameGroup: "mo_arachas", bondGroup: "", musterGroup: "arachas", displayName: "Арахас", deckLimit: 1, sourceSet: "witcher3_base"),
        "mo_arachas_2": StaticCard(faction: "monsters", row: "melee", type: "unit", strength: 4, effect: "muster", rarity: "Common", abilityTags: "", nameGroup: "mo_arachas", bondGroup: "", musterGroup: "arachas", displayName: "Арахас", deckLimit: 1, sourceSet: "witcher3_base"),
        "mo_arachas_3": StaticCard(faction: "monsters", row: "melee", type: "unit", strength: 4, effect: "muster", rarity: "Common", abilityTags: "", nameGroup: "mo_arachas", bondGroup: "", musterGroup: "arachas", displayName: "Арахас", deckLimit: 1, sourceSet: "witcher3_base"),
        "mo_arachas_behemoth": StaticCard(faction: "monsters", row: "siege", type: "unit", strength: 6, effect: "muster", rarity: "Common", abilityTags: "", nameGroup: "mo_arachas_behemoth", bondGroup: "", musterGroup: "arachas", displayName: "Арахас-бегемот", deckLimit: 1, sourceSet: "witcher3_base"),
        "mo_botchling": StaticCard(faction: "monsters", row: "melee", type: "unit", strength: 4, effect: "none", rarity: "Common", abilityTags: "", nameGroup: "mo_botchling", bondGroup: "", musterGroup: "", displayName: "Игоша", deckLimit: 1, sourceSet: "witcher3_base"),
        "mo_celaeno_harpy": StaticCard(faction: "monsters", row: "melee", type: "unit", strength: 2, effect: "agile", rarity: "Common", abilityTags: "", nameGroup: "mo_celaeno_harpy", bondGroup: "", musterGroup: "", displayName: "Гарпия келено", deckLimit: 1, sourceSet: "witcher3_base"),
        "mo_cockatrice": StaticCard(faction: "monsters", row: "ranged", type: "unit", strength: 2, effect: "none", rarity: "Common", abilityTags: "", nameGroup: "mo_cockatrice", bondGroup: "", musterGroup: "", displayName: "Кокатрикс", deckLimit: 1, sourceSet: "witcher3_base"),
        "mo_crone_brewess": StaticCard(faction: "monsters", row: "melee", type: "unit", strength: 6, effect: "muster", rarity: "Common", abilityTags: "", nameGroup: "mo_crone_brewess", bondGroup: "", musterGroup: "crones", displayName: "Ведьма: Кухарка", deckLimit: 1, sourceSet: "witcher3_base"),
        "mo_crone_weavess": StaticCard(faction: "monsters", row: "melee", type: "unit", strength: 6, effect: "muster", rarity: "Common", abilityTags: "", nameGroup: "mo_crone_weavess", bondGroup: "", musterGroup: "crones", displayName: "Ведьма: Пряха", deckLimit: 1, sourceSet: "witcher3_base"),
        "mo_crone_whispess": StaticCard(faction: "monsters", row: "melee", type: "unit", strength: 6, effect: "muster", rarity: "Common", abilityTags: "", nameGroup: "mo_crone_whispess", bondGroup: "", musterGroup: "crones", displayName: "Ведьма: Шептуха", deckLimit: 1, sourceSet: "witcher3_base"),
        "mo_draug": StaticCard(faction: "monsters", row: "melee", type: "unit", strength: 10, effect: "hero", rarity: "Hero", abilityTags: "", nameGroup: "mo_draug", bondGroup: "", musterGroup: "", displayName: "Драуг", deckLimit: 1, sourceSet: "witcher3_base"),
        "mo_earth_elemental": StaticCard(faction: "monsters", row: "siege", type: "unit", strength: 6, effect: "none", rarity: "Common", abilityTags: "", nameGroup: "mo_earth_elemental", bondGroup: "", musterGroup: "", displayName: "Земной элементаль", deckLimit: 1, sourceSet: "witcher3_base"),
        "mo_endrega": StaticCard(faction: "monsters", row: "ranged", type: "unit", strength: 2, effect: "none", rarity: "Common", abilityTags: "", nameGroup: "mo_endrega", bondGroup: "", musterGroup: "", displayName: "Эндриага", deckLimit: 1, sourceSet: "witcher3_base"),
        "mo_fiend": StaticCard(faction: "monsters", row: "melee", type: "unit", strength: 6, effect: "none", rarity: "Common", abilityTags: "", nameGroup: "mo_fiend", bondGroup: "", musterGroup: "", displayName: "Бес", deckLimit: 1, sourceSet: "witcher3_base"),
        "mo_fire_elemental": StaticCard(faction: "monsters", row: "siege", type: "unit", strength: 6, effect: "none", rarity: "Common", abilityTags: "", nameGroup: "mo_fire_elemental", bondGroup: "", musterGroup: "", displayName: "Огненный элементаль", deckLimit: 1, sourceSet: "witcher3_base"),
        "mo_foglet": StaticCard(faction: "monsters", row: "melee", type: "unit", strength: 2, effect: "none", rarity: "Common", abilityTags: "", nameGroup: "mo_foglet", bondGroup: "", musterGroup: "", displayName: "Туманник", deckLimit: 1, sourceSet: "witcher3_base"),
        "mo_forktail": StaticCard(faction: "monsters", row: "melee", type: "unit", strength: 5, effect: "none", rarity: "Common", abilityTags: "", nameGroup: "mo_forktail", bondGroup: "", musterGroup: "", displayName: "Вилохвост", deckLimit: 1, sourceSet: "witcher3_base"),
        "mo_frightener": StaticCard(faction: "monsters", row: "melee", type: "unit", strength: 5, effect: "none", rarity: "Common", abilityTags: "", nameGroup: "mo_frightener", bondGroup: "", musterGroup: "", displayName: "Пугач", deckLimit: 1, sourceSet: "witcher3_base"),
        "mo_gargoyle": StaticCard(faction: "monsters", row: "ranged", type: "unit", strength: 2, effect: "none", rarity: "Common", abilityTags: "", nameGroup: "mo_gargoyle", bondGroup: "", musterGroup: "", displayName: "Гаргулья", deckLimit: 1, sourceSet: "witcher3_base"),
        "mo_ghoul_1": StaticCard(faction: "monsters", row: "melee", type: "unit", strength: 1, effect: "muster", rarity: "Common", abilityTags: "", nameGroup: "mo_ghoul", bondGroup: "", musterGroup: "ghoul", displayName: "Гуль", deckLimit: 1, sourceSet: "witcher3_base"),
        "mo_ghoul_2": StaticCard(faction: "monsters", row: "melee", type: "unit", strength: 1, effect: "muster", rarity: "Common", abilityTags: "", nameGroup: "mo_ghoul", bondGroup: "", musterGroup: "ghoul", displayName: "Гуль", deckLimit: 1, sourceSet: "witcher3_base"),
        "mo_ghoul_3": StaticCard(faction: "monsters", row: "melee", type: "unit", strength: 1, effect: "muster", rarity: "Common", abilityTags: "", nameGroup: "mo_ghoul", bondGroup: "", musterGroup: "ghoul", displayName: "Гуль", deckLimit: 1, sourceSet: "witcher3_base"),
        "mo_grave_hag": StaticCard(faction: "monsters", row: "ranged", type: "unit", strength: 5, effect: "none", rarity: "Common", abilityTags: "", nameGroup: "mo_grave_hag", bondGroup: "", musterGroup: "", displayName: "Кладбищенская баба", deckLimit: 1, sourceSet: "witcher3_base"),
        "mo_griffin": StaticCard(faction: "monsters", row: "melee", type: "unit", strength: 5, effect: "none", rarity: "Common", abilityTags: "", nameGroup: "mo_griffin", bondGroup: "", musterGroup: "", displayName: "Грифон", deckLimit: 1, sourceSet: "witcher3_base"),
        "mo_harpy": StaticCard(faction: "monsters", row: "melee", type: "unit", strength: 2, effect: "agile", rarity: "Common", abilityTags: "", nameGroup: "mo_harpy", bondGroup: "", musterGroup: "", displayName: "Гарпия", deckLimit: 1, sourceSet: "witcher3_base"),
        "mo_ice_giant": StaticCard(faction: "monsters", row: "siege", type: "unit", strength: 5, effect: "none", rarity: "Common", abilityTags: "", nameGroup: "mo_ice_giant", bondGroup: "", musterGroup: "", displayName: "Ледяной великан", deckLimit: 1, sourceSet: "witcher3_base"),
        "mo_imlerith": StaticCard(faction: "monsters", row: "melee", type: "unit", strength: 10, effect: "hero", rarity: "Hero", abilityTags: "", nameGroup: "mo_imlerith", bondGroup: "", musterGroup: "", displayName: "Имлерих", deckLimit: 1, sourceSet: "witcher3_base"),
        "mo_kayran": StaticCard(faction: "monsters", row: "melee", type: "unit", strength: 8, effect: "hero", rarity: "Hero", abilityTags: "morale;agile", nameGroup: "mo_kayran", bondGroup: "", musterGroup: "", displayName: "Кейран", deckLimit: 1, sourceSet: "witcher3_base"),
        "mo_leshen": StaticCard(faction: "monsters", row: "ranged", type: "unit", strength: 10, effect: "hero", rarity: "Hero", abilityTags: "", nameGroup: "mo_leshen", bondGroup: "", musterGroup: "", displayName: "Леший", deckLimit: 1, sourceSet: "witcher3_base"),
        "gwent_unit_19": StaticCard(faction: "monsters", row: "melee", type: "unit", strength: 2, effect: "muster", rarity: "Common", abilityTags: "", nameGroup: "mo_nekker", bondGroup: "", musterGroup: "nekker", displayName: "Накер", deckLimit: 1, sourceSet: "witcher3_base"),
        "gwent_unit_20": StaticCard(faction: "monsters", row: "melee", type: "unit", strength: 2, effect: "muster", rarity: "Common", abilityTags: "", nameGroup: "mo_nekker", bondGroup: "", musterGroup: "nekker", displayName: "Накер", deckLimit: 1, sourceSet: "witcher3_base"),
        "mo_nekker_3": StaticCard(faction: "monsters", row: "melee", type: "unit", strength: 2, effect: "muster", rarity: "Common", abilityTags: "", nameGroup: "mo_nekker", bondGroup: "", musterGroup: "nekker", displayName: "Накер", deckLimit: 1, sourceSet: "witcher3_base"),
        "mo_plague_maiden": StaticCard(faction: "monsters", row: "melee", type: "unit", strength: 5, effect: "none", rarity: "Common", abilityTags: "", nameGroup: "mo_plague_maiden", bondGroup: "", musterGroup: "", displayName: "Моровая дева", deckLimit: 1, sourceSet: "witcher3_base"),
        "mo_vampire_bruxa": StaticCard(faction: "monsters", row: "melee", type: "unit", strength: 4, effect: "muster", rarity: "Common", abilityTags: "", nameGroup: "mo_vampire_bruxa", bondGroup: "", musterGroup: "vampire", displayName: "Вампир: Брукса", deckLimit: 1, sourceSet: "witcher3_base"),
        "mo_vampire_ekimmara": StaticCard(faction: "monsters", row: "melee", type: "unit", strength: 4, effect: "muster", rarity: "Common", abilityTags: "", nameGroup: "mo_vampire_ekimmara", bondGroup: "", musterGroup: "vampire", displayName: "Вампир: Экимма", deckLimit: 1, sourceSet: "witcher3_base"),
        "mo_vampire_fleder": StaticCard(faction: "monsters", row: "melee", type: "unit", strength: 4, effect: "muster", rarity: "Common", abilityTags: "", nameGroup: "mo_vampire_fleder", bondGroup: "", musterGroup: "vampire", displayName: "Вампир: Фледер", deckLimit: 1, sourceSet: "witcher3_base"),
        "mo_vampire_garkain": StaticCard(faction: "monsters", row: "melee", type: "unit", strength: 4, effect: "muster", rarity: "Common", abilityTags: "", nameGroup: "mo_vampire_garkain", bondGroup: "", musterGroup: "vampire", displayName: "Вампир: Гаркаин", deckLimit: 1, sourceSet: "witcher3_base"),
        "mo_vampire_katakan": StaticCard(faction: "monsters", row: "melee", type: "unit", strength: 5, effect: "muster", rarity: "Common", abilityTags: "", nameGroup: "mo_vampire_katakan", bondGroup: "", musterGroup: "vampire", displayName: "Вампир: Катакан", deckLimit: 1, sourceSet: "witcher3_base"),
        "mo_werewolf": StaticCard(faction: "monsters", row: "melee", type: "unit", strength: 5, effect: "none", rarity: "Common", abilityTags: "", nameGroup: "mo_werewolf", bondGroup: "", musterGroup: "", displayName: "Вервольф", deckLimit: 1, sourceSet: "witcher3_base"),
        "mo_wyvern": StaticCard(faction: "monsters", row: "ranged", type: "unit", strength: 2, effect: "none", rarity: "Common", abilityTags: "", nameGroup: "mo_wyvern", bondGroup: "", musterGroup: "", displayName: "Виверна", deckLimit: 1, sourceSet: "witcher3_base"),
        "gwent_weather_frost": StaticCard(faction: "neutral", row: "weather", type: "special", strength: 0, effect: "weather_melee", rarity: "Special", abilityTags: "", nameGroup: "neutral_biting_frost", bondGroup: "", musterGroup: "", displayName: "Мороз", deckLimit: 1, sourceSet: "witcher3_base"),
        "neutral_biting_frost_2": StaticCard(faction: "neutral", row: "weather", type: "special", strength: 0, effect: "weather_melee", rarity: "Special", abilityTags: "", nameGroup: "neutral_biting_frost", bondGroup: "", musterGroup: "", displayName: "Мороз", deckLimit: 1, sourceSet: "witcher3_base"),
        "neutral_biting_frost_3": StaticCard(faction: "neutral", row: "weather", type: "special", strength: 0, effect: "weather_melee", rarity: "Special", abilityTags: "", nameGroup: "neutral_biting_frost", bondGroup: "", musterGroup: "", displayName: "Мороз", deckLimit: 1, sourceSet: "witcher3_base"),
        "gwent_clear_weather": StaticCard(faction: "neutral", row: "special", type: "special", strength: 0, effect: "clear_weather", rarity: "Special", abilityTags: "", nameGroup: "neutral_clear_weather", bondGroup: "", musterGroup: "", displayName: "Ясная погода", deckLimit: 1, sourceSet: "witcher3_base"),
        "neutral_clear_weather_2": StaticCard(faction: "neutral", row: "special", type: "special", strength: 0, effect: "clear_weather", rarity: "Special", abilityTags: "", nameGroup: "neutral_clear_weather", bondGroup: "", musterGroup: "", displayName: "Ясная погода", deckLimit: 1, sourceSet: "witcher3_base"),
        "neutral_clear_weather_3": StaticCard(faction: "neutral", row: "special", type: "special", strength: 0, effect: "clear_weather", rarity: "Special", abilityTags: "", nameGroup: "neutral_clear_weather", bondGroup: "", musterGroup: "", displayName: "Ясная погода", deckLimit: 1, sourceSet: "witcher3_base"),
        "gwent_horn": StaticCard(faction: "neutral", row: "special", type: "special", strength: 0, effect: "commanders_horn", rarity: "Special", abilityTags: "", nameGroup: "neutral_commanders_horn", bondGroup: "", musterGroup: "", displayName: "Командирский рог", deckLimit: 1, sourceSet: "witcher3_base"),
        "neutral_commanders_horn_2": StaticCard(faction: "neutral", row: "special", type: "special", strength: 0, effect: "commanders_horn", rarity: "Special", abilityTags: "", nameGroup: "neutral_commanders_horn", bondGroup: "", musterGroup: "", displayName: "Командирский рог", deckLimit: 1, sourceSet: "witcher3_base"),
        "neutral_commanders_horn_3": StaticCard(faction: "neutral", row: "special", type: "special", strength: 0, effect: "commanders_horn", rarity: "Special", abilityTags: "", nameGroup: "neutral_commanders_horn", bondGroup: "", musterGroup: "", displayName: "Командирский рог", deckLimit: 1, sourceSet: "witcher3_base"),
        "neutral_commanders_horn_4": StaticCard(faction: "neutral", row: "special", type: "special", strength: 0, effect: "commanders_horn", rarity: "Special", abilityTags: "", nameGroup: "neutral_commanders_horn", bondGroup: "", musterGroup: "", displayName: "Командирский рог", deckLimit: 1, sourceSet: "witcher3_base"),
        "gwent_decoy": StaticCard(faction: "neutral", row: "special", type: "special", strength: 0, effect: "decoy", rarity: "Special", abilityTags: "", nameGroup: "neutral_decoy", bondGroup: "", musterGroup: "", displayName: "Чучело", deckLimit: 1, sourceSet: "witcher3_base"),
        "neutral_decoy_2": StaticCard(faction: "neutral", row: "special", type: "special", strength: 0, effect: "decoy", rarity: "Special", abilityTags: "", nameGroup: "neutral_decoy", bondGroup: "", musterGroup: "", displayName: "Чучело", deckLimit: 1, sourceSet: "witcher3_base"),
        "neutral_decoy_3": StaticCard(faction: "neutral", row: "special", type: "special", strength: 0, effect: "decoy", rarity: "Special", abilityTags: "", nameGroup: "neutral_decoy", bondGroup: "", musterGroup: "", displayName: "Чучело", deckLimit: 1, sourceSet: "witcher3_base"),
        "neutral_emiel_regis": StaticCard(faction: "neutral", row: "melee", type: "unit", strength: 5, effect: "none", rarity: "Common", abilityTags: "", nameGroup: "neutral_emiel_regis", bondGroup: "", musterGroup: "", displayName: "Эмиель Регис Рогеллек Терзиефф", deckLimit: 1, sourceSet: "witcher3_base"),
        "rare_gwent_03": StaticCard(faction: "neutral", row: "melee", type: "unit", strength: 15, effect: "hero", rarity: "Hero", abilityTags: "", nameGroup: "rare_gwent_03", bondGroup: "", musterGroup: "", displayName: "Цирилла Фиона Элен Рианнон", deckLimit: 1, sourceSet: "witcher3_base"),
        "rare_gwent_02": StaticCard(faction: "neutral", row: "melee", type: "unit", strength: 15, effect: "hero", rarity: "Hero", abilityTags: "", nameGroup: "rare_gwent_02", bondGroup: "", musterGroup: "", displayName: "Геральт из Ривии", deckLimit: 1, sourceSet: "witcher3_base"),
        "gwent_weather_fog": StaticCard(faction: "neutral", row: "weather", type: "special", strength: 0, effect: "weather_ranged", rarity: "Special", abilityTags: "", nameGroup: "neutral_impenetrable_fog", bondGroup: "", musterGroup: "", displayName: "Непроницаемый туман", deckLimit: 1, sourceSet: "witcher3_base"),
        "neutral_impenetrable_fog_2": StaticCard(faction: "neutral", row: "weather", type: "special", strength: 0, effect: "weather_ranged", rarity: "Special", abilityTags: "", nameGroup: "neutral_impenetrable_fog", bondGroup: "", musterGroup: "", displayName: "Непроницаемый туман", deckLimit: 1, sourceSet: "witcher3_base"),
        "neutral_impenetrable_fog_3": StaticCard(faction: "neutral", row: "weather", type: "special", strength: 0, effect: "weather_ranged", rarity: "Special", abilityTags: "", nameGroup: "neutral_impenetrable_fog", bondGroup: "", musterGroup: "", displayName: "Непроницаемый туман", deckLimit: 1, sourceSet: "witcher3_base"),
        "rare_gwent_04": StaticCard(faction: "neutral", row: "melee", type: "unit", strength: 0, effect: "hero", rarity: "Hero", abilityTags: "spy", nameGroup: "rare_gwent_04", bondGroup: "", musterGroup: "", displayName: "Таинственный эльф", deckLimit: 1, sourceSet: "witcher3_base"),
        "gwent_scorch": StaticCard(faction: "neutral", row: "special", type: "special", strength: 0, effect: "scorch", rarity: "Special", abilityTags: "", nameGroup: "neutral_scorch", bondGroup: "", musterGroup: "", displayName: "Казнь", deckLimit: 1, sourceSet: "witcher3_base"),
        "neutral_scorch_2": StaticCard(faction: "neutral", row: "special", type: "special", strength: 0, effect: "scorch", rarity: "Special", abilityTags: "", nameGroup: "neutral_scorch", bondGroup: "", musterGroup: "", displayName: "Казнь", deckLimit: 1, sourceSet: "witcher3_base"),
        "neutral_scorch_3": StaticCard(faction: "neutral", row: "special", type: "special", strength: 0, effect: "scorch", rarity: "Special", abilityTags: "", nameGroup: "neutral_scorch", bondGroup: "", musterGroup: "", displayName: "Казнь", deckLimit: 1, sourceSet: "witcher3_base"),
        "gwent_weather_rain": StaticCard(faction: "neutral", row: "weather", type: "special", strength: 0, effect: "weather_siege", rarity: "Special", abilityTags: "", nameGroup: "neutral_torrential_rain", bondGroup: "", musterGroup: "", displayName: "Ливень", deckLimit: 1, sourceSet: "witcher3_base"),
        "neutral_torrential_rain_2": StaticCard(faction: "neutral", row: "weather", type: "special", strength: 0, effect: "weather_siege", rarity: "Special", abilityTags: "", nameGroup: "neutral_torrential_rain", bondGroup: "", musterGroup: "", displayName: "Ливень", deckLimit: 1, sourceSet: "witcher3_base"),
        "neutral_torrential_rain_3": StaticCard(faction: "neutral", row: "weather", type: "special", strength: 0, effect: "weather_siege", rarity: "Special", abilityTags: "", nameGroup: "neutral_torrential_rain", bondGroup: "", musterGroup: "", displayName: "Ливень", deckLimit: 1, sourceSet: "witcher3_base"),
        "neutral_triss": StaticCard(faction: "neutral", row: "melee", type: "unit", strength: 7, effect: "hero", rarity: "Hero", abilityTags: "", nameGroup: "neutral_triss", bondGroup: "", musterGroup: "", displayName: "Трисс Меригольд", deckLimit: 1, sourceSet: "witcher3_base"),
        "neutral_vesemir": StaticCard(faction: "neutral", row: "melee", type: "unit", strength: 6, effect: "none", rarity: "Common", abilityTags: "", nameGroup: "neutral_vesemir", bondGroup: "", musterGroup: "", displayName: "Весемир", deckLimit: 1, sourceSet: "witcher3_base"),
        "rare_gwent_06": StaticCard(faction: "neutral", row: "melee", type: "unit", strength: 2, effect: "commanders_horn", rarity: "Uncommon", abilityTags: "", nameGroup: "rare_gwent_06", bondGroup: "", musterGroup: "", displayName: "Лютик", deckLimit: 1, sourceSet: "witcher3_base"),
        "neutral_villentretenmerth": StaticCard(faction: "neutral", row: "melee", type: "unit", strength: 7, effect: "scorch_melee", rarity: "Uncommon", abilityTags: "", nameGroup: "neutral_villentretenmerth", bondGroup: "", musterGroup: "", displayName: "Виллентретенмерт", deckLimit: 1, sourceSet: "witcher3_base"),
        "rare_gwent_05": StaticCard(faction: "neutral", row: "ranged", type: "unit", strength: 7, effect: "hero", rarity: "Hero", abilityTags: "medic", nameGroup: "rare_gwent_05", bondGroup: "", musterGroup: "", displayName: "Йеннифэр из Венгерберга", deckLimit: 1, sourceSet: "witcher3_base"),
        "neutral_zoltan": StaticCard(faction: "neutral", row: "melee", type: "unit", strength: 5, effect: "none", rarity: "Common", abilityTags: "", nameGroup: "neutral_zoltan", bondGroup: "", musterGroup: "", displayName: "Золтан Хивай", deckLimit: 1, sourceSet: "witcher3_base"),
    ]

    static var allCards: [GwentCard] {
        cards.keys.sorted().compactMap { card($0) }
    }

    static func card(_ cardId: String) -> GwentCard? {
        guard let row = cards[cardId] else { return nil }
        return GwentCard(
            cardId: cardId,
            faction: row.faction,
            row: row.row,
            type: row.type,
            strength: row.strength,
            effect: row.effect,
            rarity: row.rarity,
            abilityTags: split(row.abilityTags),
            nameGroup: row.nameGroup,
            bondGroup: row.bondGroup,
            musterGroup: row.musterGroup,
            displayName: row.displayName,
            effectText: "",
            deckLimit: row.deckLimit,
            sourceSet: row.sourceSet
        )
    }

    private static func split(_ raw: String) -> [String] {
        raw.split(separator: ";").map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }.filter { !$0.isEmpty }
    }
}


struct GwentDeck: Codable, Equatable, Identifiable {
    var deckId: String
    var playerId: String
    var leaderCardId: String
    var cardIds: [String]

    var id: String { deckId }

    enum CodingKeys: String, CodingKey {
        case deckId = "deck_id"
        case playerId = "player_id"
        case leaderCardId = "leader_card_id"
        case cardIds = "card_ids"
    }

    init(deckId: String, playerId: String, leaderCardId: String, cardIds: [String]) {
        self.deckId = deckId
        self.playerId = playerId
        self.leaderCardId = leaderCardId
        self.cardIds = cardIds
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        deckId = container.decodeFlexibleString(forKey: .deckId)
        playerId = container.decodeFlexibleString(forKey: .playerId)
        leaderCardId = container.decodeFlexibleString(forKey: .leaderCardId)
        let savedCards = (try? container.decodeIfPresent([String].self, forKey: .cardIds)) ?? nil
        if let savedCards {
            cardIds = savedCards
        } else {
            let rawCards = container.decodeFlexibleString(forKey: .cardIds)
            cardIds = rawCards.split(separator: ";").map(String.init)
        }
    }
}

extension KeyedDecodingContainer {
    func decodeFlexibleString(forKey key: Key) -> String {
        decodeFlexibleStringIfPresent(forKey: key) ?? ""
    }

    func decodeFlexibleStringIfPresent(forKey key: Key) -> String? {
        if let value = try? decodeIfPresent(String.self, forKey: key) {
            return value
        }
        if let value = try? decodeIfPresent(Int.self, forKey: key) {
            return String(value)
        }
        if let value = try? decodeIfPresent(Double.self, forKey: key) {
            return String(value)
        }
        if let value = try? decodeIfPresent(Bool.self, forKey: key) {
            return value ? "true" : "false"
        }
        return nil
    }

    func decodeFlexibleInt(forKey key: Key, default fallback: Int = 0) -> Int {
        decodeFlexibleIntIfPresent(forKey: key) ?? fallback
    }

    func decodeFlexibleIntIfPresent(forKey key: Key) -> Int? {
        if let value = try? decodeIfPresent(Int.self, forKey: key) {
            return value
        }
        if let value = try? decodeIfPresent(Double.self, forKey: key) {
            return Int(value)
        }
        if let value = try? decodeIfPresent(String.self, forKey: key) {
            return Int(value)
        }
        return nil
    }

    func decodeFlexibleBool(forKey key: Key, default fallback: Bool = false) -> Bool {
        if let value = try? decodeIfPresent(Bool.self, forKey: key) {
            return value
        }
        if let value = try? decodeIfPresent(String.self, forKey: key) {
            return ["true", "1", "yes"].contains(value.trimmingCharacters(in: .whitespacesAndNewlines).lowercased())
        }
        return fallback
    }
}
