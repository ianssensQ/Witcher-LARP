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
    let role: String?
    let displayName: String?

    enum CodingKeys: String, CodingKey {
        case playerId = "player_id"
        case role
        case displayName = "display_name"
    }
}

struct SyncRequest: Encodable {
    let deviceId: String
    let events: [QueuedEvent]

    enum CodingKeys: String, CodingKey {
        case deviceId = "device_id"
        case events
    }
}

struct SyncResponse: Decodable {
    let serverTime: Date?
    let snapshotVersion: Int?
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
    let serverEventId: String?

    var id: UUID { eventId }

    enum CodingKeys: String, CodingKey {
        case eventId = "event_id"
        case status
        case reason
        case serverEventId = "server_event_id"
    }
}
