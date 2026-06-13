import Foundation

struct LoginRequest: Encodable {
    let playerCode: String
    let deviceId: String

    enum CodingKeys: String, CodingKey {
        case playerCode = "player_code"
        case deviceId = "device_id"
    }
}

struct LoginResponse: Decodable {
    let playerId: String
    let roleType: String?
    let displayName: String?
    let deviceId: String?
    let snapshotPath: String?

    enum CodingKeys: String, CodingKey {
        case playerId = "player_id"
        case roleType = "role_type"
        case displayName = "display_name"
        case deviceId = "device_id"
        case snapshotPath = "snapshot_path"
    }
}

struct HealthResponse: Decodable {
    let status: String?
    let service: String?
    let database: JSONValue?
    let api: APIHealth?
}

struct APIHealth: Decodable {
    let revision: String?
    let features: [String]?
}

struct SyncRequest: Encodable {
    let deviceId: String
    let actorId: String
    let actorType: String
    let events: [QueuedEvent]

    enum CodingKeys: String, CodingKey {
        case deviceId = "device_id"
        case actorId = "actor_id"
        case actorType = "actor_type"
        case events
    }
}

struct SyncResponse: Decodable {
    let serverTime: Date?
    let snapshotVersion: String?
    let results: [SyncEventResult]

    enum CodingKeys: String, CodingKey {
        case serverTime = "server_time"
        case snapshotVersion = "snapshot_version"
        case results
    }
}

struct SyncEventResult: Codable, Identifiable {
    let eventId: UUID
    let status: String
    let reason: String?
    let serverEventId: Int?

    var id: UUID { eventId }

    enum CodingKeys: String, CodingKey {
        case eventId = "event_id"
        case status
        case reason
        case serverEventId = "server_event_id"
    }
}

struct QrLookupRequest: Encodable {
    let code: String
    let playerId: String?
    let deviceId: String?
    let source: String
    let physicalPresenceConfirmed: Bool

    enum CodingKeys: String, CodingKey {
        case code
        case playerId = "player_id"
        case deviceId = "device_id"
        case source
        case physicalPresenceConfirmed = "physical_presence_confirmed"
    }
}

struct OrderActionRequest: Encodable {
    let action: String
    let orderId: String?
    let playerId: String?
    let resultEventId: String?
    let source: String

    enum CodingKeys: String, CodingKey {
        case action
        case orderId = "order_id"
        case playerId = "player_id"
        case resultEventId = "result_event_id"
        case source
    }
}

struct PvpTablesResponse: Decodable {
    let throttle: JSONValue?
    let tables: [JSONValue]?
    let queuedChallenges: [JSONValue]?

    enum CodingKeys: String, CodingKey {
        case throttle
        case tables
        case queuedChallenges = "queued_challenges"
    }
}

struct PvpChallengeRequest: Encodable {
    let challengerId: String
    let targetId: String
    let stake: [String: JSONValue]
    let challengeId: String?
    let mandatory: Bool
    let masterApproval: Bool
    let source: String

    enum CodingKeys: String, CodingKey {
        case challengerId = "challenger_id"
        case targetId = "target_id"
        case stake
        case challengeId = "challenge_id"
        case mandatory
        case masterApproval = "master_approval"
        case source
    }
}

struct PvpStartRequest: Encodable {
    let masterApproval: Bool
    let mulligansByPlayer: [String: [String]]?
    let deckIdsByPlayer: [String: String]?
    let preferredStartingPlayerId: String?
    let source: String

    enum CodingKeys: String, CodingKey {
        case masterApproval = "master_approval"
        case mulligansByPlayer = "mulligans_by_player"
        case deckIdsByPlayer = "deck_ids_by_player"
        case preferredStartingPlayerId = "preferred_starting_player_id"
        case source
    }
}

struct PvpRefusalRequest: Encodable {
    let reason: String
    let actorId: String?
    let source: String

    enum CodingKeys: String, CodingKey {
        case reason
        case actorId = "actor_id"
        case source
    }
}

struct GwentPreparationRequest: Encodable {
    let mulligans: [String]?
    let deckId: String?
    let preferredStartingPlayerId: String?
    let source: String

    enum CodingKeys: String, CodingKey {
        case mulligans
        case deckId = "deck_id"
        case preferredStartingPlayerId = "preferred_starting_player_id"
        case source
    }
}

struct GwentActionRequest: Encodable {
    let action: String
    let roundNumber: Int?
    let cardId: String?
    let row: String?
    let targetCardId: String?
    let discardCardIds: [String]?
    let reviveCardId: String?
    let reviveRow: String?
    let actionId: String?
    let source: String

    enum CodingKeys: String, CodingKey {
        case action
        case roundNumber = "round_number"
        case cardId = "card_id"
        case row
        case targetCardId = "target_card_id"
        case discardCardIds = "discard_card_ids"
        case reviveCardId = "revive_card_id"
        case reviveRow = "revive_row"
        case actionId = "action_id"
        case source
    }
}

struct GwentBotMatchRequest: Encodable {
    let mulligans: [String]?
    let deckId: String?
    let source: String

    enum CodingKeys: String, CodingKey {
        case mulligans
        case deckId = "deck_id"
        case source
    }
}

struct GwentDeckSaveRequest: Encodable {
    let deckId: String?
    let leaderCardId: String
    let cardIds: [String]
    let source: String

    enum CodingKeys: String, CodingKey {
        case deckId = "deck_id"
        case leaderCardId = "leader_card_id"
        case cardIds = "card_ids"
        case source
    }
}

struct GwentFinishRequest: Encodable {
    let winnerId: String?
    let outcome: String
    let source: String

    enum CodingKeys: String, CodingKey {
        case winnerId = "winner_id"
        case outcome
        case source
    }
}

struct TradeCreateRequest: Encodable {
    let fromPlayerId: String
    let toPlayerId: String
    let assetType: String
    let assetId: String
    let quantity: Int
    let priceGold: Int
    let mode: String
    let transferId: String?
    let autoAccept: Bool
    let source: String

    enum CodingKeys: String, CodingKey {
        case fromPlayerId = "from_player_id"
        case toPlayerId = "to_player_id"
        case assetType = "asset_type"
        case assetId = "asset_id"
        case quantity
        case priceGold = "price_gold"
        case mode
        case transferId = "transfer_id"
        case autoAccept = "auto_accept"
        case source
    }
}

struct MaterialMarketSellRequest: Encodable {
    let materialId: String
    let quantity: Int
    let saleId: String?
    let source: String

    enum CodingKeys: String, CodingKey {
        case materialId = "material_id"
        case quantity
        case saleId = "sale_id"
        case source
    }
}

struct TradeAcceptRequest: Encodable {
    let acceptedByPlayerId: String
    let source: String

    enum CodingKeys: String, CodingKey {
        case acceptedByPlayerId = "accepted_by_player_id"
        case source
    }
}

struct TradeDeclineRequest: Encodable {
    let declinedByPlayerId: String
    let reason: String
    let source: String

    enum CodingKeys: String, CodingKey {
        case declinedByPlayerId = "declined_by_player_id"
        case reason
        case source
    }
}
