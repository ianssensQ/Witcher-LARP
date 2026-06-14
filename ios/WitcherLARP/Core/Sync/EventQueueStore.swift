import Foundation

final class EventQueueStore {
    static let shared = EventQueueStore()

    private let fileManager = FileManager.default
    private let queueURL: URL
    private let sequenceURL: URL

    private init() {
        let documents = fileManager.urls(for: .documentDirectory, in: .userDomainMask)[0]
        let folder = documents.appendingPathComponent("WitcherLARP", isDirectory: true)
        try? fileManager.createDirectory(at: folder, withIntermediateDirectories: true)
        queueURL = folder.appendingPathComponent("event_queue.json")
        sequenceURL = folder.appendingPathComponent("client_sequence.json")
    }

    func loadEvents() -> [QueuedEvent] {
        loadAllEvents().filter { !$0.isTerminalSynced }
    }

    private func loadAllEvents() -> [QueuedEvent] {
        guard let data = try? Data(contentsOf: queueURL) else { return [] }
        return (try? JSONDecoder().decode([QueuedEvent].self, from: data)) ?? []
    }

    func append(_ event: QueuedEvent) {
        var events = loadAllEvents()
        events.append(event)
        save(events)
    }

    func replaceEvents(_ events: [QueuedEvent]) {
        save(events)
    }

    func clear() {
        try? fileManager.removeItem(at: queueURL)
        try? fileManager.removeItem(at: sequenceURL)
    }

    func makeEvent(
        playerId: String,
        eventType: String,
        payload: [String: JSONValue]
    ) -> QueuedEvent {
        QueuedEvent(
            playerId: playerId,
            clientSequence: nextClientSequence(),
            eventType: eventType,
            payload: payload
        )
    }

    func applySyncResults(_ results: [SyncEventResult]) {
        let byEventId = Dictionary(uniqueKeysWithValues: results.map { ($0.eventId, $0) })
        let syncedAt = Date()
        let remaining = loadAllEvents().compactMap { event -> QueuedEvent? in
            guard let result = byEventId[event.id] else { return event }
            let updated = event.markingSyncResult(result, syncedAt: syncedAt)
            return updated.isTerminalSynced ? nil : updated
        }
        save(remaining)
    }

    func markSyncError(_ message: String) {
        let updated = loadAllEvents().map { event in
            event.markingSyncError(message)
        }
        save(updated)
    }

    private func save(_ events: [QueuedEvent]) {
        let data = try? JSONEncoder().encode(events)
        try? data?.write(to: queueURL, options: [.atomic])
    }

    private func nextClientSequence() -> Int {
        let current: Int
        if
            let data = try? Data(contentsOf: sequenceURL),
            let saved = try? JSONDecoder().decode(Int.self, from: data)
        {
            current = saved
        } else {
            current = 0
        }
        let next = current + 1
        let data = try? JSONEncoder().encode(next)
        try? data?.write(to: sequenceURL, options: [.atomic])
        return next
    }
}

struct QueuedEvent: Codable, Identifiable, Equatable {
    let id: UUID
    let playerId: String
    let clientSequence: Int
    let createdAt: Date
    let eventType: String
    let payload: [String: JSONValue]
    let syncStatus: String
    let syncReason: String?
    let serverEventId: Int?
    let lastSyncedAt: Date?

    var isTerminalSynced: Bool {
        switch syncStatus.lowercased() {
        case "accepted", "duplicate", "synced":
            return true
        default:
            return false
        }
    }

    init(
        id: UUID = UUID(),
        playerId: String,
        clientSequence: Int,
        createdAt: Date = Date(),
        eventType: String,
        payload: [String: JSONValue],
        syncStatus: String = "pending",
        syncReason: String? = nil,
        serverEventId: Int? = nil,
        lastSyncedAt: Date? = nil
    ) {
        self.id = id
        self.playerId = playerId
        self.clientSequence = clientSequence
        self.createdAt = createdAt
        self.eventType = eventType
        self.payload = payload
        self.syncStatus = syncStatus
        self.syncReason = syncReason
        self.serverEventId = serverEventId
        self.lastSyncedAt = lastSyncedAt
    }

    enum CodingKeys: String, CodingKey {
        case id = "event_id"
        case playerId = "player_id"
        case clientSequence = "client_sequence"
        case createdAt = "created_at"
        case eventType = "event_type"
        case payload
        case syncStatus = "sync_status"
        case syncReason = "sync_reason"
        case serverEventId = "server_event_id"
        case lastSyncedAt = "last_synced_at"
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        id = try container.decode(UUID.self, forKey: .id)
        playerId = try container.decode(String.self, forKey: .playerId)
        clientSequence = try container.decode(Int.self, forKey: .clientSequence)
        createdAt = try container.decode(Date.self, forKey: .createdAt)
        eventType = try container.decode(String.self, forKey: .eventType)
        payload = try container.decode([String: JSONValue].self, forKey: .payload)
        syncStatus = (try? container.decodeIfPresent(String.self, forKey: .syncStatus)) ?? "pending"
        syncReason = try? container.decodeIfPresent(String.self, forKey: .syncReason)
        serverEventId = try? container.decodeIfPresent(Int.self, forKey: .serverEventId)
        lastSyncedAt = try? container.decodeIfPresent(Date.self, forKey: .lastSyncedAt)
    }

    func markingSyncResult(_ result: SyncEventResult, syncedAt: Date) -> QueuedEvent {
        QueuedEvent(
            id: id,
            playerId: playerId,
            clientSequence: clientSequence,
            createdAt: createdAt,
            eventType: eventType,
            payload: payload,
            syncStatus: result.status,
            syncReason: result.reason,
            serverEventId: result.serverEventId,
            lastSyncedAt: syncedAt
        )
    }

    func markingSyncError(_ message: String) -> QueuedEvent {
        QueuedEvent(
            id: id,
            playerId: playerId,
            clientSequence: clientSequence,
            createdAt: createdAt,
            eventType: eventType,
            payload: payload,
            syncStatus: "sync_error",
            syncReason: message,
            serverEventId: serverEventId,
            lastSyncedAt: lastSyncedAt
        )
    }
}
