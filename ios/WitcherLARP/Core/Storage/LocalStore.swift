import Foundation

final class LocalStore {
    static let shared = LocalStore()

    private let fileManager = FileManager.default
    private let baseDirectory: URL

    private init() {
        let documents = fileManager.urls(for: .documentDirectory, in: .userDomainMask)[0]
        baseDirectory = documents.appendingPathComponent("WitcherLARP", isDirectory: true)
        try? fileManager.createDirectory(at: baseDirectory, withIntermediateDirectories: true)
    }

    func loadDeviceId() -> String {
        if let saved: String = load("device_id.json") {
            return saved
        }
        let created = UUID().uuidString
        save(created, as: "device_id.json")
        return created
    }

    func loadServerURL() -> URL? {
        guard let value: String = load("server_url.json") else { return nil }
        return URL(string: value)
    }

    func saveServerURL(_ url: URL) {
        save(url.absoluteString, as: "server_url.json")
    }

    func loadPlayerCode() -> String? {
        load("player_code.json")
    }

    func savePlayerCode(_ code: String) {
        save(code, as: "player_code.json")
    }

    func loadSnapshot() -> PlayerSnapshot? {
        load("snapshot.json")
    }

    func saveSnapshot(_ snapshot: PlayerSnapshot) {
        save(snapshot, as: "snapshot.json")
    }

    func clearPlayerSession() {
        remove("player_code.json")
        remove("snapshot.json")
        remove("unlocked_act_ids.json")
        remove("pve_cooldowns.json")
    }

    func loadUnlockedActIds() -> Set<String> {
        let saved: [String]? = load("unlocked_act_ids.json")
        return Set(saved ?? [])
    }

    func saveUnlockedActIds(_ actIds: Set<String>) {
        save(actIds.sorted(), as: "unlocked_act_ids.json")
    }

    func loadPVECooldowns() -> [String: Date] {
        load("pve_cooldowns.json") ?? [:]
    }

    func savePVECooldowns(_ cooldowns: [String: Date]) {
        save(cooldowns, as: "pve_cooldowns.json")
    }

    private func load<T: Decodable>(_ fileName: String) -> T? {
        let url = baseDirectory.appendingPathComponent(fileName)
        guard let data = try? Data(contentsOf: url) else { return nil }
        return try? JSONDecoder().decode(T.self, from: data)
    }

    private func save<T: Encodable>(_ value: T, as fileName: String) {
        let url = baseDirectory.appendingPathComponent(fileName)
        let data = try? JSONEncoder().encode(value)
        try? data?.write(to: url, options: [.atomic])
    }

    private func remove(_ fileName: String) {
        let url = baseDirectory.appendingPathComponent(fileName)
        try? fileManager.removeItem(at: url)
    }
}
