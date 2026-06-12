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

struct QRLookupRequest: Encodable {
    let code: String
    let playerId: String?
    let deviceId: String
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

struct QRLookupResponse: Decodable, Equatable {
    let status: String
    let eventType: String?
    let reason: String?
    let message: String?
    let qr: QRLookupQRPayload?
    let scenario: PvEScenarioCard?

    enum CodingKeys: String, CodingKey {
        case status
        case eventType = "event_type"
        case reason
        case message
        case qr
        case scenario
    }
}

struct QRLookupQRPayload: Decodable, Equatable {
    let qrId: String?
    let manualCode: String?
    let scenarioId: String?
    let qrMode: String?
    let actId: String?
    let locationNodeId: String?
    let locked: Bool?

    enum CodingKeys: String, CodingKey {
        case qrId = "qr_id"
        case manualCode = "manual_code"
        case scenarioId = "scenario_id"
        case qrMode = "qr_mode"
        case actId = "act_id"
        case locationNodeId = "location_node_id"
        case locked
    }
}
