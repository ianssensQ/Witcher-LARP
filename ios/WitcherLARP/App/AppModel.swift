import Foundation
import CryptoKit

@MainActor
final class AppModel: ObservableObject {
    @Published var serverURL: URL
    @Published var playerCode: String
    @Published var snapshot: PlayerSnapshot?
    @Published var pendingEvents: [QueuedEvent] = []
    @Published var syncState: SyncState = .offline
    @Published var errorMessage: String?
    @Published var infoMessage: String?
    @Published var activePVEMission: PvESceneDraft?
    @Published var lastPvEResult: PvESceneDraft?
    @Published var lastQRLookup: JSONValue?
    @Published var pvpTables: PvpTablesResponse?
    @Published var pvpPlayerState: JSONValue?
    @Published var lastPvpActionResult: JSONValue?
    @Published var runtimeGwentDecks: [GwentDeck] = []
    @Published var lastTradeResult: JSONValue?
    @Published var lastMaterialMarketResult: JSONValue?
    @Published var localUnlockedActIds: Set<String> = []
    @Published var serverHealth: HealthResponse?
    @Published var serverHealthChecked = false

    private let store = LocalStore.shared
    private let queue = EventQueueStore.shared
    private var api: LarpAPIClient
    private let deviceId: String
    static let canonicalStats = ["Сила", "Ловкость", "Разум", "Харизма", "Воля"]
    static let startStatBudget = 7
    static let startStatMax = 3
    static let defaultRuntimeStatMax = 7
    static let defaultServerURLString = "http://192.168.68.118:8002"
    private static let staleDefaultServerURLStrings: Set<String> = [
        "http://127.0.0.1:8000",
        "http://192.168.1.9:8000"
    ]
    private let requiredAPIRevision = "ios-gwent-pvp-v1"
    private let requiredGwentFeatures: Set<String> = [
        "ios_gwent_bot_match",
        "ios_gwent_deckbuilder",
        "ios_gwent_pvp_actions",
        "ios_gwent_preflight",
        "ios_gwent_scoiatael_first_turn"
    ]
    let screenshotInitialTab: String?
    let screenshotShowsQR: Bool
    let screenshotShowsGwentTable: Bool
    let demoSnapshotMode: Bool

    var player: PlayerProfile? {
        snapshot?.currentPlayer
    }

    var effectiveUnlockedActIds: Set<String> {
        var ids: Set<String> = ["act1"]
        ids.formUnion(snapshot?.actUnlockState.arrayStrings("unlocked_act_ids") ?? [])
        ids.formUnion(localUnlockedActIds)
        return ids
    }

    var revealedActIds: Set<String> {
        Set(snapshot?.actUnlockState.arrayStrings("revealed_act_ids") ?? [])
    }

    var hasPlayableSession: Bool {
        snapshot != nil && !playerCode.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
    }

    var screenshotMode: Bool {
        demoSnapshotMode || screenshotInitialTab != nil || screenshotShowsQR || screenshotShowsGwentTable
    }

    var gwentUXEnabled: Bool {
        true
    }

    var serverIsReachable: Bool {
        serverHealth?.status?.lowercased() == "ok"
    }

    var needsServerSetupForGwent: Bool {
        !screenshotMode && serverHealthChecked && !serverSupportsGwent
    }

    var serverSupportsGwent: Bool {
        guard let api = serverHealth?.api else { return false }
        let features = Set(api.features ?? [])
        return api.revision == requiredAPIRevision && requiredGwentFeatures.isSubset(of: features)
    }

    var runtimeStatMax: Int {
        let configured = snapshot?.checks.xpRules.first?.int("max_stat") ?? 0
        return configured > 0 ? configured : Self.defaultRuntimeStatMax
    }

    var serverConnectionLabel: String {
        guard serverHealth != nil else {
            return "Проверяем связь с сервером игры..."
        }
        if serverIsReachable {
            return "Сервер игры доступен."
        }
        return "Сервер ответил, но не готов. Проверь базу и импорт данных."
    }

    init() {
        #if DEBUG
        let launchArguments = ProcessInfo.processInfo.arguments
        if let tabArgumentIndex = launchArguments.firstIndex(of: "--initial-tab"),
           launchArguments.indices.contains(launchArguments.index(after: tabArgumentIndex)) {
            self.screenshotInitialTab = launchArguments[launchArguments.index(after: tabArgumentIndex)]
        } else {
            self.screenshotInitialTab = nil
        }
        self.screenshotShowsQR = launchArguments.contains("--show-qr")
        self.screenshotShowsGwentTable = launchArguments.contains("--show-gwent-table")
        self.demoSnapshotMode = launchArguments.contains("--demo-snapshot")
        #else
        self.screenshotInitialTab = nil
        self.screenshotShowsQR = false
        self.screenshotShowsGwentTable = false
        self.demoSnapshotMode = false
        #endif
        let defaultURL = URL(string: Self.defaultServerURLString)!
        let storedURL = LocalStore.shared.loadServerURL()
        let startupURL = Self.startupServerURL(storedURL: storedURL, defaultURL: defaultURL)
        let didOverrideStoredServerURL = storedURL?.absoluteString != startupURL.absoluteString
        LocalStore.shared.saveServerURL(startupURL)
        self.serverURL = startupURL
        self.playerCode = LocalStore.shared.loadPlayerCode() ?? ""
        self.api = LarpAPIClient(baseURL: startupURL)
        self.deviceId = LocalStore.shared.loadDeviceId()
        self.snapshot = LocalStore.shared.loadSnapshot()
        self.pendingEvents = EventQueueStore.shared.loadEvents()
        self.localUnlockedActIds = LocalStore.shared.loadUnlockedActIds()
        if didOverrideStoredServerURL {
            self.infoMessage = "Адрес сервера автоматически выставлен: \(startupURL.absoluteString)"
        }
        #if DEBUG
        print("WitcherLARP startup server URL: \(startupURL.absoluteString)")
        #endif
        #if DEBUG
        if demoSnapshotMode {
            loadDemoSnapshot()
        }
        if launchArguments.contains("--demo-queue") {
            seedDemoQueue()
        }
        #endif
    }

    func updateServerURL(_ url: URL) {
        serverURL = url
        api = LarpAPIClient(baseURL: url)
        store.saveServerURL(url)
        serverHealth = nil
        serverHealthChecked = false
        infoMessage = "Адрес сервера обновлен. Проверь связь перед входом."
        errorMessage = nil
    }

    @discardableResult
    func updateServerURL(from text: String) -> Bool {
        guard let url = Self.normalizedServerURL(from: text) else {
            errorMessage = "Адрес сервера должен выглядеть как \(Self.defaultServerURLString)"
            infoMessage = nil
            return false
        }
        updateServerURL(url)
        return true
    }

