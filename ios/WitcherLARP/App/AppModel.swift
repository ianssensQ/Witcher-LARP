import Foundation

@MainActor
final class AppModel: ObservableObject {
    @Published var serverURL: URL
    @Published var snapshot: PlayerSnapshot?
    @Published var activePvEScenario: PvEScenarioCard?
    @Published var lastQRLookup: QRLookupResponse?
    @Published var pendingEvents: [QueuedEvent] = []
    @Published var syncState: SyncState = .offline
    @Published var errorMessage: String?

    private let store = LocalStore.shared
    private let queue = EventQueueStore.shared
    private var api: LarpAPIClient
    private let deviceId: String
    private var playerCode: String?

    var activeQRMode: String? {
        lastQRLookup?.qr?.qrMode
    }

    init() {
        let defaultURL = URL(string: "http://127.0.0.1:8000")!
        let savedURL = LocalStore.shared.loadServerURL() ?? defaultURL
        self.serverURL = savedURL
        self.api = LarpAPIClient(baseURL: savedURL)
        self.deviceId = LocalStore.shared.loadDeviceId()
        self.playerCode = LocalStore.shared.loadPlayerCode()
        self.snapshot = LocalStore.shared.loadSnapshot()
        self.pendingEvents = EventQueueStore.shared.loadEvents()
    }

    func updateServerURL(_ url: URL) {
        serverURL = url
        api = LarpAPIClient(baseURL: url)
        store.saveServerURL(url)
    }

    func login(playerCode: String) async {
        do {
            syncState = .syncing
            _ = try await api.login(playerCode: playerCode, deviceId: deviceId)
            let loadedSnapshot = try await api.fetchSnapshot(playerCode: playerCode)
            self.playerCode = playerCode
            snapshot = loadedSnapshot
            store.savePlayerCode(playerCode)
            store.saveSnapshot(loadedSnapshot)
            syncState = .synced
            errorMessage = nil
        } catch {
            syncState = .syncError
            errorMessage = error.localizedDescription
        }
    }

    func appendQRAttempt(qrId: String, source: QRInputSource) {
        guard let snapshot else { return }
        let event = QueuedEvent(
            playerId: snapshot.playerId,
            eventType: "qr_attempt",
            payload: [
                "qr_id": qrId,
                "source": source.rawValue,
                "presence_confirmed": "true"
            ]
        )
        queue.append(event)
        pendingEvents = queue.loadEvents()
    }

    func lookupQRCode(_ code: String, source: QRInputSource) async {
        guard let snapshot else { return }
        guard let playerCode else {
            appendQRAttempt(qrId: code, source: source)
            errorMessage = "Player code is required for online QR lookup."
            syncState = .needsReview
            return
        }

        do {
            syncState = .syncing
            let response = try await api.lookupQR(
                code: code,
                playerCode: playerCode,
                playerId: snapshot.playerId,
                deviceId: deviceId,
                source: source.rawValue,
                physicalPresenceConfirmed: true
            )
            lastQRLookup = response
            if let scenario = response.scenario {
                activePvEScenario = scenario
            }
            syncState = response.status == "ok" ? .synced : .needsReview
            errorMessage = response.status == "ok" ? nil : (response.message ?? response.reason ?? response.status)
        } catch {
            appendQRAttempt(qrId: code, source: source)
            syncState = .needsReview
            errorMessage = "QR lookup is queued for sync: \(error.localizedDescription)"
        }
    }

    func syncPendingEvents() async {
        let events = queue.loadEvents()
        guard !events.isEmpty else {
            syncState = .synced
            return
        }

        do {
            syncState = .syncing
            let response = try await api.sync(events: events, deviceId: deviceId)
            queue.applySyncResults(response.results)
            pendingEvents = queue.loadEvents()
            syncState = pendingEvents.isEmpty ? .synced : .needsReview
            errorMessage = nil
        } catch {
            syncState = .syncError
            errorMessage = error.localizedDescription
        }
    }
}

enum SyncState: String {
    case offline
    case syncing
    case synced
    case syncError
    case needsReview
}

enum QRInputSource: String {
    case camera = "qr_scan"
    case manual = "manual_id"
}
