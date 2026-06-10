import Foundation

struct PlayerSnapshot: Codable, Equatable {
    let snapshotVersion: Int
    let playerId: String
    let displayName: String
    let roleType: String
    let actId: String?
    let level: Int
    let xp: Int
    let gold: Int
    let reputationLabel: String
    let goals: [PlayerGoal]

    enum CodingKeys: String, CodingKey {
        case snapshotVersion = "snapshot_version"
        case playerId = "player_id"
        case displayName = "display_name"
        case roleType = "role_type"
        case actId = "act_id"
        case level
        case xp
        case gold
        case reputationLabel = "reputation_label"
        case goals
    }
}

struct PlayerGoal: Codable, Equatable, Identifiable {
    let goalId: String
    let title: String
    let progressLabel: String?

    var id: String { goalId }

    enum CodingKeys: String, CodingKey {
        case goalId = "goal_id"
        case title
        case progressLabel = "progress_label"
    }
}