    func resetLocalSession() {
        store.clearPlayerSession()
        queue.clear()
        playerCode = ""
        snapshot = nil
        pendingEvents = []
        localUnlockedActIds = []
        pvpTables = nil
        pvpPlayerState = nil
        lastPvpActionResult = nil
        runtimeGwentDecks = []
        lastPvEResult = nil
        activePVEMission = nil
        lastQRLookup = nil
        lastTradeResult = nil
        lastMaterialMarketResult = nil
        syncState = .offline
        infoMessage = "Локальная сессия сброшена. Войди по коду персонажа заново."
        errorMessage = nil
    }

    func checkServerHealth() async {
        do {
            let health = try await api.fetchHealth()
            serverHealth = health
            serverHealthChecked = true
            if serverIsReachable {
                infoMessage = "Сервер игры доступен: \(serverURL.absoluteString)"
                errorMessage = nil
            } else {
                errorMessage = "Сервер ответил, но база или импорт не готовы. Проверь мастерский FastAPI на ноутбуке."
            }
        } catch {
            serverHealth = nil
            serverHealthChecked = true
            errorMessage = "Не могу подключиться к серверу игры. Проверь Wi-Fi и адрес сервера в настройках."
        }
    }

    func loadDemoSnapshot() {
        do {
            let data = Data(Self.demoSnapshotJSON.utf8)
            let demo = try JSONDecoder().decode(PlayerSnapshot.self, from: data)
            let gwentData = Data(Self.demoGwentStateJSON.utf8)
            playerCode = "WC-WOLF-6GF4"
            snapshot = demo
            runtimeGwentDecks = []
            localUnlockedActIds = []
            lastPvpActionResult = try JSONDecoder().decode(JSONValue.self, from: gwentData)
            pvpPlayerState = nil
            activePVEMission = nil
            store.savePlayerCode(playerCode)
            store.saveSnapshot(demo)
            store.saveUnlockedActIds(localUnlockedActIds)
            syncState = .offline
            infoMessage = "Открыт локальный демо-дневник для Xcode просмотра"
            errorMessage = nil
        } catch {
            errorMessage = readable(error)
        }
    }

    private func seedDemoQueue() {
        guard let player else { return }
        let proofId = UUID(uuidString: "11111111-1111-4111-8111-111111111111")!
        let orderId = UUID(uuidString: "22222222-2222-4222-8222-222222222222")!
        let createdAt = Date(timeIntervalSince1970: 1_780_000_000)
        let pveEvent = QueuedEvent(
            id: proofId,
            playerId: player.playerId,
            clientSequence: 1,
            createdAt: createdAt,
            eventType: "pve_completed",
            payload: [
                "player_id": .string(player.playerId),
                "qr_id": .string("qr_a1_002"),
                "scenario_id": .string("scn_a1_002"),
                "result": .string("success"),
                "roll": .int(16),
                "created_offline": .bool(true)
            ]
        )
        let submissionEvent = QueuedEvent(
            id: orderId,
            playerId: player.playerId,
            clientSequence: 2,
            createdAt: createdAt.addingTimeInterval(60),
            eventType: "order_submission",
            payload: [
                "player_id": .string(player.playerId),
                "order_id": .string("order_demo_active"),
                "object_id": .string("qr_a1_002"),
                "result_event_id": .string(proofId.uuidString),
                "proof_qr_id": .string("qr_a1_002"),
                "created_offline": .bool(true)
            ]
        )
        queue.replaceEvents([pveEvent, submissionEvent])
        pendingEvents = queue.loadEvents()
        syncState = .pending
        infoMessage = "Demo Sync Queue подготовлена для скриншотов"
    }

    func login(playerCode rawCode: String) async {
        let code = rawCode.trimmingCharacters(in: .whitespacesAndNewlines).uppercased()
        guard !code.isEmpty else { return }
        do {
            syncState = .syncing
            await checkServerHealth()
            if errorMessage != nil {
                syncState = .syncError
                return
            }
            _ = try await api.login(playerCode: code, deviceId: deviceId)
            let loadedSnapshot = try await api.fetchSnapshot(playerCode: code)
            playerCode = code
            snapshot = loadedSnapshot
            runtimeGwentDecks = []
            activePVEMission = nil
            lastPvEResult = nil
            store.savePlayerCode(code)
            store.saveSnapshot(loadedSnapshot)
            syncState = .synced
            infoMessage = "Игровой дневник загружен."
            errorMessage = nil
        } catch {
            syncState = .syncError
            errorMessage = readable(error)
        }
    }

    func refreshSnapshot() async {
        guard !playerCode.isEmpty else { return }
        do {
            syncState = .syncing
            let loadedSnapshot = try await api.fetchSnapshot(playerCode: playerCode)
            snapshot = loadedSnapshot
            activePVEMission = nil
            store.saveSnapshot(loadedSnapshot)
            syncState = pendingEvents.isEmpty ? .synced : .pending
            infoMessage = "Игровой дневник обновлен."
            errorMessage = nil
        } catch {
            syncState = .syncError
            errorMessage = readable(error)
        }
    }

    func appendQRAttempt(qrId: String, source: QRInputSource, reviewReason: String? = nil) {
        guard let player else { return }
        var payload: [String: JSONValue] = [
            "player_id": .string(player.playerId),
            "manual_code": .string(qrId),
            "normalized_code": .string(qrId.trimmingCharacters(in: .whitespacesAndNewlines).uppercased()),
            "source": .string(source.apiValue),
            "physical_presence_confirmed": .bool(true),
            "local_status": .string(reviewReason == nil ? "started" : "needs_master_review")
        ]
        if let reviewReason {
            payload["review_reason"] = .string(reviewReason)
        }
        queue.append(queue.makeEvent(playerId: player.playerId, eventType: "qr_attempt", payload: payload))
        pendingEvents = queue.loadEvents()
        syncState = .pending
    }

    func lookupQR(
        code rawCode: String,
        source: QRInputSource,
        physicalPresenceConfirmed: Bool
    ) async {
        guard let player, !playerCode.isEmpty else {
            errorMessage = "Нужен вход по коду игрока перед проверкой QR."
            return
        }
        let code = rawCode.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !code.isEmpty else { return }

        do {
            let result = try await api.lookupQR(
                code: code,
                playerId: player.playerId,
                deviceId: deviceId,
                source: source,
                playerCode: playerCode,
                physicalPresenceConfirmed: physicalPresenceConfirmed
            )
            lastQRLookup = result
            infoMessage = "Код проверен на сервере."
            errorMessage = nil
        } catch {
            errorMessage = readable(error)
        }
    }

