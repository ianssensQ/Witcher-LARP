import Foundation

struct LarpAPIClient {
    var baseURL: URL
    var session: URLSession = .shared

    func fetchHealth() async throws -> HealthResponse {
        try await decode(HealthResponse.self, from: URLRequest(url: endpoint("/health")))
    }

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

    func sync(
        events: [QueuedEvent],
        deviceId: String,
        playerCode: String,
        actorId: String,
        actorType: String
    ) async throws -> SyncResponse {
        let request = try jsonRequest(
            path: "/api/events/sync",
            method: "POST",
            body: SyncRequest(deviceId: deviceId, actorId: actorId, actorType: actorType, events: events),
            playerCode: playerCode
        )
        return try await decode(SyncResponse.self, from: request)
    }

    func lookupQR(
        code: String,
        playerId: String,
        deviceId: String,
        source: QRInputSource,
        playerCode: String,
        physicalPresenceConfirmed: Bool = true
    ) async throws -> JSONValue {
        let request = try jsonRequest(
            path: "/api/qr/lookup",
            method: "POST",
            body: QrLookupRequest(
                code: code,
                playerId: playerId,
                deviceId: deviceId,
                source: source.apiValue,
                physicalPresenceConfirmed: physicalPresenceConfirmed
            ),
            playerCode: playerCode
        )
        return try await decode(JSONValue.self, from: request)
    }

    func acceptOrder(_ order: OrderSummary, player: PlayerProfile, playerCode: String) async throws -> JSONValue {
        let request = try jsonRequest(
            path: "/api/lords/\(order.lordId)/orders",
            method: "POST",
            body: OrderActionRequest(
                action: "accept",
                orderId: order.orderId,
                playerId: player.playerId,
                resultEventId: nil,
                source: "player_app"
            ),
            playerCode: playerCode
        )
        return try await decode(JSONValue.self, from: request)
    }

    func submitOrder(
        _ order: OrderSummary,
        player: PlayerProfile,
        resultEventId: String,
        playerCode: String
    ) async throws -> JSONValue {
        let request = try jsonRequest(
            path: "/api/lords/\(order.lordId)/orders",
            method: "POST",
            body: OrderActionRequest(
                action: "submit_success",
                orderId: order.orderId,
                playerId: player.playerId,
                resultEventId: resultEventId,
                source: "player_app"
            ),
            playerCode: playerCode
        )
        return try await decode(JSONValue.self, from: request)
    }

    func fetchPvpTables() async throws -> PvpTablesResponse {
        try await decode(PvpTablesResponse.self, from: URLRequest(url: endpoint("/api/pvp/tables")))
    }

    func fetchPvpPlayerState(playerCode: String) async throws -> JSONValue {
        var request = URLRequest(url: endpoint("/api/pvp/player-state"))
        request.setValue(playerCode, forHTTPHeaderField: "X-Player-Code")
        return try await decode(JSONValue.self, from: request)
    }

    func createPvpChallenge(
        player: PlayerProfile,
        targetId: String,
        stakeAssetType: String,
        stakeAssetId: String,
        stakeQuantity: Int,
        playerCode: String
    ) async throws -> JSONValue {
        let normalizedStakeType = stakeAssetType.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        let normalizedStakeId = stakeAssetId.trimmingCharacters(in: .whitespacesAndNewlines)
        let normalizedQuantity = max(1, stakeQuantity)
        let stake: [String: JSONValue]
        if normalizedStakeType == "gold" {
            stake = [
                "asset_type": .string("gold"),
                "asset_id": .string("gold"),
                "amount": .int(normalizedQuantity),
                "transfer_on_finish": .bool(true)
            ]
        } else {
            stake = [
                "asset_type": .string(normalizedStakeType),
                "asset_id": .string(normalizedStakeId),
                "quantity": .int(normalizedQuantity),
                "transfer_on_finish": .bool(true)
            ]
        }
        let request = try jsonRequest(
            path: "/api/pvp/challenges",
            method: "POST",
            body: PvpChallengeRequest(
                challengerId: player.playerId,
                targetId: targetId,
                stake: stake,
                challengeId: "ios-gwent-\(UUID().uuidString)",
                mandatory: true,
                masterApproval: false,
                source: "ios_gwent_app"
            ),
            playerCode: playerCode
        )
        return try await decode(JSONValue.self, from: request)
    }

    func startPvpChallenge(
        challengeId: String,
        playerCode: String,
        mulligansByPlayer: [String: [String]]? = nil,
        deckIdsByPlayer: [String: String]? = nil,
        preferredStartingPlayerId: String? = nil
    ) async throws -> JSONValue {
        let request = try jsonRequest(
            path: "/api/pvp/challenges/\(challengeId)/start",
            method: "POST",
            body: PvpStartRequest(
                masterApproval: false,
                mulligansByPlayer: mulligansByPlayer,
                deckIdsByPlayer: deckIdsByPlayer,
                preferredStartingPlayerId: normalizedOptional(preferredStartingPlayerId),
                source: "ios_gwent_app"
            ),
            playerCode: playerCode
        )
        return try await decode(JSONValue.self, from: request)
    }

