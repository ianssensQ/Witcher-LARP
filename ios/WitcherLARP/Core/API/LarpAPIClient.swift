import Foundation

struct LarpAPIClient {
    var baseURL: URL
    var session: URLSession = .shared

    func login(playerCode: String, deviceId: String) async throws -> LoginResponse {
        let request = try jsonRequest(
            path: "/api/auth/player-code",
            method: "POST",
            body: LoginRequest(playerCode: playerCode, deviceId: deviceId)
        )
        return try await decode(LoginResponse.self, from: request)
    }

    func fetchSnapshot(playerCode: String) async throws -> PlayerSnapshot {
        var components = URLComponents(url: endpoint("/api/content/snapshot"), resolvingAgainstBaseURL: false)!
        components.queryItems = [URLQueryItem(name: "player_code", value: playerCode)]
        guard let url = components.url else { throw APIError.invalidURL }
        return try await decode(PlayerSnapshot.self, from: URLRequest(url: url))
    }

    func sync(events: [QueuedEvent], deviceId: String) async throws -> SyncResponse {
        let request = try jsonRequest(
            path: "/api/events/sync",
            method: "POST",
            body: SyncRequest(deviceId: deviceId, events: events)
        )
        return try await decode(SyncResponse.self, from: request)
    }

    func lookupQR(
        code: String,
        playerCode: String,
        playerId: String?,
        deviceId: String,
        source: String,
        physicalPresenceConfirmed: Bool = true
    ) async throws -> QRLookupResponse {
        var request = try jsonRequest(
            path: "/api/qr/lookup",
            method: "POST",
            body: QRLookupRequest(
                code: code,
                playerId: playerId,
                deviceId: deviceId,
                source: source,
                physicalPresenceConfirmed: physicalPresenceConfirmed
            )
        )
        request.setValue(playerCode, forHTTPHeaderField: "X-Player-Code")
        return try await decode(QRLookupResponse.self, from: request)
    }

    private func jsonRequest<T: Encodable>(path: String, method: String, body: T) throws -> URLRequest {
        let url = endpoint(path)
        var request = URLRequest(url: url)
        request.httpMethod = method
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder.larp.encode(body)
        return request
    }

    private func endpoint(_ path: String) -> URL {
        baseURL.appendingPathComponent(path.trimmingCharacters(in: CharacterSet(charactersIn: "/")))
    }

    private func decode<T: Decodable>(_ type: T.Type, from request: URLRequest) async throws -> T {
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else { throw APIError.invalidResponse }
        guard (200..<300).contains(http.statusCode) else { throw APIError.httpStatus(http.statusCode) }
        return try JSONDecoder.larp.decode(T.self, from: data)
    }
}

enum APIError: Error {
    case invalidURL
    case invalidResponse
    case httpStatus(Int)
}

private extension JSONEncoder {
    static var larp: JSONEncoder {
        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        encoder.outputFormatting = [.sortedKeys]
        return encoder
    }
}

private extension JSONDecoder {
    static var larp: JSONDecoder {
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        return decoder
    }
}