    @discardableResult
    func beginPVE(code rawCode: String, source: QRInputSource) -> Bool {
        guard let snapshot, let player = snapshot.currentPlayer else { return false }
        let normalized = rawCode.trimmingCharacters(in: .whitespacesAndNewlines).uppercased()
        guard let qr = snapshot.qrObjects.first(where: {
            $0.manualCode.uppercased() == normalized || $0.qrId.uppercased() == normalized
        }) else {
            appendQRAttempt(qrId: normalized, source: source, reviewReason: "unknown_qr")
            errorMessage = "Код не найден в сохраненных данных игры. Попытка уйдет мастеру на проверку."
            return false
        }
        guard effectiveUnlockedActIds.contains(qr.actId) else {
            appendQRAttempt(qrId: normalized, source: source, reviewReason: "future_act_locked")
            errorMessage = "Этот объект из будущего акта. Нужна синхронизация или код мастера после объявления акта."
            return false
        }
        guard let scenario = snapshot.pveScenarios.first(where: { $0.scenarioId == qr.scenarioId }) else {
            appendQRAttempt(qrId: normalized, source: source, reviewReason: "missing_local_scenario")
            errorMessage = "Сцена не найдена в сохраненных данных игры. Попытка уйдет мастеру на проверку."
            return false
        }

        let reward = snapshot.rewards.first(where: { $0.rewardId == scenario.rewardId })
        let draft = PvESceneDraft.start(
            qr: qr,
            scenario: scenario,
            reward: reward,
            player: player,
            source: source
        )
        activePVEMission = draft
        lastPvEResult = nil
        infoMessage = "Миссия открыта: \(qr.manualCode)."
        errorMessage = nil
        return true
    }

    func choosePVEOption(_ choiceId: String) {
        guard var draft = activePVEMission else { return }
        guard let updated = draft.selecting(choiceId: choiceId) else { return }
        draft = updated
        activePVEMission = draft
        infoMessage = draft.isReadyForChecks ? "Выбор сделан. Начинаются испытания." : "Выбор сохранен."
        errorMessage = nil
    }

    func rollNextPVECheck() {
        guard var draft = activePVEMission else { return }
        guard let updated = draft.rollingNextCheck() else { return }
        draft = updated
        activePVEMission = draft
        if draft.isComplete {
            finishPVE(draft)
        } else {
            infoMessage = "Проверка сохранена: \(draft.lastRollSummary)."
            errorMessage = nil
        }
    }

    private func finishPVE(_ draft: PvESceneDraft) {
        let event = queue.makeEvent(
            playerId: draft.player.playerId,
            eventType: "pve_completed",
            payload: draft.eventPayload
        )
        queue.append(event)
        lastPvEResult = draft
        activePVEMission = nil
        pendingEvents = queue.loadEvents()
        syncState = .pending
        infoMessage = "Результат миссии сохранен на телефоне: \(draft.resultLabel)."
        errorMessage = nil
    }

    func initialStatPointsRemaining(for player: PlayerProfile) -> Int {
        max(0, Self.startStatBudget - player.stats.values.reduce(0, +))
    }

    func allocatableStatPoints(for player: PlayerProfile) -> Int {
        initialStatPointsRemaining(for: player) + max(0, player.unspentStatPoints)
    }

    func canAllocateStat(_ stat: String, for player: PlayerProfile) -> Bool {
        let current = player.stats[stat] ?? 0
        if initialStatPointsRemaining(for: player) > 0 {
            return current < Self.startStatMax
        }
        return player.unspentStatPoints > 0 && current < runtimeStatMax
    }

    func allocateStatPoint(_ stat: String) {
        guard let snapshot, let player = snapshot.currentPlayer else { return }
        guard Self.canonicalStats.contains(stat), canAllocateStat(stat, for: player) else {
            errorMessage = "Этот стат сейчас нельзя повысить."
            return
        }
        let initialRemaining = initialStatPointsRemaining(for: player)
        let allocationType = initialRemaining > 0 ? "initial" : "level_up"
        let unspentAfter = allocationType == "level_up"
            ? max(0, player.unspentStatPoints - 1)
            : player.unspentStatPoints
        let updatedPlayer = player.applyingStatDelta(stat, unspentStatPointsAfter: unspentAfter)
        let updatedSnapshot = snapshot.updatingCurrentPlayer(updatedPlayer)
        self.snapshot = updatedSnapshot
        store.saveSnapshot(updatedSnapshot)
        let statsAfterPayload: [String: JSONValue] = Dictionary(uniqueKeysWithValues: Self.canonicalStats.map {
            ($0, JSONValue.int(updatedPlayer.stats[$0] ?? 0))
        })

        queue.append(queue.makeEvent(
            playerId: player.playerId,
            eventType: "player_stats_allocated",
            payload: [
                "player_id": .string(player.playerId),
                "allocation_type": .string(allocationType),
                "stat_deltas": .object([stat: .int(1)]),
                "stats_after": .object(statsAfterPayload),
                "unspent_stat_points_after": .int(unspentAfter),
                "source": .string("ios_player_app"),
                "created_offline": .bool(true),
                "device_id": .string(deviceId)
            ]
        ))
        pendingEvents = queue.loadEvents()
        syncState = .pending
        infoMessage = "\(stat) повышен. Изменение уйдет при следующей синхронизации."
        errorMessage = nil
    }

    func unlockAct(actId rawActId: String, code rawCode: String) {
        guard let player else {
            errorMessage = "Нужен вход по коду игрока перед открытием акта."
            return
        }
        guard let snapshot else {
            errorMessage = "Нужны сохраненные данные игры с раскрытыми мастерскими кодами."
            return
        }

        let actId = rawActId.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        let code = rawCode.trimmingCharacters(in: .whitespacesAndNewlines).uppercased()
        guard !actId.isEmpty, !code.isEmpty else {
            errorMessage = "Укажи акт и код мастера."
            return
        }

        guard let row = snapshot.actUnlockCodes.first(where: {
            $0.string("act_id").caseInsensitiveCompare(actId) == .orderedSame
        }) else {
            errorMessage = "В сохраненных данных нет кода для \(actId). Обнови дневник после объявления мастера."
            return
        }

        let revealed = row.string("revealed") == "true"
        let visibleCode = row.string("code").trimmingCharacters(in: .whitespacesAndNewlines).uppercased()
        let expectedHash = row.string("code_sha256").trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        let suppliedHash = sha256Hex(code)
        guard revealed, (!visibleCode.isEmpty || !expectedHash.isEmpty) else {
            errorMessage = "Код для \(actId) еще не раскрыт. Нужна синхронизация после мастерского объявления."
            return
        }
        guard visibleCode == code || expectedHash == suppliedHash else {
            errorMessage = "Код мастера не подходит для \(actId)."
            return
        }

        localUnlockedActIds.insert(actId)
        store.saveUnlockedActIds(localUnlockedActIds)

        let alreadyQueued = pendingEvents.contains { event in
            event.eventType == "act_unlocked_offline" && event.payload.string("act_id") == actId
        }
        if !alreadyQueued {
            queue.append(queue.makeEvent(
                playerId: player.playerId,
                eventType: "act_unlocked_offline",
                payload: [
                    "player_id": .string(player.playerId),
                    "act_id": .string(actId),
                    "code_sha256": .string(suppliedHash),
                    "source": .string("ios_player_app"),
                    "unlock_source": .string("master_unlock_code"),
                    "created_offline": .bool(true),
                    "device_id": .string(deviceId)
                ]
            ))
        }
        pendingEvents = queue.loadEvents()
        syncState = .pending
        infoMessage = alreadyQueued
            ? "\(actId) уже открыт на этом телефоне; событие синхронизации уже в очереди."
            : "\(actId) открыт на этом телефоне; событие синхронизации добавлено."
        errorMessage = nil
    }