    func prepareGwentChallenge(
        challengeId: String,
        playerCode: String,
        mulligans: [String] = [],
        deckId: String? = nil,
        preferredStartingPlayerId: String? = nil
    ) async throws -> JSONValue {
        let request = try jsonRequest(
            path: "/api/pvp/challenges/\(challengeId)/ready",
            method: "POST",
            body: GwentPreparationRequest(
                mulligans: mulligans.isEmpty ? nil : mulligans,
                deckId: normalizedOptional(deckId),
                preferredStartingPlayerId: normalizedOptional(preferredStartingPlayerId),
                source: "ios_gwent_app"
            ),
            playerCode: playerCode
        )
        return try await decode(JSONValue.self, from: request)
    }

    func refusePvpChallenge(
        challengeId: String,
        player: PlayerProfile,
        reason: String,
        playerCode: String
    ) async throws -> JSONValue {
        let request = try jsonRequest(
            path: "/api/pvp/challenges/\(challengeId)/refusal",
            method: "POST",
            body: PvpRefusalRequest(
                reason: reason,
                actorId: player.playerId,
                source: "ios_gwent_app"
            ),
            playerCode: playerCode
        )
        return try await decode(JSONValue.self, from: request)
    }

    func startGwentBotMatch(
        playerCode: String,
        mulligans: [String] = [],
        deckId: String? = nil
    ) async throws -> JSONValue {
        let request = try jsonRequest(
            path: "/api/pvp/bot-match",
            method: "POST",
            body: GwentBotMatchRequest(
                mulligans: mulligans.isEmpty ? nil : mulligans,
                deckId: normalizedOptional(deckId),
                source: "ios_gwent_app"
            ),
            playerCode: playerCode
        )
        return try await decode(JSONValue.self, from: request)
    }

