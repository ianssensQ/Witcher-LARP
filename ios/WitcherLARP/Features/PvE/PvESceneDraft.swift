import Foundation

struct PvESceneDraft: Codable, Equatable {
    let qrId: String
    let scenarioId: String
    let stat: String
    let dc: Int
    let roll: Int
    let modifiers: [String]

    var total: Int {
        roll + modifiers.compactMap(Int.init).reduce(0, +)
    }

    var isSuccess: Bool {
        total >= dc
    }

    static func placeholder(qrId: String) -> PvESceneDraft {
        PvESceneDraft(
            qrId: qrId,
            scenarioId: "pending_snapshot_lookup",
            stat: "body",
            dc: 12,
            roll: Int.random(in: 1...20),
            modifiers: []
        )
    }
}