    func syncPendingEvents() async {
        let events = queue.loadEvents()
        guard !events.isEmpty else {
            syncState = .synced
            return
        }
        guard let player, !playerCode.isEmpty else {
            syncState = .syncError
            errorMessage = "Нужен вход по коду игрока перед синхронизацией."
            return
        }

        do {
            syncState = .syncing
            let response = try await api.sync(
                events: events,
                deviceId: deviceId,
                playerCode: playerCode,
                actorId: player.playerId,
                actorType: player.roleType
            )
            queue.applySyncResults(response.results)
            pendingEvents = queue.loadEvents()
            syncState = pendingEvents.isEmpty ? .synced : .needsReview
            infoMessage = syncSummary(response.results)
            errorMessage = nil
        } catch {
            syncState = .syncError
            errorMessage = readable(error)
        }
    }

    func acceptOrder(_ order: OrderSummary) async {
        guard let player, !playerCode.isEmpty else { return }
        do {
            _ = try await api.acceptOrder(order, player: player, playerCode: playerCode)
            infoMessage = "Заказ принят: \(order.objectLabel)"
            await refreshSnapshot()
        } catch {
            errorMessage = readable(error)
        }
    }

    func submitOrder(_ order: OrderSummary) async {
        guard let player, !playerCode.isEmpty else { return }
        let events = queue.loadEvents()
        guard let proofEvent = events.last(where: {
            $0.eventType == "pve_completed"
                && $0.payload.string("qr_id") == order.objectId
                && $0.payload.string("player_id", default: player.playerId) == player.playerId
        }) else {
            errorMessage = "Для сдачи заказа сначала пройди QR/PvE на объекте «\(order.objectLabel)»."
            return
        }
        let alreadyQueued = events.contains { event in
            event.eventType == "order_submission" && event.payload.string("order_id") == order.orderId
        }
        if !alreadyQueued {
            queue.append(queue.makeEvent(
                playerId: player.playerId,
                eventType: "order_submission",
                payload: [
                    "player_id": .string(player.playerId),
                    "order_id": .string(order.orderId),
                    "object_id": .string(order.objectId),
                    "result_event_id": .string(proofEvent.id.uuidString),
                    "proof_qr_id": .string(proofEvent.payload.string("qr_id")),
                    "source": .string("ios_player_app"),
                    "created_offline": .bool(true),
                    "device_id": .string(deviceId)
                ]
            ))
        }
        pendingEvents = queue.loadEvents()
        syncState = .pending
        infoMessage = alreadyQueued
            ? "Сдача заказа уже есть в очереди синхронизации."
            : "Сдача заказа сохранена на телефоне и отправится через синхронизацию."
        errorMessage = nil
    }

    func refreshPvpTables() async {
        guard await ensureGwentServerReady() else { return }
        do {
            pvpTables = try await api.fetchPvpTables()
            if !playerCode.isEmpty {
                pvpPlayerState = try await api.fetchPvpPlayerState(playerCode: playerCode)
            }
            infoMessage = "PvP/Gwent столы обновлены"
        } catch {
            errorMessage = readable(error)
        }
    }

    func refreshPvpState(silent: Bool = false) async {
        guard !playerCode.isEmpty else {
            if !silent {
                errorMessage = "Нужен вход по коду игрока перед обновлением Гвинта."
            }
            return
        }
        guard await ensureGwentServerReady() else { return }
        do {
            pvpPlayerState = try await api.fetchPvpPlayerState(playerCode: playerCode)
            if !silent {
                infoMessage = "Состояние Гвинта обновлено"
            }
            errorMessage = nil
        } catch {
            errorMessage = readable(error)
        }
    }

    func createPvpChallenge(
        targetId: String,
        stakeAssetType: String,
        stakeAssetId: String,
        stakeQuantity: Int = 1
    ) async {
        guard let player, !playerCode.isEmpty else {
            errorMessage = "Нужен вход по коду игрока перед Gwent challenge."
            return
        }
        let target = targetId.trimmingCharacters(in: .whitespacesAndNewlines)
        let stakeId = stakeAssetId.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !target.isEmpty, !stakeId.isEmpty, stakeQuantity > 0 else {
            errorMessage = "Укажи соперника и ставку для вызова на Гвинт."
            return
        }

        do {
            let result = try await api.createPvpChallenge(
                player: player,
                targetId: target,
                stakeAssetType: stakeAssetType,
                stakeAssetId: stakeId,
                stakeQuantity: stakeQuantity,
                playerCode: playerCode
            )
            lastPvpActionResult = result
            infoMessage = "Gwent challenge создан."
            errorMessage = nil
            await refreshPvpTables()
        } catch {
            errorMessage = readable(error)
        }
    }

    func startPvpChallenge(
        id challengeId: String,
        mulligans: [String] = [],
        deckId: String? = nil,
        preferredStartingPlayerId: String? = nil
    ) async {
        guard let player, !playerCode.isEmpty else {
            errorMessage = "Нужен вход по коду игрока перед стартом Gwent."
            return
        }
        let id = challengeId.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !id.isEmpty else { return }
        let selectedDeckId = deckId?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""

        do {
            let result = try await api.startPvpChallenge(
                challengeId: id,
                playerCode: playerCode,
                mulligansByPlayer: mulligans.isEmpty ? nil : [player.playerId: mulligans],
                deckIdsByPlayer: selectedDeckId.isEmpty ? nil : [player.playerId: selectedDeckId],
                preferredStartingPlayerId: preferredStartingPlayerId
            )
            lastPvpActionResult = result
            infoMessage = "Gwent challenge стартовал."
            errorMessage = nil
            await refreshPvpTables()
        } catch {
            errorMessage = readable(error)
        }
    }

    func prepareGwentChallenge(
        id challengeId: String,
        mulligans: [String] = [],
        deckId: String? = nil,
        preferredStartingPlayerId: String? = nil
    ) async {
        guard !playerCode.isEmpty else {
            errorMessage = "Нужен вход по коду игрока перед подготовкой Gwent."
            return
        }
        let id = challengeId.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !id.isEmpty else { return }

        do {
            let result = try await api.prepareGwentChallenge(
                challengeId: id,
                playerCode: playerCode,
                mulligans: mulligans,
                deckId: deckId,
                preferredStartingPlayerId: preferredStartingPlayerId
            )
            lastPvpActionResult = result
            infoMessage = result.objectValue?.object("match") == nil
                ? "Готовность к Gwent отправлена."
                : "Оба игрока готовы. Gwent стартовал."
            errorMessage = nil
            await refreshPvpTables()
        } catch {
            errorMessage = readable(error)
        }
    }

