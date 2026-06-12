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
    let cards: [SnapshotRow]
    let potions: [SnapshotRow]
    let artifacts: [SnapshotRow]
    let gwentCards: [GwentCard]
    let gwentDecks: [GwentDeck]
    let assetOwnership: [SnapshotRow]
    let potionInventory: [SnapshotRow]
    let tradeTransfers: [SnapshotRow]
    let rewardApprovals: [SnapshotRow]
    let goals: SnapshotGoals
    let actUnlockCodes: [SnapshotRow]
    let actUnlockState: SnapshotRow

    var currentPlayer: PlayerProfile? {
        player ?? players.first
    }

    var visibleGoals: [PlayerGoal] {
        goals.personalGoals
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
        case cards
        case potions
        case artifacts
        case gwentCards = "gwent_cards"
        case gwentDecks = "gwent_decks"
        case assetOwnership = "asset_ownership"
        case potionInventory = "potion_inventory"
        case tradeTransfers = "trade_transfers"
        case rewardApprovals = "reward_approvals"
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
        cards = (try? container.decode([SnapshotRow].self, forKey: .cards)) ?? []
        potions = (try? container.decode([SnapshotRow].self, forKey: .potions)) ?? []
        artifacts = (try? container.decode([SnapshotRow].self, forKey: .artifacts)) ?? []
        gwentCards = (try? container.decode([GwentCard].self, forKey: .gwentCards)) ?? []
        gwentDecks = (try? container.decode([GwentDeck].self, forKey: .gwentDecks)) ?? []
        assetOwnership = (try? container.decode([SnapshotRow].self, forKey: .assetOwnership)) ?? []
        potionInventory = (try? container.decode([SnapshotRow].self, forKey: .potionInventory)) ?? []
        tradeTransfers = (try? container.decode([SnapshotRow].self, forKey: .tradeTransfers)) ?? []
        rewardApprovals = (try? container.decode([SnapshotRow].self, forKey: .rewardApprovals)) ?? []
        goals = (try? container.decode(SnapshotGoals.self, forKey: .goals)) ?? SnapshotGoals()
        actUnlockCodes = (try? container.decode([SnapshotRow].self, forKey: .actUnlockCodes)) ?? []
        actUnlockState = (try? container.decode(SnapshotRow.self, forKey: .actUnlockState)) ?? [:]
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
    let reputationLabel: String
    let stats: [String: Int]

    var id: String { playerId }

    enum CodingKeys: String, CodingKey {
        case playerId = "player_id"
        case roleType = "role_type"
        case displayName = "display_name"
        case actId = "act_id"
        case level
        case xp
        case gold
        case reputationLabel = "reputation_label"
        case reputationState = "reputation_state"
        case statsJson = "stats_json"
        case stats
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
        try container.encode(reputationLabel, forKey: .reputationLabel)
        try container.encode(stats, forKey: .stats)
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
    let combatProfileId: String
    let rewardId: String
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
        case combatProfileId = "combat_profile_id"
        case rewardId = "reward_id"
        case successText = "success_text"
        case failureText = "failure_text"
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        scenarioId = container.decodeFlexibleString(forKey: .scenarioId)
        actId = container.decodeFlexibleString(forKey: .actId)
        tier = container.decodeFlexibleInt(forKey: .tier, default: 1)
        sceneType = container.decodeFlexibleString(forKey: .sceneType)
        primaryStat = container.decodeFlexibleString(forKey: .primaryStat)
        dc = container.decodeFlexibleInt(forKey: .dc)
        combatProfileId = container.decodeFlexibleString(forKey: .combatProfileId)
        rewardId = container.decodeFlexibleString(forKey: .rewardId)
        successText = container.decodeFlexibleStringIfPresent(forKey: .successText) ?? "Успех"
        failureText = container.decodeFlexibleStringIfPresent(forKey: .failureText) ?? "Провал"
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

    var id: String { orderId }
    var isAcceptable: Bool { ["published", "addressed_pending", "failed_retryable"].contains(status) }
    var isSubmittable: Bool { ["accepted", "in_progress", "claimed_at_prop", "submitted_pending_sync"].contains(status) }

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
    }

    private static func splitIds(_ raw: String?) -> [String] {
        (raw ?? "")
            .split(separator: ";")
            .map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
            .filter { !$0.isEmpty }
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
        if let value = try? decodeIfPresent(Int.self, forKey: key) {
            return value
        }
        if let value = try? decodeIfPresent(Double.self, forKey: key) {
            return Int(value)
        }
        if let value = try? decodeIfPresent(String.self, forKey: key) {
            return Int(value) ?? fallback
        }
        return fallback
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
