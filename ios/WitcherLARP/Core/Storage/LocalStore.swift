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

    func loadSnapshot() -> PlayerSnapshot? {
        load("snapshot.json")
    }

    func saveSnapshot(_ snapshot: PlayerSnapshot) {
        save(snapshot, as: "snapshot.json")
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
}