    func refusePvpChallenge(id challengeId: String, reason: String) async {
        guard let player, !playerCode.isEmpty else {
            errorMessage = "Нужен вход по коду игрока перед отказом от Gwent."
            return
        }
        let id = challengeId.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !id.isEmpty else { return }

        do {
            let result = try await api.refusePvpChallenge(
                challengeId: id,
                player: player,
                reason: reason.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ? "declined" : reason,
                playerCode: playerCode
            )
            lastPvpActionResult = result
            infoMessage = "Gwent refusal отправлен."
            errorMessage = nil
            await refreshPvpTables()
        } catch {
            errorMessage = readable(error)
        }
    }

    func startGwentBotMatch(mulligans: [String] = [], deckId: String? = nil) async {
        guard !playerCode.isEmpty else {
            errorMessage = "Нужен вход по коду игрока перед тренировкой Gwent."
            return
        }

        guard await ensureGwentServerReady() else { return }
        do {
            let result = try await api.startGwentBotMatch(
                playerCode: playerCode,
                mulligans: mulligans,
                deckId: deckId
            )
            lastPvpActionResult = result
            infoMessage = "Тренировочная партия Gwent началась."
            errorMessage = nil
            await refreshPvpTables()
        } catch {
            errorMessage = readable(error)
        }
    }

    @discardableResult
    func saveGwentDeck(_ deck: GwentDeck) async -> GwentDeck? {
        guard let player, !playerCode.isEmpty else {
            errorMessage = "Нужен вход по коду игрока перед сохранением колоды."
            return nil
        }
        guard await ensureGwentServerReady() else { return nil }

        let requestedDeckId = deck.deckId.hasPrefix("runtime_deck_")
            ? deck.deckId
            : "runtime_deck_\(player.playerId)_\(deck.deckId)"

        do {
            let result = try await api.saveGwentDeck(
                playerCode: playerCode,
                deckId: requestedDeckId,
                leaderCardId: deck.leaderCardId,
                cardIds: deck.cardIds
            )
            guard let responseDeck = result.objectValue?.object("deck") else {
                lastPvpActionResult = result
                infoMessage = "Колода сохранена на сервере."
                errorMessage = nil
                return nil
            }
            let savedCardIds = responseDeck.arrayStrings("card_ids")
            let savedDeck = GwentDeck(
                deckId: responseDeck.string("deck_id", default: requestedDeckId),
                playerId: responseDeck.string("player_id", default: player.playerId),
                leaderCardId: responseDeck.string("leader_card_id", default: deck.leaderCardId),
                cardIds: savedCardIds.isEmpty ? deck.cardIds : savedCardIds
            )
            runtimeGwentDecks.removeAll { $0.deckId == savedDeck.deckId }
            runtimeGwentDecks.append(savedDeck)
            lastPvpActionResult = result
            infoMessage = "Колода сохранена на сервере."
            errorMessage = nil
            return savedDeck
        } catch {
            errorMessage = readable(error)
            return nil
        }
    }

    func recordGwentAction(
        matchId: String,
        roundNumber: Int,
        action: String,
        cardId: String? = nil,
        row: String? = nil,
        targetCardId: String? = nil,
        discardCardIds: [String]? = nil,
        reviveCardId: String? = nil,
        reviveRow: String? = nil,
        actionId: String? = nil
    ) async {
        guard !playerCode.isEmpty else {
            errorMessage = "Нужен вход по коду игрока перед ходом Gwent."
            return
        }
        let id = matchId.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !id.isEmpty else { return }

        do {
            let result = try await api.recordGwentAction(
                matchId: id,
                action: action,
                roundNumber: max(1, roundNumber),
                cardId: cardId,
                row: row,
                targetCardId: targetCardId,
                discardCardIds: discardCardIds,
                reviveCardId: reviveCardId,
                reviveRow: reviveRow,
                actionId: actionId,
                playerCode: playerCode
            )
            lastPvpActionResult = result
            infoMessage = action == "pass" ? "Пас отправлен." : "Ход отправлен."
            errorMessage = nil
            await refreshPvpTables()
        } catch {
            await recoverPvpStateAfterError(preserving: readable(error))
        }
    }

    func finishGwentMatch(matchId: String, winnerId: String) async {
        guard !playerCode.isEmpty else {
            errorMessage = "Нужен вход по коду игрока перед завершением Gwent."
            return
        }
        let id = matchId.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !id.isEmpty else { return }

        do {
            let result = try await api.finishGwentMatch(
                matchId: id,
                winnerId: winnerId,
                playerCode: playerCode
            )
            lastPvpActionResult = result
            pvpPlayerState = result
            infoMessage = "Gwent match finish отправлен."
            errorMessage = nil
            do {
                pvpTables = try await api.fetchPvpTables()
            } catch {
                errorMessage = readable(error)
            }
        } catch {
            await recoverPvpStateAfterError(preserving: readable(error))
        }
    }

    private func recoverPvpStateAfterError(preserving message: String) async {
        if !playerCode.isEmpty {
            if let state = try? await api.fetchPvpPlayerState(playerCode: playerCode) {
                pvpPlayerState = state
            }
            if let tables = try? await api.fetchPvpTables() {
                pvpTables = tables
            }
        }
        errorMessage = message
    }

    private func ensureGwentServerReady() async -> Bool {
        if serverSupportsGwent {
            return true
        }
        do {
            let health = try await api.fetchHealth()
            serverHealth = health
            if serverSupportsGwent {
                return true
            }
            errorMessage = incompatibleServerMessage(health)
            return false
        } catch {
            errorMessage = "Не могу подключиться к серверу игры. Проверь, что FastAPI запущен на ноутбуке по адресу из настроек."
            return false
        }
    }

    private func incompatibleServerMessage(_ health: HealthResponse) -> String {
        let revision = health.api?.revision ?? "нет версии"
        return "Сервер не поддерживает текущий iOS Гвинт (\(revision)). Перезапусти мастерский FastAPI из текущего кода; /health должен показать \(requiredAPIRevision)."
    }

    private static func normalizedServerURL(from text: String) -> URL? {
        var raw = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !raw.isEmpty else { return nil }
        if raw.lowercased().hasSuffix("/health") {
            raw.removeLast("/health".count)
        }
        while raw.hasSuffix("/") {
            raw.removeLast()
        }
        if !raw.contains("://") {
            raw = "http://\(raw)"
        }
        guard var components = URLComponents(string: raw),
              let scheme = components.scheme?.lowercased(),
              scheme == "http" || scheme == "https",
              components.host != nil
        else {
            return nil
        }
        components.path = ""
        components.query = nil
        components.fragment = nil
        return components.url
    }