    func saveGwentDeck(
        playerCode: String,
        deckId: String?,
        leaderCardId: String,
        cardIds: [String]
    ) async throws -> JSONValue {
        let request = try jsonRequest(
            path: "/api/pvp/decks",
            method: "POST",
            body: GwentDeckSaveRequest(
                deckId: normalizedOptional(deckId),
                leaderCardId: leaderCardId.trimmingCharacters(in: .whitespacesAndNewlines),
                cardIds: cardIds.map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }.filter { !$0.isEmpty },
                source: "ios_gwent_app"
            ),
            playerCode: playerCode
        )
        return try await decode(JSONValue.self, from: request)
    }

    func recordGwentAction(
        matchId: String,
        action: String,
        roundNumber: Int,
        cardId: String?,
        row: String?,
        targetCardId: String?,
        discardCardIds: [String]?,
        reviveCardId: String?,
        reviveRow: String?,
        actionId: String?,
        playerCode: String
    ) async throws -> JSONValue {
        let normalizedActionId = actionId?.trimmingCharacters(in: .whitespacesAndNewlines)
        let requestActionId: String
        if let normalizedActionId, !normalizedActionId.isEmpty {
            requestActionId = normalizedActionId
        } else {
            requestActionId = "ios-gwent-action-\(UUID().uuidString)"
        }

        let request = try jsonRequest(
            path: "/api/pvp/matches/\(matchId)/actions",
            method: "POST",
            body: GwentActionRequest(
                action: action,
                roundNumber: roundNumber,
                cardId: cardId?.trimmingCharacters(in: .whitespacesAndNewlines),
                row: row?.trimmingCharacters(in: .whitespacesAndNewlines),
                targetCardId: targetCardId?.trimmingCharacters(in: .whitespacesAndNewlines),
                discardCardIds: discardCardIds?.map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }.filter { !$0.isEmpty },
                reviveCardId: reviveCardId?.trimmingCharacters(in: .whitespacesAndNewlines),
                reviveRow: reviveRow?.trimmingCharacters(in: .whitespacesAndNewlines),
                actionId: requestActionId,
                source: "ios_gwent_app"
            ),
            playerCode: playerCode
        )
        return try await decode(JSONValue.self, from: request)
    }

    func finishGwentMatch(
        matchId: String,
        winnerId: String?,
        playerCode: String
    ) async throws -> JSONValue {
        let normalizedWinner = winnerId?.trimmingCharacters(in: .whitespacesAndNewlines)
        let request = try jsonRequest(
            path: "/api/pvp/matches/\(matchId)/finish",
            method: "POST",
            body: GwentFinishRequest(
                winnerId: normalizedWinner?.isEmpty == true ? nil : normalizedWinner,
                outcome: "normal",
                source: "ios_gwent_app"
            ),
            playerCode: playerCode
        )
        return try await decode(JSONValue.self, from: request)
    }

    func createTradeTransfer(
        from player: PlayerProfile,
        toPlayerId: String,
        assetType: String,
        assetId: String,
        quantity: Int,
        priceGold: Int,
        mode: String,
        playerCode: String
    ) async throws -> JSONValue {
        let request = try jsonRequest(
            path: "/api/trade-transfers",
            method: "POST",
            body: TradeCreateRequest(
                fromPlayerId: player.playerId,
                toPlayerId: toPlayerId,
                assetType: assetType,
                assetId: assetId,
                quantity: quantity,
                priceGold: priceGold,
                mode: mode,
                transferId: "ios-trade-\(UUID().uuidString)",
                autoAccept: false,
                source: "ios_player_app"
            ),
            playerCode: playerCode
        )
        return try await decode(JSONValue.self, from: request)
    }

    func sellMaterial(
        player: PlayerProfile,
        materialId: String,
        quantity: Int,
        playerCode: String
    ) async throws -> JSONValue {
        let request = try jsonRequest(
            path: "/api/players/\(player.playerId)/material-market/sell",
            method: "POST",
            body: MaterialMarketSellRequest(
                materialId: materialId,
                quantity: max(1, quantity),
                saleId: "ios-material-sale-\(UUID().uuidString)",
                source: "ios_player_app"
            ),
            playerCode: playerCode
        )
        return try await decode(JSONValue.self, from: request)
    }

    func acceptTradeTransfer(
        transferId: String,
        player: PlayerProfile,
        playerCode: String
    ) async throws -> JSONValue {
        let request = try jsonRequest(
            path: "/api/trade-transfers/\(transferId)/accept",
            method: "POST",
            body: TradeAcceptRequest(acceptedByPlayerId: player.playerId, source: "ios_player_app"),
            playerCode: playerCode
        )
        return try await decode(JSONValue.self, from: request)
    }

    func declineTradeTransfer(
        transferId: String,
        player: PlayerProfile,
        reason: String,
        playerCode: String
    ) async throws -> JSONValue {
        let request = try jsonRequest(
            path: "/api/trade-transfers/\(transferId)/decline",
            method: "POST",
            body: TradeDeclineRequest(
                declinedByPlayerId: player.playerId,
                reason: reason,
                source: "ios_player_app"
            ),
            playerCode: playerCode
        )
        return try await decode(JSONValue.self, from: request)
    }

    private func jsonRequest<T: Encodable>(
        path: String,
        method: String,
        body: T,
        playerCode: String? = nil
    ) throws -> URLRequest {
        let url = endpoint(path)
        var request = URLRequest(url: url)
        request.httpMethod = method
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        if let playerCode {
            request.setValue(playerCode, forHTTPHeaderField: "X-Player-Code")
        }
        request.httpBody = try JSONEncoder.larp.encode(body)
        return request
    }

    private func endpoint(_ path: String) -> URL {
        var url = baseURL
        for component in path.split(separator: "/") {
            url.appendPathComponent(String(component))
        }
        return url
    }

    private func normalizedOptional(_ value: String?) -> String? {
        let trimmed = value?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        return trimmed.isEmpty ? nil : trimmed
    }

    private func decode<T: Decodable>(_ type: T.Type, from request: URLRequest) async throws -> T {
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else { throw APIError.invalidResponse }
        guard (200..<300).contains(http.statusCode) else {
            throw APIError.httpStatus(http.statusCode, detail: errorDetail(from: data))
        }
        return try JSONDecoder.larp.decode(T.self, from: data)
    }

    private func errorDetail(from data: Data) -> String? {
        guard !data.isEmpty else { return nil }
        if let payload = try? JSONDecoder.larp.decode(JSONValue.self, from: data),
           let object = payload.objectValue {
            if let detail = object["detail"], let text = readableErrorDetail(detail) {
                return text
            }
            if let message = object["message"], let text = readableErrorDetail(message) {
                return text
            }
            if let error = object["error"], let text = readableErrorDetail(error) {
                return text
            }
        }
        let fallback = String(data: data, encoding: .utf8)?
            .trimmingCharacters(in: .whitespacesAndNewlines)
        guard let fallback, !fallback.isEmpty else { return nil }
        return String(fallback.prefix(240))
    }

    private func readableErrorDetail(_ value: JSONValue) -> String? {
        if let text = value.stringValue?.trimmingCharacters(in: .whitespacesAndNewlines), !text.isEmpty {
            return text
        }
        if let array = value.arrayValue {
            let text = array
                .map(\.displayText)
                .filter { !$0.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty }
                .joined(separator: ", ")
                .trimmingCharacters(in: .whitespacesAndNewlines)
            return text.isEmpty ? nil : text
        }
        let text = value.displayText.trimmingCharacters(in: .whitespacesAndNewlines)
        return text.isEmpty || text == "null" ? nil : text
    }
}

enum APIError: Error {
    case invalidURL
    case invalidResponse
    case httpStatus(Int, detail: String?)
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
