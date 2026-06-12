import Foundation

final class EventQueueStore {
    static let shared = EventQueueStore()

    private let fileManager = FileManager.default
    private let queueURL: URL

    private init() {
        let documents = fileManager.urls(for: .documentDirectory, in: .userDomainMask)[0]
        let folder = documents.appendingPathComponent("WitcherLARP", isDirectory: true)
        try? fileManager.createDirectory(at: folder, withIntermediateDirectories: true)
        queueURL = folder.appendingPathComponent("event_queue.json")
    }

    func loadEvents() -> [QueuedEvent] {
        guard let data = try? Data(contentsOf: queueURL) else { return [] }
        return (try? JSONDecoder().decode([QueuedEvent].self, from: data)) ?? []
    }

    func append(_ event: QueuedEvent) {
        var events = loadEvents()
        events.append(event)
        save(events)
    }

    func applySyncResults(_ results: [SyncEventResult]) {
        let statuses = Dictionary(uniqueKeysWithValues: results.map { ($0.eventId, $0.status) })
        let remaining = loadEvents().filter { event in
            guard let status = statuses[event.id] else { return true }
            return status != "accepted" && status != "duplicate"
        }
        save(remaining)
    }

    private func save(_ events: [QueuedEvent]) {
        let data = try? JSONEncoder().encode(events)
        try? data?.write(to: queueURL, options: [.atomic])
    }
}

struct QueuedEvent: Codable, Identifiable, Equatable {
    let id: UUID
    let playerId: String
    let clientSequence: Int
    let createdAt: Date
    let eventType: String
    let payload: [String: String]

    init(
        id: UUID = UUID(),
        playerId: String,
        clientSequence: Int = Int(Date().timeIntervalSince1970),
        createdAt: Date = Date(),
        eventType: String,
        payload: [String: String]
    ) {
        self.id = id
        self.playerId = playerId
        self.clientSequence = clientSequence
        self.createdAt = createdAt
        self.eventType = eventType
        self.payload = payload
    }

    enum CodingKeys: String, CodingKey {
        case id = "event_id"
        case playerId = "player_id"
        case clientSequence = "client_sequence"
        case createdAt = "created_at"
        case eventType = "event_type"
        case payload
    }
}