    private static func startupServerURL(storedURL: URL?, defaultURL: URL) -> URL {
        guard let normalizedDefault = normalizedServerURL(from: defaultURL.absoluteString) else {
            return defaultURL
        }
        guard let storedURL,
              let normalizedStored = normalizedServerURL(from: storedURL.absoluteString)
        else {
            return normalizedDefault
        }
        if normalizedStored.absoluteString == normalizedDefault.absoluteString {
            return normalizedDefault
        }
        let staleDefaultURLs = Set(
            staleDefaultServerURLStrings.compactMap { normalizedServerURL(from: $0)?.absoluteString }
        )
        if staleDefaultURLs.contains(normalizedStored.absoluteString) {
            return normalizedDefault
        }
        return normalizedStored
    }

    func createTradeTransfer(
        toPlayerId: String,
        assetType: String,
        assetId: String,
        quantity: Int,
        priceGold: Int,
        mode: String
    ) async {
        guard let player, !playerCode.isEmpty else {
            errorMessage = "Нужен вход по коду игрока перед передачей вещи."
            return
        }
        guard !toPlayerId.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            errorMessage = "Выбери получателя передачи."
            return
        }
        guard !assetId.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            errorMessage = "Выбери вещь для передачи."
            return
        }

        do {
            syncState = .syncing
            let result = try await api.createTradeTransfer(
                from: player,
                toPlayerId: toPlayerId.trimmingCharacters(in: .whitespacesAndNewlines),
                assetType: assetType,
                assetId: assetId.trimmingCharacters(in: .whitespacesAndNewlines),
                quantity: max(1, quantity),
                priceGold: max(0, priceGold),
                mode: mode,
                playerCode: playerCode
            )
            lastTradeResult = result
            syncState = pendingEvents.isEmpty ? .synced : .pending
            infoMessage = "Передача создана и отправлена на сервер."
            errorMessage = nil
            await refreshSnapshot()
        } catch {
            syncState = .syncError
            errorMessage = readable(error)
        }
    }

    func sellMaterial(materialId: String, quantity: Int) async {
        guard let player, !playerCode.isEmpty else {
            errorMessage = "Нужен вход по коду игрока перед продажей материалов."
            return
        }
        let normalizedMaterialId = materialId.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !normalizedMaterialId.isEmpty else {
            errorMessage = "Выбери материал для продажи."
            return
        }

        do {
            syncState = .syncing
            let result = try await api.sellMaterial(
                player: player,
                materialId: normalizedMaterialId,
                quantity: max(1, quantity),
                playerCode: playerCode
            )
            lastMaterialMarketResult = result
            syncState = pendingEvents.isEmpty ? .synced : .pending
            infoMessage = "Материал продан рынку."
            errorMessage = nil
            await refreshSnapshot()
        } catch {
            syncState = .syncError
            errorMessage = readable(error)
        }
    }

    func acceptTradeTransfer(id transferId: String) async {
        guard let player, !playerCode.isEmpty else { return }
        let id = transferId.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !id.isEmpty else { return }

        do {
            let result = try await api.acceptTradeTransfer(
                transferId: id,
                player: player,
                playerCode: playerCode
            )
            lastTradeResult = result
            infoMessage = "Передача принята."
            errorMessage = nil
            await refreshSnapshot()
        } catch {
            errorMessage = readable(error)
        }
    }

    func declineTradeTransfer(id transferId: String, reason: String) async {
        guard let player, !playerCode.isEmpty else { return }
        let id = transferId.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !id.isEmpty else { return }

        do {
            let result = try await api.declineTradeTransfer(
                transferId: id,
                player: player,
                reason: reason.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ? "declined" : reason,
                playerCode: playerCode
            )
            lastTradeResult = result
            infoMessage = "Передача отклонена."
            errorMessage = nil
            await refreshSnapshot()
        } catch {
            errorMessage = readable(error)
        }
    }

    private func syncSummary(_ results: [SyncEventResult]) -> String {
        let grouped = Dictionary(grouping: results, by: \.status).mapValues { $0.count }
        return grouped
            .sorted { $0.key < $1.key }
            .map { "\(syncStatusLabel($0.key)): \($0.value)" }
            .joined(separator: ", ")
    }

    private func syncStatusLabel(_ status: String) -> String {
        switch status.lowercased() {
        case "accepted":
            return "принято"
        case "duplicate":
            return "уже было принято"
        case "needs_review", "review", "queued_for_review":
            return "ждет мастера"
        case "rejected":
            return "отклонено"
        default:
            return status
        }
    }

    private func readable(_ error: Error) -> String {
        if let api = error as? APIError {
            return api.description
        }
        return error.localizedDescription
    }

    private func sha256Hex(_ value: String) -> String {
        SHA256.hash(data: Data(value.utf8))
            .map { String(format: "%02x", $0) }
            .joined()
    }

    private static let demoSnapshotJSON = """
    {
      "snapshot_version": "ios-demo-local",
      "generated_at": "2026-06-12T00:00:00+03:00",
      "auth": {"scope": "player_code", "player_id": "p_witcher_1", "player_code_id": "code_witcher_1"},
      "player": {
        "player_id": "p_witcher_1",
        "role_type": "witcher",
        "display_name": "Ведьмак Волк",
        "level": "2",
        "xp": "14",
        "gold": "35",
        "challenge_tokens": "3",
        "stats_json": "{\\"Сила\\":3,\\"Ловкость\\":2,\\"Разум\\":1,\\"Харизма\\":1,\\"Воля\\":2}",
        "reputation_state": {"player_descriptor": "Нейтральная репутация"}
      },
      "players": [
        {
          "player_id": "p_witcher_1",
          "role_type": "witcher",
          "display_name": "Ведьмак Волк",
          "level": "2",
          "xp": "14",
          "gold": "35",
          "challenge_tokens": "3",
          "stats_json": "{\\"Сила\\":3,\\"Ловкость\\":2,\\"Разум\\":1,\\"Харизма\\":1,\\"Воля\\":2}",
          "reputation_state": {"player_descriptor": "Нейтральная репутация"}
        },
        {
          "player_id": "p_lord_1",
          "role_type": "lord",
          "display_name": "Лорд Севера",
          "level": "1",
          "xp": "0",
          "gold": "80",
          "stats_json": "{}",
          "reputation_state": {"player_descriptor": "Влиятельный союзник"}
        },
        {
          "player_id": "p_sorc_1",
          "role_type": "sorceress",
          "display_name": "Чародейка Лира",
          "level": "1",
          "xp": "0",
          "gold": "45",
          "stats_json": "{\\"Воля\\":3,\\"Разум\\":3}",
          "reputation_state": {"player_descriptor": "Опасная репутация"}
        },
        {
          "player_id": "p_witcher_2",
          "role_type": "witcher",
          "display_name": "Ведьмак Грифон",
          "level": "1",
          "xp": "4",
          "gold": "18",
          "stats_json": "{\\"Сила\\":2,\\"Ловкость\\":3}",
          "reputation_state": {"player_descriptor": "Добрая слава"}
        }
      ],
      "orders": [
        {
          "order_id": "order_demo_public",
          "lord_id": "p_lord_1",
          "target_player_id": "",
          "accepted_by_player_id": "",
          "submitted_by_player_id": "",
          "object_id": "qr_a1_001",
          "object_label": "След у темного леса",
          "object_type": "qr_object",
          "visibility": "public",
          "status": "published",
          "escrow_reward_id": "reward_order_success"
        },
        {
          "order_id": "order_demo_active",
          "lord_id": "p_lord_1",
          "target_player_id": "p_witcher_1",
          "accepted_by_player_id": "p_witcher_1",
          "submitted_by_player_id": "",
          "object_id": "qr_a1_002",
          "object_label": "Разведка у деревни",
          "object_type": "qr_object",
          "visibility": "addressed",
          "status": "accepted",
          "escrow_reward_id": "reward_order_success"
        }
      ],
      "qr_objects": [
        {
          "qr_id": "qr_a1_001",
          "manual_code": "QR-A1-K7Q2",
          "scenario_id": "scn_a1_001",
          "qr_mode": "repeatable_scene",
          "act_id": "act1",
          "location_node_id": "node_forest_dark",
          "physical_presence_required": "true"
        },
        {
          "qr_id": "qr_a1_002",
          "manual_code": "QR-A1-M4Y8",
          "scenario_id": "scn_a1_002",
          "qr_mode": "repeatable_scene",
          "act_id": "act1",
          "location_node_id": "node_village_barn",
          "physical_presence_required": "true"
        }
      ],
      "pve_scenarios": [
        {
          "scenario_id": "scn_a1_001",
          "act_id": "act1",
          "tier": "1",
          "scene_type": "monster_hunt",
          "primary_stat": "Сила",
          "dc": "11",
          "combat_profile_id": "mob_neutral_patrol_t1",
          "reward_id": "reward_pve_t1",
          "success_text": "След взят",
          "failure_text": "След потерян"
        },
        {
          "scenario_id": "scn_a1_002",
          "act_id": "act1",
          "tier": "1",
          "scene_type": "investigation",
          "primary_stat": "Разум",
          "dc": "10",
          "combat_profile_id": "mob_neutral_patrol_t1",
          "reward_id": "reward_pve_t1",
          "success_text": "Улика найдена",
          "failure_text": "Ложный след"
        }
      ],
      "mobs": [],
      "rewards": [
        {"reward_id": "reward_pve_t1", "xp": "4", "gold": "10", "rarity": "Common", "approval_policy": "auto"}
      ],
      "items": [
        {"item_id": "item_monster_trophy", "item_type": "trophy", "tier": "3", "effect_json": "{\\"use\\":\\"lord_influence_claim\\"}"},
        {"item_id": "item_order_seal", "item_type": "order_token", "tier": "2", "effect_json": "{\\"use\\":\\"order_completion_proof\\"}"},
        {"item_id": "item_secret_writ", "item_type": "quest_object", "tier": "2", "effect_json": "{\\"use\\":\\"quest_leverage\\"}"}
      ],
      "materials": [
        {"material_id": "mat_herbs", "display_name": "Травы", "rarity": "Common", "category": "alchemy", "description": "База для простых зелий.", "effect_json": "{\\"market_only\\":true}"},
        {"material_id": "mat_silver_dust", "display_name": "Серебряная пыль", "rarity": "Uncommon", "category": "monster", "description": "След чудовищ и серебра.", "effect_json": "{\\"market_only\\":true}"}
      ],
      "material_market": [
        {"market_id": "market_herbs", "material_id": "mat_herbs", "display_name": "Травы", "category": "alchemy", "description": "База для простых зелий.", "base_price": "4", "min_price": "2", "max_price": "8", "current_price": "5", "total_player_quantity": "9", "trend": "balanced"},
        {"market_id": "market_silver_dust", "material_id": "mat_silver_dust", "display_name": "Серебряная пыль", "category": "monster", "description": "След чудовищ и серебра.", "base_price": "9", "min_price": "5", "max_price": "18", "current_price": "14", "total_player_quantity": "3", "trend": "scarce"}
      ],
      "cards": [
        {"card_id": "pc_infantry_t1", "card_type": "personal_to_army", "tier": "1", "name": "Infantry Favor", "conversion_rule": "may_transfer_to_lord_once"},
        {"card_id": "pc_guard_t1", "card_type": "personal_to_army", "tier": "1", "name": "Guard Contract", "conversion_rule": "may_transfer_to_lord_once"}
      ],
      "potions": [
        {"potion_id": "potion_common_swallow", "rarity": "Common", "wholesale_cost": "8", "effect_json": "{\\"effect\\":\\"any_check_modifier_plus_1\\",\\"modifier\\":1}"},
        {"potion_id": "potion_common_cat", "rarity": "Common", "wholesale_cost": "8", "effect_json": "{\\"effect\\":\\"extra_hint\\"}"}
      ],
      "artifacts": [
        {"artifact_id": "artifact_silver_chain", "rarity": "Rare", "visibility": "owner_visible", "counterplay": "can_be_stolen_by_order"}
      ],
      "asset_ownership": [
        {"owner_player_id": "p_witcher_1", "asset_type": "item", "asset_id": "item_monster_trophy", "quantity": "1", "status": "active"},
        {"owner_player_id": "p_witcher_1", "asset_type": "artifact", "asset_id": "artifact_silver_chain", "quantity": "1", "status": "active"}
      ],
      "potion_inventory": [
        {"player_id": "p_witcher_1", "potion_id": "potion_common_swallow", "quantity": "2"}
      ],
      "material_inventory": [
        {"player_id": "p_witcher_1", "material_id": "mat_herbs", "display_name": "Травы", "category": "alchemy", "description": "База для простых зелий.", "quantity": "5"},
        {"player_id": "p_witcher_1", "material_id": "mat_silver_dust", "display_name": "Серебряная пыль", "category": "monster", "description": "След чудовищ и серебра.", "quantity": "1"}
      ],
      "trade_transfers": [
        {"transfer_id": "trade_pending_demo", "from_player_id": "p_witcher_1", "to_player_id": "p_lord_1", "asset_type": "item", "asset_id": "item_monster_trophy", "quantity": "1", "price_gold": "0", "mode": "gift", "status": "pending_locked"},
        {"transfer_id": "trade_incoming_demo", "from_player_id": "p_sorc_1", "to_player_id": "p_witcher_1", "asset_type": "potion", "asset_id": "potion_common_swallow", "quantity": "1", "price_gold": "5", "mode": "sell", "status": "pending_locked"}
      ],
      "reward_approvals": [
        {"approval_id": "approval_demo_locked_reward", "player_id": "p_witcher_1", "reward_id": "reward_pve_t1", "status": "pending_master_approval"}
      ],
      "gwent_cards": [
        {"card_id": "gwent_leader_wolf", "faction": "northern", "row": "leader", "type": "leader", "strength": "0", "effect": "leader_foltest_clear_weather", "rarity": "Uncommon", "ability_tags": "", "name_group": "leader_foltest", "bond_group": "", "muster_group": ""},
        {"card_id": "gwent_unit_01", "faction": "northern", "row": "melee", "type": "unit", "strength": "4", "effect": "none", "rarity": "Common", "ability_tags": "", "name_group": "silver_blade", "bond_group": "", "muster_group": ""},
        {"card_id": "gwent_unit_02", "faction": "northern", "row": "melee", "type": "unit", "strength": "4", "effect": "none", "rarity": "Common", "ability_tags": "", "name_group": "kaer_morhen_tracker", "bond_group": "", "muster_group": ""},
        {"card_id": "gwent_unit_03", "faction": "northern", "row": "melee", "type": "unit", "strength": "5", "effect": "tight_bond", "rarity": "Common", "ability_tags": "", "name_group": "blue_stripes_soldier", "bond_group": "blue_stripes", "muster_group": ""},
        {"card_id": "gwent_unit_04", "faction": "northern", "row": "melee", "type": "unit", "strength": "5", "effect": "tight_bond", "rarity": "Common", "ability_tags": "", "name_group": "blue_stripes_soldier", "bond_group": "blue_stripes", "muster_group": ""},
        {"card_id": "rare_gwent_02", "faction": "neutral", "row": "melee", "type": "unit", "strength": "15", "effect": "hero", "rarity": "Hero", "ability_tags": "hero", "name_group": "geralt_of_rivia", "bond_group": "", "muster_group": "", "display_name": "Геральт из Ривии", "effect_text": "Не подвержен погоде, командирскому рогу, казни и большинству способностей."},
        {"card_id": "gwent_weather_frost", "faction": "neutral", "row": "weather", "type": "special", "strength": "0", "effect": "weather_melee", "rarity": "Common", "ability_tags": "", "name_group": "biting_frost", "bond_group": "", "muster_group": ""},
        {"card_id": "gwent_clear_weather", "faction": "neutral", "row": "special", "type": "special", "strength": "0", "effect": "clear_weather", "rarity": "Common", "ability_tags": "", "name_group": "clear_weather", "bond_group": "", "muster_group": ""},
        {"card_id": "gwent_horn", "faction": "neutral", "row": "special", "type": "special", "strength": "0", "effect": "commanders_horn", "rarity": "Uncommon", "ability_tags": "", "name_group": "commanders_horn", "bond_group": "", "muster_group": ""}
      ],
      "gwent_decks": [
        {
          "deck_id": "deck_witcher_wolf",
          "player_id": "p_witcher_1",
          "leader_card_id": "gwent_leader_wolf",
          "card_ids": "rare_gwent_02;gwent_unit_01;gwent_unit_02;gwent_unit_03;gwent_unit_04;gwent_weather_frost;gwent_clear_weather;gwent_horn"
        }
      ],
      "goals": {
        "personal_goals": [
          {"goal_id": "goal_demo_hunt", "public_text": "Добыть доказательство у лесного QR"},
          {"goal_id": "goal_demo_order", "public_text": "Закрыть заказ лорда через proof"}
        ],
        "goal_tracks": []
      },
      "act_unlock_state": {
        "current_act_id": "act1",
        "unlocked_act_ids": ["act1"],
        "revealed_act_ids": ["act2"],
        "policy": "server_sync_or_revealed_master_code"
      },
      "act_unlock_codes": [
        {
          "unlock_id": "unlock_act2",
          "act_id": "act2",
          "revealed_after_start": "true",
          "server_unlocked": true,
          "revealed": true,
          "code": "UNLOCK-A2-7GQ4",
          "code_sha256": "93f6704b37a7cdac3004a21ae7c065d253585e560b85a900666e09f53bf2b100",
          "physical_announcement_state": "announced",
          "physical_announcement_at": "2026-06-12T12:30:00+03:00",
          "unlock_revealed_at": "2026-06-12T12:31:00+03:00",
          "unlock_revealed_by": "gm_king"
        },
        {
          "unlock_id": "unlock_act3",
          "act_id": "act3",
          "revealed_after_start": "true",
          "server_unlocked": false,
          "revealed": false,
          "code": null,
          "code_sha256": null,
          "physical_announcement_state": null,
          "physical_announcement_at": null,
          "unlock_revealed_at": null,
          "unlock_revealed_by": null
        }
      ]
    }
    """

    private static let demoGwentStateJSON = """
    {
      "challenge": {
        "challenge_id": "ios_demo_challenge",
        "challenger_id": "p_witcher_1",
        "target_id": "p_witcher_2",
        "status": "in_match",
        "assigned_zone": "main_house_table"
      },
      "match": {
        "match_id": "ios_demo_match",
        "challenge_id": "ios_demo_challenge",
        "status": "round_in_progress",
        "deck_state": {
          "p_witcher_1": {
            "hand": ["rare_gwent_02", "gwent_unit_01", "gwent_unit_02", "gwent_weather_frost"],
            "graveyard": ["gwent_unit_03"],
            "leader_used": false
          },
          "p_witcher_2": {
            "hand": ["gwent_unit_07", "gwent_unit_08"],
            "graveyard": [],
            "leader_used": false
          },
          "cards_burn_after_round": false
        }
      },
      "round": {
        "round_number": 1,
        "winner_id": null,
        "round_state": {
          "status": "pending_player_submissions",
          "ready_players": [],
          "missing_players": ["p_witcher_1", "p_witcher_2"],
          "passed": {"p_witcher_1": false, "p_witcher_2": false},
          "board": {
            "p_witcher_1": {
              "melee": ["rare_gwent_02"],
              "ranged": [],
              "siege": []
            },
            "p_witcher_2": {
              "melee": [],
              "ranged": [],
              "siege": []
            }
          }
        }
      }
    }
    """
}

enum SyncState: String {
    case offline
    case pending
    case syncing
    case synced
    case syncError
    case needsReview
}

enum QRInputSource: String {
    case camera
    case manual

    var apiValue: String {
        switch self {
        case .camera:
            return "qr_scan"
        case .manual:
            return "manual_id"
        }
    }
}

extension APIError: CustomStringConvertible {
    var description: String {
        switch self {
        case .invalidURL:
            return "Некорректный URL сервера."
        case .invalidResponse:
            return "Сервер вернул некорректный ответ."
        case .httpStatus(let status, let detail):
            if let detail = detail?.trimmingCharacters(in: .whitespacesAndNewlines), !detail.isEmpty {
                if status == 404 || detail.caseInsensitiveCompare("not found") == .orderedSame {
                    return "Сервер не нашел нужный игровой API. Проверь, что приложение подключено к текущему FastAPI, а не к старому серверу."
                }
                return detail
            }
            if status == 404 {
                return "Сервер не нашел нужный игровой API. Проверь, что приложение подключено к текущему FastAPI, а не к старому серверу."
            }
            return "HTTP \(status). Проверь код игрока и адрес сервера в настройках."
        }
    }
}
