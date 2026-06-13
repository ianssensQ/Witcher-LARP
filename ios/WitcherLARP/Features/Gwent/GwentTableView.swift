import SwiftUI
import UIKit
import Combine
import UniformTypeIdentifiers

private struct GwentTargetSelection: Identifiable {
    let id = UUID()
    let action: String
    let matchId: String
    let roundNumber: Int
    let cardId: String
    let row: String?
    let targetKind: String
    let discardCardIds: [String]
    let targets: [[String: JSONValue]]

    var title: String {
        switch targetKind {
        case "own_non_hero_unit":
            return "Выбери карту, которую вернет приманка"
        case "graveyard_unit":
            return "Выбери карту из сброса для медика"
        case "leader_own_graveyard_unit":
            return "Выбери карту из своего сброса"
        case "leader_opponent_graveyard_unit":
            return "Выбери карту из сброса соперника"
        default:
            return "Выбери цель"
        }
    }
}

private struct GwentLeaderDiscardSelection: Identifiable {
    let id = UUID()
    let matchId: String
    let roundNumber: Int
    let cardId: String
    let hand: [String]
    let drawCardId: String
}

private struct GwentDeckMetrics {
    let units: Int
    let specials: Int
    let heroes: Int
    let rows: [String: Int]

    var activeRows: Int {
        rows.values.filter { $0 > 0 }.count
    }
}

private struct GwentCardPlacement: Identifiable {
    let row: String?
    let isOpponent: Bool
    let title: String

    var id: String {
        "\(isOpponent ? "opponent" : "own"):\(row ?? "special")"
    }
}

private struct GwentEffectInfo: Identifiable {
    let id: String
    let title: String
    let subtitle: String
    let body: String
    let icon: String
    let badge: String
    let color: Color
    let usesDarkText: Bool
}

private struct GwentLeaderActivation: Identifiable {
    let id = UUID()
    let match: [String: JSONValue]
    let leaderCardId: String
    let effectInfo: GwentEffectInfo
}

private enum GwentBoardFocusSide {
    case own
    case opponent

    var isOpponent: Bool {
        self == .opponent
    }
}

private struct GwentOrientationRequester: UIViewControllerRepresentable {
    let orientations: UIInterfaceOrientationMask

    func makeUIViewController(context: Context) -> Controller {
        let controller = Controller()
        controller.orientations = orientations
        return controller
    }

    func updateUIViewController(_ uiViewController: Controller, context: Context) {
        uiViewController.orientations = orientations
        uiViewController.requestOrientation()
    }

    static func dismantleUIViewController(_ uiViewController: Controller, coordinator: ()) {
        uiViewController.orientations = .portrait
        uiViewController.requestOrientation()
    }

    final class Controller: UIViewController {
        var orientations: UIInterfaceOrientationMask = .landscape

        override var supportedInterfaceOrientations: UIInterfaceOrientationMask {
            orientations
        }

        override func viewDidAppear(_ animated: Bool) {
            super.viewDidAppear(animated)
            requestOrientation()
        }

        func requestOrientation() {
            setNeedsUpdateOfSupportedInterfaceOrientations()
            let targetOrientation: UIInterfaceOrientation = orientations.contains(.landscapeRight)
                ? .landscapeRight
                : (orientations.contains(.landscapeLeft) ? .landscapeLeft : .portrait)
            UIDevice.current.setValue(targetOrientation.rawValue, forKey: "orientation")
            guard let windowScene = view.window?.windowScene else { return }
            windowScene.requestGeometryUpdate(.iOS(interfaceOrientations: orientations)) { _ in }
        }
    }
}

private struct GwentTableLayout {
    enum Density {
        case tightPhone
        case phone
        case regular
    }

    let viewport: CGSize
    let safeAreaInsets: EdgeInsets
    let density: Density
    let contentInsets: EdgeInsets
    let contentWidth: CGFloat
    let contentHeight: CGFloat
    let selectionMode: Bool

    init(viewport: CGSize, safeAreaInsets: EdgeInsets, compactHeight: Bool, selectionMode: Bool = false) {
        self.viewport = viewport
        self.safeAreaInsets = safeAreaInsets
        self.selectionMode = selectionMode

        let safeHorizontal = safeAreaInsets.leading + safeAreaInsets.trailing
        let safeVertical = safeAreaInsets.top + safeAreaInsets.bottom
        let usableWidth = max(viewport.width - safeHorizontal, 0)
        let usableHeight = max(viewport.height - safeVertical, 0)
        let longSide = max(viewport.width, viewport.height)
        let shortSide = min(viewport.width, viewport.height)
        let phoneLike = compactHeight || shortSide <= 500

        let resolvedDensity: Density
        if phoneLike && (usableHeight <= 390 || usableWidth <= 760) {
            resolvedDensity = .tightPhone
        } else if phoneLike {
            resolvedDensity = .phone
        } else {
            resolvedDensity = .regular
        }

        let baseHorizontal: CGFloat
        let baseVertical: CGFloat
        switch resolvedDensity {
        case .tightPhone:
            baseHorizontal = 6
            baseVertical = 3
        case .phone:
            baseHorizontal = 8
            baseVertical = 5
        case .regular:
            baseHorizontal = 12
            baseVertical = 8
        }

        let notchFallback: CGFloat = phoneLike && safeHorizontal < 20 && longSide >= 780 ? 44 : 0
        let landscapeTopClearance: CGFloat = phoneLike ? (resolvedDensity == .tightPhone ? 34 : 40) : 0
        let leading = max(max(safeAreaInsets.leading, baseHorizontal), notchFallback)
        let trailing = max(max(safeAreaInsets.trailing, baseHorizontal), notchFallback)
        let top = max(max(safeAreaInsets.top, baseVertical), landscapeTopClearance)
        let bottom = max(safeAreaInsets.bottom, baseVertical)

        self.density = resolvedDensity
        self.contentInsets = EdgeInsets(top: top, leading: leading, bottom: bottom, trailing: trailing)
        self.contentWidth = max(viewport.width - leading - trailing, 320)
        self.contentHeight = max(viewport.height - top - bottom, 240)
    }

    var isCompact: Bool {
        density != .regular
    }

    var isTightPhone: Bool {
        density == .tightPhone
    }

    var showsExpandedRails: Bool {
        density == .regular
    }

    var tableStackSpacing: CGFloat {
        isTightPhone ? 3 : (isCompact ? 4 : 6)
    }

    var tableColumnSpacing: CGFloat {
        isTightPhone ? 4 : (isCompact ? 6 : 8)
    }

    var boardRowSpacing: CGFloat {
        isTightPhone ? 2 : (isCompact ? 3 : 4)
    }

    var tableHeaderHeight: CGFloat {
        isTightPhone ? 34 : (isCompact ? 36 : 40)
    }

    var playerRailWidth: CGFloat {
        isTightPhone ? 58 : (isCompact ? 70 : 92)
    }

    var railSpacing: CGFloat {
        isTightPhone ? 3 : (isCompact ? 4 : 7)
    }

    var weatherStripHeight: CGFloat {
        isTightPhone ? 24 : (isCompact ? 28 : 34)
    }

    var actionButtonHeight: CGFloat {
        isTightPhone ? 26 : (isCompact ? 28 : 32)
    }

    var handStripPadding: CGFloat {
        isTightPhone ? 4 : (isCompact ? 5 : 8)
    }

    var handInternalSpacing: CGFloat {
        isTightPhone ? 3 : (isCompact ? 4 : 8)
    }

    var handExpandedHeight: CGFloat {
        if selectionMode {
            switch density {
            case .tightPhone:
                return min(172, max(164, contentHeight * 0.46))
            case .phone:
                return min(228, max(210, contentHeight * 0.50))
            case .regular:
                return min(276, max(252, contentHeight * 0.48))
            }
        }
        switch density {
        case .tightPhone:
            return min(102, max(86, contentHeight * 0.26))
        case .phone:
            return min(118, max(98, contentHeight * 0.27))
        case .regular:
            return 140
        }
    }

    var handCollapsedHeight: CGFloat {
        isTightPhone ? 34 : (isCompact ? 38 : 48)
    }

    var handPanelHeight: CGFloat {
        selectionMode ? handExpandedHeight : handCollapsedHeight
    }

    var boardAreaHeight: CGFloat {
        max(selectionMode ? 124 : 190, contentHeight - tableHeaderHeight - handPanelHeight - (tableStackSpacing * 2))
    }

    var boardRowHeight: CGFloat {
        let visibleRows: CGFloat = selectionMode ? 3 : 6
        let fitted = floor((boardAreaHeight - weatherStripHeight - (boardRowSpacing * visibleRows)) / visibleRows)
        switch density {
        case .tightPhone:
            return min(selectionMode ? 44 : 36, max(selectionMode ? 34 : 28, fitted))
        case .phone:
            return min(selectionMode ? 52 : 42, max(selectionMode ? 40 : 32, fitted))
        case .regular:
            return min(selectionMode ? 70 : 54, max(selectionMode ? 56 : 44, fitted))
        }
    }

    var boardRowIconSize: CGFloat {
        switch density {
        case .tightPhone:
            return max(22, min(26, boardRowHeight - 6))
        case .phone:
            return max(24, min(30, boardRowHeight - 6))
        case .regular:
            return 38
        }
    }

    var boardCardWidth: CGFloat {
        if selectionMode {
            return isTightPhone ? 122 : (isCompact ? 138 : 160)
        }
        return isTightPhone ? 112 : (isCompact ? 126 : 148)
    }

    var boardCardHeight: CGFloat {
        max(selectionMode ? 34 : 28, boardRowHeight - (isCompact ? 8 : 14))
    }

    var boardCardBadgeSize: CGFloat {
        isTightPhone ? 24 : (isCompact ? 26 : 30)
    }

    var boardCardEffectSize: CGFloat {
        isTightPhone ? 15 : (isCompact ? 17 : 20)
    }

    var boardCardTitleFontSize: CGFloat {
        isTightPhone ? 8.5 : (isCompact ? 9.5 : 11)
    }

    var boardCardTitleBandHeight: CGFloat {
        min(isTightPhone ? 24 : (isCompact ? 26 : 30), max(18, boardCardHeight * 0.62))
    }

    var emptyRowWidth: CGFloat {
        isTightPhone ? 78 : (isCompact ? 92 : 116)
    }

    var handCardSpacing: CGFloat {
        isTightPhone ? 5 : (isCompact ? 6 : 8)
    }

    var handCardPadding: CGFloat {
        isTightPhone ? 5 : (isCompact ? 6 : 8)
    }

    var handCardWidth: CGFloat {
        if selectionMode {
            return isTightPhone ? 118 : (isCompact ? 136 : 156)
        }
        return isTightPhone ? 80 : (isCompact ? 92 : 106)
    }

    var handCardHeight: CGFloat {
        let rowsAboveHand: CGFloat = selectionMode ? actionPanelHeight : actionButtonHeight
        let available = handExpandedHeight - rowsAboveHand - (handStripPadding * 2) - handInternalSpacing
        switch density {
        case .tightPhone:
            return max(selectionMode ? 82 : 46, min(selectionMode ? 96 : 62, available))
        case .phone:
            return max(selectionMode ? 102 : 56, min(selectionMode ? 124 : 72, available))
        case .regular:
            return selectionMode ? 144 : 82
        }
    }

    var actionPanelHeight: CGFloat {
        switch density {
        case .tightPhone:
            return 50
        case .phone:
            return 58
        case .regular:
            return 70
        }
    }

    var selectedActionControlsWidth: CGFloat {
        isTightPhone ? 220 : (isCompact ? 268 : 360)
    }

    var focusedHandCardWidth: CGFloat {
        isTightPhone ? 72 : (isCompact ? 82 : 96)
    }

    var focusedHandCardHeight: CGFloat {
        max(50, actionPanelHeight - 4)
    }

    var selectedHandLift: CGFloat {
        isTightPhone ? 6 : (isCompact ? 8 : 10)
    }
}

struct GwentTableView: View {
    @EnvironmentObject private var model: AppModel
    @Environment(\.dismiss) private var dismiss
    @Environment(\.verticalSizeClass) private var verticalSizeClass
    @State private var selectedCardId: String?
    @State private var handExpanded = false
    @State private var boardFocusSide: GwentBoardFocusSide = .own
    @State private var dropTargetRow: String?
    @State private var inspectedPilePlayerId: String?
    @State private var inspectedPileTitle = "Сброс"
    @State private var pendingTargetSelection: GwentTargetSelection?
    @State private var pendingLeaderDiscardSelection: GwentLeaderDiscardSelection?
    @State private var selectedLeaderDiscardIds: Set<String> = []
    @State private var activeEffectInfo: GwentEffectInfo?
    @State private var pendingLeaderActivation: GwentLeaderActivation?
    @State private var selectedMulliganCardIds: Set<String> = []
    @State private var selectedDeckId = ""
    @State private var selectedPreferredStartingPlayerId = ""
    @State private var showingDeckReview = false
    @State private var appliedTableScreenshotArguments = false
    @State private var isSavingDeck = false
    @State private var refusalReason = "safety_stop"
    @State private var pendingGwentActionId: String?
    @State private var observedTurnKey = ""
    @State private var localTurnStartedAt: Date?
    @State private var countdownNow = Date()
    @State private var autoPassTurnKey: String?

    private let ownRows = ["melee", "ranged", "siege"]
    private let opponentRows = ["siege", "ranged", "melee"]
    private let turnLimitSeconds = 60

    var body: some View {
        GeometryReader { proxy in
            let isLandscape = proxy.size.width > proxy.size.height
            let handMode = activeGwentShouldShowHandMode && handExpanded
            let layout = GwentTableLayout(
                viewport: proxy.size,
                safeAreaInsets: proxy.safeAreaInsets,
                compactHeight: compactLandscapeTable,
                selectionMode: handMode
            )

            ZStack {
                gwentTableBackground
                    .ignoresSafeArea()

                if isLandscape {
                    landscapeTable(layout: layout)
                } else {
                    portraitRotationPrompt
                }

                if let activeEffectInfo {
                    effectInfoPlaque(activeEffectInfo, layout: layout)
                        .transition(.move(edge: .top).combined(with: .opacity))
                        .zIndex(30)
                }

                if let pendingLeaderActivation {
                    leaderActivationPlaque(pendingLeaderActivation, layout: layout)
                        .transition(.move(edge: .top).combined(with: .opacity))
                        .zIndex(32)
                }
            }
            .frame(width: proxy.size.width, height: proxy.size.height)
            .ignoresSafeArea()
        }
        .background(GwentOrientationRequester(orientations: .landscape))
        .statusBarHidden()
        .persistentSystemOverlays(.hidden)
        .preferredColorScheme(.dark)
        .sheet(isPresented: Binding(
            get: { inspectedPilePlayerId != nil },
            set: { if !$0 { inspectedPilePlayerId = nil } }
        )) {
            pileInspectionSheet
        }
        .sheet(item: $pendingTargetSelection) { selection in
            targetSelectionSheet(selection)
        }
        .sheet(item: $pendingLeaderDiscardSelection) { selection in
            leaderDiscardSelectionSheet(selection)
        }
        .sheet(isPresented: $showingDeckReview) {
            deckReviewSheet
        }
        .task {
            await runGwentPollingLoop()
        }
        .onAppear {
            normalizeSelectedDeck()
            applyTableScreenshotArgumentsIfNeeded()
            syncTurnTimerForCurrentState()
            syncHandModeForTurn(animated: false)
        }
        .onReceive(Timer.publish(every: 1, on: .main, in: .common).autoconnect()) { now in
            handleTurnTimerTick(now)
        }
        .onChange(of: model.snapshot?.snapshotVersion ?? "") { _ in
            normalizeSelectedDeck()
        }
        .onChange(of: model.runtimeGwentDecks.map(\.deckId).joined(separator: "|")) { _ in
            normalizeSelectedDeck()
        }
        .onChange(of: selectedDeckId) { _ in
            selectedMulliganCardIds.removeAll()
            normalizePreferredStartingPlayer()
        }
        .onChange(of: activeGwentShouldShowHandMode) { _ in
            syncHandModeForTurn()
        }
        .onChange(of: activeGwentTurnKey) { _ in
            syncTurnTimerForCurrentState()
            syncHandModeForTurn()
        }
        .onChange(of: selectedCardId ?? "") { _ in
            syncBoardFocusForSelectedCard()
        }
    }

    private func landscapeTable(layout: GwentTableLayout) -> some View {
        VStack(spacing: layout.tableStackSpacing) {
            tableHeader(layout: layout)

            if let match = activeMatch, isMatchResolutionVisible(match) {
                matchResolutionPanel(match)
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else if let match = activeMatch {
                if layout.selectionMode {
                    focusedBoard(match: match, layout: layout)
                        .frame(maxWidth: .infinity, maxHeight: .infinity)
                } else {
                    fullBoard(match: match, layout: layout)
                        .frame(maxWidth: .infinity, maxHeight: .infinity)
                }

                handStrip(match: match, layout: layout)
            } else if let challenge = activeChallenge {
                challengeStartPanel(challenge)
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else {
                emptyTablePanel
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            }
        }
        .padding(layout.contentInsets)
    }

    private func fullBoard(match: [String: JSONValue], layout: GwentTableLayout) -> some View {
        let opponentId = opponentPlayerId
        return HStack(spacing: layout.tableColumnSpacing) {
            playerRail(playerId: opponentId, isOpponent: true, layout: layout)

            VStack(spacing: layout.boardRowSpacing) {
                ForEach(opponentRows, id: \.self) { row in
                    boardRow(playerId: opponentId, row: row, isOpponent: true, layout: layout)
                }

                weatherStrip(match: match, layout: layout)

                ForEach(ownRows, id: \.self) { row in
                    boardRow(playerId: ownPlayerId, row: row, isOpponent: false, layout: layout)
                }
            }
            .frame(maxWidth: .infinity)

            playerRail(playerId: ownPlayerId, isOpponent: false, layout: layout)
        }
    }

    private func focusedBoard(match: [String: JSONValue], layout: GwentTableLayout) -> some View {
        let focusIsOpponent = boardFocusSide.isOpponent
        let focusedPlayerId = focusIsOpponent ? opponentPlayerId : ownPlayerId
        let rows = focusIsOpponent ? opponentRows : ownRows

        return HStack(spacing: layout.tableColumnSpacing) {
            playerRail(playerId: focusedPlayerId, isOpponent: focusIsOpponent, layout: layout)

            VStack(spacing: layout.boardRowSpacing) {
                HStack(spacing: layout.isCompact ? 6 : 8) {
                    Label(focusIsOpponent ? "Ряды соперника" : "Ваши ряды", systemImage: focusIsOpponent ? "eye.fill" : "shield.fill")
                        .font(layout.isCompact ? .caption2.bold() : .caption.bold())
                        .foregroundStyle(focusIsOpponent ? .orange.opacity(0.92) : .yellow.opacity(0.92))
                        .lineLimit(1)

                    Spacer()

                    boardFocusToggle(layout: layout)
                }
                .frame(height: layout.weatherStripHeight)
                .padding(.horizontal, layout.isTightPhone ? 6 : 8)
                .background(.black.opacity(0.26))
                .clipShape(RoundedRectangle(cornerRadius: 8))

                ForEach(rows, id: \.self) { row in
                    boardRow(playerId: focusedPlayerId, row: row, isOpponent: focusIsOpponent, layout: layout)
                }
            }
            .frame(maxWidth: .infinity)
        }
    }

    private func boardFocusToggle(layout: GwentTableLayout) -> some View {
        HStack(spacing: 4) {
            Button {
                withAnimation(.spring(response: 0.22, dampingFraction: 0.88)) {
                    boardFocusSide = .own
                }
            } label: {
                Label("Свои", systemImage: "shield.fill")
                    .labelStyle(.iconOnly)
                    .frame(width: layout.isTightPhone ? 26 : 30, height: layout.isTightPhone ? 22 : 24)
            }
            .buttonStyle(.plain)
            .foregroundStyle(boardFocusSide == .own ? .black : .white.opacity(0.72))
            .background(boardFocusSide == .own ? .yellow.opacity(0.92) : .white.opacity(0.10))
            .clipShape(RoundedRectangle(cornerRadius: 7))
            .accessibilityLabel("Показать свои ряды")

            Button {
                withAnimation(.spring(response: 0.22, dampingFraction: 0.88)) {
                    boardFocusSide = .opponent
                }
            } label: {
                Label("Чужие", systemImage: "eye.fill")
                    .labelStyle(.iconOnly)
                    .frame(width: layout.isTightPhone ? 26 : 30, height: layout.isTightPhone ? 22 : 24)
            }
            .buttonStyle(.plain)
            .foregroundStyle(boardFocusSide == .opponent ? .black : .white.opacity(0.72))
            .background(boardFocusSide == .opponent ? .orange.opacity(0.92) : .white.opacity(0.10))
            .clipShape(RoundedRectangle(cornerRadius: 7))
            .accessibilityLabel("Показать ряды соперника")
        }
    }

    private func tableHeader(layout: GwentTableLayout) -> some View {
        HStack(spacing: layout.isCompact ? 7 : 10) {
            Button {
                dismiss()
            } label: {
                Image(systemName: "xmark")
                    .font(layout.isCompact ? .subheadline.bold() : .headline.bold())
                    .frame(width: layout.isCompact ? 32 : 36, height: layout.tableHeaderHeight)
            }
            .buttonStyle(.plain)
            .background(.black.opacity(0.28))
            .clipShape(RoundedRectangle(cornerRadius: 8))

            VStack(alignment: .leading, spacing: 1) {
                Text(tableTitle)
                    .font(layout.isCompact ? .caption.bold() : .headline.bold())
                    .lineLimit(1)
                Text(tableSubtitle)
                    .font(layout.isCompact ? .caption2 : .caption)
                    .foregroundStyle(.white.opacity(0.68))
                    .lineLimit(1)
            }

            Spacer()

            if let stake = activeStake, !stakeIsPractice(stake) {
                stakePill(stake)
            }

            if activeTurnCountdownSeconds != nil {
                turnCountdownPill(layout: layout)
            }

            if let root = gwentStateRoot, activeGwentPlayerSubmitted(root) {
                Label("Ход отправлен", systemImage: "checkmark.circle.fill")
                    .font(.caption.bold())
                    .foregroundStyle(.green)
                    .padding(.horizontal, 10)
                    .padding(.vertical, 7)
                    .background(.black.opacity(0.24))
                    .clipShape(RoundedRectangle(cornerRadius: 8))
            }

            Button {
                Task { await model.refreshPvpState() }
            } label: {
                Image(systemName: "arrow.clockwise")
                    .font(layout.isCompact ? .subheadline.bold() : .headline.bold())
                    .frame(width: layout.isCompact ? 34 : 40, height: layout.tableHeaderHeight)
            }
            .buttonStyle(.plain)
            .background(.black.opacity(0.28))
            .clipShape(RoundedRectangle(cornerRadius: 8))
            .accessibilityLabel("Обновить Гвинт")
        }
        .foregroundStyle(.white)
        .frame(height: layout.tableHeaderHeight)
    }

    private func playerRail(playerId: String, isOpponent: Bool, layout: GwentTableLayout) -> some View {
        let id = playerId.isEmpty ? (isOpponent ? "opponent" : ownPlayerId) : playerId
        let state = deckState(playerId: id)
        let graveyard = state.arrayStrings("graveyard")
        let remainingDeck = state.int("draw_pile_count", default: state.arrayStrings("draw_pile").count)
        let handCount = isOpponent ? state.int("hand_count", default: state.arrayStrings("hand").count) : activeGwentHand.count
        let faction = gwentFactionForPlayer(id)

        return VStack(spacing: layout.railSpacing) {
            Text(isOpponent ? "Соперник" : "Вы")
                .font(.caption2.bold())
                .foregroundStyle(.white.opacity(0.58))
                .textCase(.uppercase)
                .lineLimit(1)

            Text(gwentPlayerName(id))
                .font(layout.isCompact ? .caption2.bold() : .caption.bold())
                .multilineTextAlignment(.center)
                .lineLimit(layout.isTightPhone ? 1 : 2)
                .minimumScaleFactor(0.56)

            if layout.showsExpandedRails {
                factionBadge(faction)
            }

            Text("\(playerTotal(playerId: id))")
                .font(.system(size: layout.isTightPhone ? 26 : (layout.isCompact ? 30 : 38), weight: .black, design: .rounded))
                .frame(
                    width: layout.isTightPhone ? 46 : (layout.isCompact ? 52 : 64),
                    height: layout.isTightPhone ? 34 : (layout.isCompact ? 40 : 54)
                )
                .background(scoreColor(for: id).opacity(0.2))
                .overlay(
                    RoundedRectangle(cornerRadius: 8)
                        .stroke(scoreColor(for: id).opacity(0.6), lineWidth: 1)
                )
                .clipShape(RoundedRectangle(cornerRadius: 8))

            roundLifeGems(playerId: id)

            VStack(spacing: 4) {
                railMetric(layout.isTightPhone ? "Р" : "Рука", "\(handCount)", layout: layout)
                railMetric(layout.isTightPhone ? "К" : "Колода", remainingDeck == 0 ? "-" : "\(remainingDeck)", layout: layout)
                Button {
                    inspectedPilePlayerId = id
                    inspectedPileTitle = isOpponent ? "Сброс соперника" : "Ваш сброс"
                } label: {
                    railMetric(layout.isTightPhone ? "С" : "Сброс", "\(graveyard.count)", layout: layout)
                }
                .buttonStyle(.plain)
                .disabled(graveyard.isEmpty)
            }

            Spacer(minLength: 0)

            Text(playerReadiness(id))
                .font(.caption2.bold())
                .foregroundStyle(readinessColor(id))
                .lineLimit(1)
                .minimumScaleFactor(0.62)
                .padding(.horizontal, layout.isTightPhone ? 4 : 8)
                .padding(.vertical, layout.isTightPhone ? 4 : 6)
                .frame(maxWidth: .infinity)
                .background(.black.opacity(0.22))
                .clipShape(RoundedRectangle(cornerRadius: 8))
        }
        .foregroundStyle(.white)
        .padding(layout.isTightPhone ? 4 : (layout.isCompact ? 6 : 8))
        .frame(width: layout.playerRailWidth)
        .background(.black.opacity(0.18))
        .overlay(
            RoundedRectangle(cornerRadius: 8)
                .stroke(.white.opacity(0.12), lineWidth: 1)
        )
        .clipShape(RoundedRectangle(cornerRadius: 8))
    }

    private func railMetric(_ title: String, _ value: String, layout: GwentTableLayout) -> some View {
        HStack {
            Text(title)
                .font(.caption2)
                .foregroundStyle(.white.opacity(0.58))
            Spacer(minLength: 4)
            Text(value)
                .font(layout.isCompact ? .caption2.bold() : .caption.bold())
        }
    }

    private func stakePill(_ stake: [String: JSONValue]) -> some View {
        Label(stakeLabel(stake), systemImage: stakeIcon(stake))
            .font(.caption.bold())
            .foregroundStyle(stakeColor(stake))
            .lineLimit(1)
            .padding(.horizontal, 10)
            .padding(.vertical, 7)
            .background(.black.opacity(0.24))
            .overlay(
                RoundedRectangle(cornerRadius: 8)
                    .stroke(stakeColor(stake).opacity(0.42), lineWidth: 1)
            )
            .clipShape(RoundedRectangle(cornerRadius: 8))
    }

    private func turnCountdownPill(layout: GwentTableLayout) -> some View {
        let remaining = activeTurnCountdownSeconds ?? turnLimitSeconds
        let isOwnTurn = activeGwentIsPlayerTurn
        let isUrgent = remaining <= 10
        let color: Color = isUrgent ? .red : (isOwnTurn ? .yellow : .white.opacity(0.72))
        return Label("\(turnCountdownPrefix) \(formatTurnCountdown(remaining))", systemImage: "timer")
            .font(layout.isCompact ? .caption2.bold() : .caption.bold())
            .foregroundStyle(color)
            .lineLimit(1)
            .minimumScaleFactor(0.68)
            .padding(.horizontal, layout.isTightPhone ? 8 : 10)
            .padding(.vertical, layout.isTightPhone ? 6 : 7)
            .background(.black.opacity(0.26))
            .overlay(
                RoundedRectangle(cornerRadius: 8)
                    .stroke(color.opacity(isUrgent ? 0.62 : 0.38), lineWidth: 1)
            )
            .clipShape(RoundedRectangle(cornerRadius: 8))
            .accessibilityLabel("\(turnCountdownPrefix): \(remaining) секунд")
    }

    private func stakeBanner(_ stake: [String: JSONValue], prefix: String) -> some View {
        HStack(spacing: 8) {
            Image(systemName: stakeIcon(stake))
                .foregroundStyle(stakeColor(stake))
                .frame(width: 22)
            VStack(alignment: .leading, spacing: 2) {
                Text(prefix)
                    .font(.caption2.bold())
                    .foregroundStyle(.white.opacity(0.52))
                    .textCase(.uppercase)
                Text(stakeLabel(stake))
                    .font(.caption.bold())
                    .foregroundStyle(.white)
                    .lineLimit(1)
                    .minimumScaleFactor(0.72)
            }
            Spacer(minLength: 6)
            Text(stakeStatusLabel(stake))
                .font(.caption2.bold())
                .foregroundStyle(stakeColor(stake))
                .lineLimit(1)
        }
        .padding(.horizontal, 10)
        .padding(.vertical, 8)
        .background(.black.opacity(0.22))
        .overlay(
            RoundedRectangle(cornerRadius: 8)
                .stroke(stakeColor(stake).opacity(0.32), lineWidth: 1)
        )
        .clipShape(RoundedRectangle(cornerRadius: 8))
    }

    private func roundLifeGems(playerId: String) -> some View {
        let wins = roundWins(playerId)
        return HStack(spacing: 5) {
            ForEach(0..<2, id: \.self) { index in
                Image(systemName: index < wins ? "diamond.fill" : "diamond")
                    .font(.caption2.bold())
                    .foregroundStyle(index < wins ? .yellow.opacity(0.94) : .white.opacity(0.44))
            }
        }
        .frame(height: 18)
        .padding(.horizontal, 6)
        .background(.black.opacity(0.2))
        .clipShape(RoundedRectangle(cornerRadius: 7))
        .accessibilityLabel("Победы в раундах: \(wins) из 2")
    }

    private func boardRow(playerId: String, row: String, isOpponent: Bool, layout: GwentTableLayout) -> some View {
        let cards = boardCards(playerId: playerId, row: row)
        let actionMode = selectedCardId != nil && activeGwentCanPlay
        let isPlayableTarget = selectedCardCanPlay(row: row, isOpponent: isOpponent)
        let isEffectTarget = selectedCardHighlightsRow(row: row, playerId: playerId, isOpponent: isOpponent)
        let activeEffects = activeRowEffects(playerId: playerId, row: row)
        let shouldDim = actionMode && !isPlayableTarget && !isEffectTarget && !selectedCardHighlightsAnyCard(in: cards, playerId: playerId)
        return HStack(spacing: layout.isCompact ? 5 : 7) {
            VStack(spacing: 1) {
                Image(systemName: gwentRowIcon(row))
                    .font(layout.isCompact ? .caption2.bold() : .caption.bold())
                Text("\(rowScore(playerId: playerId, row: row, cards: cards))")
                    .font(layout.isCompact ? .caption2.bold() : .caption.bold())
            }
            .foregroundStyle(gwentRowColor(row))
            .frame(width: layout.boardRowIconSize, height: layout.boardRowIconSize)
            .background(.black.opacity(0.24))
            .clipShape(RoundedRectangle(cornerRadius: 8))

            if !activeEffects.isEmpty {
                rowEffectBadges(activeEffects, layout: layout)
            }

            ScrollView(.horizontal, showsIndicators: false) {
                LazyHStack(spacing: layout.isCompact ? 4 : 5) {
                    if cards.isEmpty {
                        emptyRowLabel(row, layout: layout)
                    } else {
                        ForEach(Array(cards.enumerated()), id: \.offset) { _, card in
                            let cardHighlighted = selectedBoardCardIsHighlighted(card, playerId: playerId)
                            let cardDimmed = actionMode && selectedCardDimsUnrelatedBoardCards && !cardHighlighted
                            boardCardTile(
                                card,
                                playerId: playerId,
                                row: row,
                                rowCards: cards,
                                layout: layout,
                                highlighted: cardHighlighted,
                                dimmed: cardDimmed
                            )
                        }
                    }
                }
                .frame(maxWidth: .infinity, alignment: isOpponent ? .trailing : .leading)
            }

            if actionMode && (isPlayableTarget || isEffectTarget) {
                Text(isPlayableTarget ? "Сюда" : selectedRowEffectLabel(row: row))
                    .font(.system(size: layout.isTightPhone ? 8 : 9, weight: .black))
                    .foregroundStyle(isPlayableTarget ? .black : selectedCardActionColor(selectedCardId ?? ""))
                    .lineLimit(1)
                    .minimumScaleFactor(0.58)
                    .padding(.horizontal, layout.isTightPhone ? 5 : 7)
                    .padding(.vertical, 4)
                    .background(isPlayableTarget ? .yellow.opacity(0.95) : .black.opacity(0.34))
                    .clipShape(Capsule())
            }
        }
        .padding(layout.isTightPhone ? 3 : (layout.isCompact ? 4 : 5))
        .frame(height: layout.boardRowHeight)
        .background(
            boardRowBackgroundView(
                row: row,
                activeEffects: activeEffects,
                playable: isPlayableTarget,
                effectTarget: isEffectTarget
            )
        )
        .overlay(
            RoundedRectangle(cornerRadius: 8)
                .stroke(
                    dropTargetRow == rowDropKey(row, isOpponent: isOpponent)
                        ? .yellow.opacity(0.92)
                        : boardRowStrokeColor(
                            row: row,
                            activeEffects: activeEffects,
                            playable: isPlayableTarget,
                            effectTarget: isEffectTarget
                        ),
                    lineWidth: dropTargetRow == rowDropKey(row, isOpponent: isOpponent) || isPlayableTarget || isEffectTarget || !activeEffects.isEmpty ? 2 : 1
                )
        )
        .opacity(shouldDim ? 0.42 : 1)
        .clipShape(RoundedRectangle(cornerRadius: 8))
        .contentShape(Rectangle())
        .onTapGesture {
            guard let match = activeMatch, let selectedCardId else { return }
            if selectedCardPlaysWithoutSpecificRow(selectedCardId) && selectedCardHighlightsRow(row: row, playerId: playerId, isOpponent: isOpponent) {
                Task { await play(cardId: selectedCardId, on: nil, match: match) }
                return
            }
            guard cardCanUseBoardSide(selectedCardId, isOpponent: isOpponent) else {
                model.errorMessage = wrongSideMessage(for: selectedCardId)
                return
            }
            guard selectedCardCanPlay(row: row, isOpponent: isOpponent) else { return }
            Task { await play(cardId: selectedCardId, on: row, match: match) }
        }
        .onDrop(
            of: [UTType.plainText],
            isTargeted: Binding(
                get: { dropTargetRow == rowDropKey(row, isOpponent: isOpponent) },
                set: { isTargeted in dropTargetRow = isTargeted ? rowDropKey(row, isOpponent: isOpponent) : nil }
            )
        ) { providers in
            guard let match = activeMatch else { return false }
            return handleCardDrop(providers, row: row, isOpponent: isOpponent, match: match)
        }
    }

    private func weatherStrip(match: [String: JSONValue], layout: GwentTableLayout) -> some View {
        let roundNumber = activeGwentRoundNumber
        let history = roundHistoryText(match)
        let weatherEffects = activeWeatherEffectInfos()
        let revealInfo = privateRevealEffectInfo()
        return HStack(spacing: layout.isCompact ? 6 : 8) {
            Text("Раунд \(roundNumber)")
                .font(layout.isCompact ? .caption2.bold() : .caption.bold())
            Divider()
                .frame(height: layout.isCompact ? 14 : 18)
                .overlay(.white.opacity(0.25))
            if weatherEffects.isEmpty {
                Label("Погоды нет", systemImage: "sun.max.fill")
                    .font(.caption2.bold())
                    .foregroundStyle(.white.opacity(0.64))
                    .lineLimit(1)
                    .minimumScaleFactor(0.62)
            } else {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 4) {
                        ForEach(weatherEffects) { effect in
                            effectChip(effect, layout: layout, compactLabel: layout.isTightPhone)
                        }
                    }
                }
                .frame(maxWidth: layout.isTightPhone ? 132 : 240, alignment: .leading)
            }
            if !history.isEmpty, !layout.isTightPhone {
                Divider()
                    .frame(height: layout.isCompact ? 14 : 18)
                    .overlay(.white.opacity(0.25))
                Text(history)
                    .font(.caption2.bold())
                    .foregroundStyle(.white.opacity(0.62))
                    .lineLimit(1)
            }
            if let revealInfo {
                Divider()
                    .frame(height: layout.isCompact ? 14 : 18)
                    .overlay(.white.opacity(0.25))
                effectChip(revealInfo, layout: layout, compactLabel: layout.isTightPhone)
            }
            Spacer()
            Text(gwentStatusLabel(roundStatus))
                .font(layout.isCompact ? .caption2.bold() : .caption.bold())
                .foregroundStyle(.white.opacity(0.68))
        }
        .foregroundStyle(.white)
        .padding(.horizontal, layout.isTightPhone ? 6 : (layout.isCompact ? 8 : 10))
        .frame(height: layout.weatherStripHeight)
        .background(.black.opacity(0.28))
        .clipShape(RoundedRectangle(cornerRadius: 8))
    }

    private func rowEffectBadges(_ effects: [GwentEffectInfo], layout: GwentTableLayout) -> some View {
        HStack(spacing: layout.isTightPhone ? 3 : 4) {
            ForEach(effects) { effect in
                effectChip(effect, layout: layout, compactLabel: layout.isTightPhone)
            }
        }
        .frame(width: layout.isTightPhone ? CGFloat(effects.count * 26) : nil)
    }

    private func effectChip(
        _ effect: GwentEffectInfo,
        layout: GwentTableLayout,
        compactLabel: Bool = false
    ) -> some View {
        Button {
            withAnimation(.spring(response: 0.22, dampingFraction: 0.88)) {
                activeEffectInfo = effect
            }
        } label: {
            HStack(spacing: compactLabel ? 0 : 4) {
                Image(systemName: effect.icon)
                    .font(.system(size: layout.isTightPhone ? 8 : 9, weight: .black))
                    .frame(width: layout.isTightPhone ? 18 : 20, height: layout.isTightPhone ? 18 : 20)

                if !compactLabel {
                    Text(effect.badge)
                        .font(.system(size: layout.isTightPhone ? 8 : 9, weight: .black))
                        .lineLimit(1)
                        .minimumScaleFactor(0.62)
                }
            }
            .foregroundStyle(effect.usesDarkText ? .black : .white)
            .padding(.leading, compactLabel ? 0 : 5)
            .padding(.trailing, compactLabel ? 0 : 7)
            .frame(height: layout.isTightPhone ? 20 : 22)
            .background(effect.color.opacity(effect.usesDarkText ? 0.90 : 0.72))
            .overlay(
                Capsule()
                    .stroke(.white.opacity(0.30), lineWidth: 1)
            )
            .clipShape(Capsule())
        }
        .buttonStyle(.plain)
        .accessibilityLabel("\(effect.title). \(effect.subtitle)")
    }

    private func effectInfoPlaque(_ info: GwentEffectInfo, layout: GwentTableLayout) -> some View {
        ZStack(alignment: .topTrailing) {
            Color.black.opacity(0.001)
                .onTapGesture {
                    withAnimation(.spring(response: 0.22, dampingFraction: 0.9)) {
                        activeEffectInfo = nil
                    }
                }

            VStack(alignment: .leading, spacing: layout.isTightPhone ? 6 : 8) {
                HStack(alignment: .top, spacing: 8) {
                    Image(systemName: info.icon)
                        .font(layout.isTightPhone ? .caption.bold() : .headline.bold())
                        .foregroundStyle(info.color)
                        .frame(width: layout.isTightPhone ? 24 : 28, height: layout.isTightPhone ? 24 : 28)
                        .background(info.color.opacity(0.16))
                        .clipShape(Circle())

                    VStack(alignment: .leading, spacing: 2) {
                        Text(info.title)
                            .font(layout.isTightPhone ? .caption.bold() : .subheadline.bold())
                            .foregroundStyle(.white)
                            .lineLimit(1)
                            .minimumScaleFactor(0.68)
                        Text(info.subtitle)
                            .font(.caption2.bold())
                            .foregroundStyle(info.color.opacity(0.92))
                            .lineLimit(1)
                            .minimumScaleFactor(0.62)
                    }

                    Spacer(minLength: 8)

                    Button {
                        withAnimation(.spring(response: 0.22, dampingFraction: 0.9)) {
                            activeEffectInfo = nil
                        }
                    } label: {
                        Image(systemName: "xmark")
                            .font(.caption.bold())
                            .frame(width: 24, height: 24)
                    }
                    .buttonStyle(.plain)
                    .foregroundStyle(.white.opacity(0.76))
                    .background(.white.opacity(0.08))
                    .clipShape(Circle())
                    .accessibilityLabel("Закрыть описание эффекта")
                }

                Text(info.body)
                    .font(.system(size: layout.isTightPhone ? 10 : 12, weight: .semibold))
                    .foregroundStyle(.white.opacity(0.82))
                    .lineLimit(layout.isTightPhone ? 3 : 4)
                    .minimumScaleFactor(0.74)
                    .fixedSize(horizontal: false, vertical: true)
            }
            .padding(layout.isTightPhone ? 10 : 12)
            .frame(width: min(layout.contentWidth * (layout.isTightPhone ? 0.64 : 0.54), layout.isTightPhone ? 300 : 390))
            .background(
                LinearGradient(
                    colors: [
                        Color(red: 0.13, green: 0.095, blue: 0.065).opacity(0.96),
                        Color(red: 0.035, green: 0.030, blue: 0.026).opacity(0.98)
                    ],
                    startPoint: .topLeading,
                    endPoint: .bottomTrailing
                )
            )
            .overlay(
                RoundedRectangle(cornerRadius: 10)
                    .stroke(info.color.opacity(0.48), lineWidth: 1)
            )
            .clipShape(RoundedRectangle(cornerRadius: 10))
            .shadow(color: .black.opacity(0.46), radius: 18, y: 8)
            .padding(.top, layout.contentInsets.top + layout.tableHeaderHeight + 6)
            .padding(.trailing, layout.contentInsets.trailing)
        }
    }

    private func leaderActivationPlaque(_ activation: GwentLeaderActivation, layout: GwentTableLayout) -> some View {
        let info = activation.effectInfo
        let canActivate = activeGwentCanUseLeader && !isSubmittingGwentAction
        return ZStack(alignment: .topTrailing) {
            Color.black.opacity(0.001)
                .onTapGesture {
                    withAnimation(.spring(response: 0.22, dampingFraction: 0.9)) {
                        pendingLeaderActivation = nil
                    }
                }

            VStack(alignment: .leading, spacing: layout.isTightPhone ? 7 : 9) {
                HStack(alignment: .top, spacing: 8) {
                    Image(systemName: info.icon)
                        .font(layout.isTightPhone ? .caption.bold() : .headline.bold())
                        .foregroundStyle(info.color)
                        .frame(width: layout.isTightPhone ? 24 : 28, height: layout.isTightPhone ? 24 : 28)
                        .background(info.color.opacity(0.16))
                        .clipShape(Circle())

                    VStack(alignment: .leading, spacing: 2) {
                        Text(info.title)
                            .font(layout.isTightPhone ? .caption.bold() : .subheadline.bold())
                            .foregroundStyle(.white)
                            .lineLimit(1)
                            .minimumScaleFactor(0.68)
                        Text(info.subtitle)
                            .font(.caption2.bold())
                            .foregroundStyle(info.color.opacity(0.92))
                            .lineLimit(1)
                            .minimumScaleFactor(0.62)
                    }

                    Spacer(minLength: 8)

                    Button {
                        withAnimation(.spring(response: 0.22, dampingFraction: 0.9)) {
                            pendingLeaderActivation = nil
                        }
                    } label: {
                        Image(systemName: "xmark")
                            .font(.caption.bold())
                            .frame(width: 24, height: 24)
                    }
                    .buttonStyle(.plain)
                    .foregroundStyle(.white.opacity(0.76))
                    .background(.white.opacity(0.08))
                    .clipShape(Circle())
                    .accessibilityLabel("Закрыть способность лидера")
                }

                Text(info.body)
                    .font(.system(size: layout.isTightPhone ? 10 : 12, weight: .semibold))
                    .foregroundStyle(.white.opacity(0.84))
                    .lineLimit(layout.isTightPhone ? 3 : 5)
                    .minimumScaleFactor(0.72)
                    .fixedSize(horizontal: false, vertical: true)

                HStack(spacing: layout.isTightPhone ? 7 : 9) {
                    Button {
                        withAnimation(.spring(response: 0.22, dampingFraction: 0.9)) {
                            pendingLeaderActivation = nil
                        }
                    } label: {
                        Text("Отмена")
                            .font(layout.isTightPhone ? .caption2.bold() : .caption.bold())
                            .frame(height: layout.actionButtonHeight)
                            .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.plain)
                    .foregroundStyle(.white.opacity(0.78))
                    .background(.white.opacity(0.08))
                    .overlay(
                        RoundedRectangle(cornerRadius: 7)
                            .stroke(.white.opacity(0.16), lineWidth: 1)
                    )
                    .clipShape(RoundedRectangle(cornerRadius: 7))

                    Button {
                        pendingLeaderActivation = nil
                        Task { await useLeader(match: activation.match) }
                    } label: {
                        HStack(spacing: 5) {
                            if isSubmittingGwentAction {
                                ProgressView()
                                    .controlSize(.small)
                                    .tint(.black)
                            }
                            Label("Активировать", systemImage: "bolt.fill")
                                .labelStyle(.titleAndIcon)
                        }
                        .font(layout.isTightPhone ? .caption2.bold() : .caption.bold())
                        .lineLimit(1)
                        .minimumScaleFactor(0.68)
                        .frame(height: layout.actionButtonHeight)
                        .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.plain)
                    .foregroundStyle(.black)
                    .background(canActivate ? info.color.opacity(0.92) : .white.opacity(0.28))
                    .overlay(
                        RoundedRectangle(cornerRadius: 7)
                            .stroke(info.color.opacity(canActivate ? 0.52 : 0.18), lineWidth: 1)
                    )
                    .clipShape(RoundedRectangle(cornerRadius: 7))
                    .disabled(!canActivate)
                    .accessibilityLabel("Активировать лидера: \(info.title)")
                }
            }
            .padding(layout.isTightPhone ? 10 : 12)
            .frame(width: min(layout.contentWidth * (layout.isTightPhone ? 0.66 : 0.56), layout.isTightPhone ? 316 : 420))
            .background(
                LinearGradient(
                    colors: [
                        Color(red: 0.13, green: 0.095, blue: 0.065).opacity(0.97),
                        Color(red: 0.035, green: 0.030, blue: 0.026).opacity(0.99)
                    ],
                    startPoint: .topLeading,
                    endPoint: .bottomTrailing
                )
            )
            .overlay(
                RoundedRectangle(cornerRadius: 10)
                    .stroke(info.color.opacity(0.54), lineWidth: 1)
            )
            .clipShape(RoundedRectangle(cornerRadius: 10))
            .shadow(color: .black.opacity(0.48), radius: 18, y: 8)
            .padding(.top, layout.contentInsets.top + layout.tableHeaderHeight + 6)
            .padding(.trailing, layout.contentInsets.trailing)
        }
    }

    private func handStrip(match: [String: JSONValue], layout: GwentTableLayout) -> some View {
        let canPlay = activeGwentCanPlay
        let handMode = activeGwentShouldShowHandMode && handExpanded
        let actionMode = canPlay && selectedCardId != nil
        return VStack(spacing: layout.handInternalSpacing) {
            if handMode {
                if actionMode, let selectedCardId {
                    selectedCardActionHeader(cardId: selectedCardId, match: match, layout: layout)
                } else {
                    handCommandBar(match: match, layout: layout)
                }
                handCardsScroll(canPlay: canPlay, layout: layout, actionMode: actionMode)
            } else {
                collapsedHandPlaque(match: match, layout: layout)
            }
        }
        .padding(layout.handStripPadding)
        .frame(height: handMode ? layout.handExpandedHeight : layout.handCollapsedHeight)
        .background(.black.opacity(0.26))
        .overlay(
            RoundedRectangle(cornerRadius: 8)
                .stroke(.white.opacity(0.12), lineWidth: 1)
        )
        .clipShape(RoundedRectangle(cornerRadius: 8))
    }

    private func collapsedHandPlaque(match: [String: JSONValue], layout: GwentTableLayout) -> some View {
        HStack(spacing: layout.isCompact ? 6 : 8) {
            Button {
                guard activeGwentShouldShowHandMode else { return }
                withAnimation(.spring(response: 0.24, dampingFraction: 0.84)) {
                    handExpanded = true
                    syncBoardFocusForSelectedCard()
                }
            } label: {
                Label("Рука \(activeGwentHand.count)", systemImage: "chevron.up")
                    .font(layout.isCompact ? .caption2.bold() : .caption.bold())
                    .frame(width: layout.isTightPhone ? 82 : (layout.isCompact ? 96 : 110), height: layout.actionButtonHeight)
            }
            .buttonStyle(.bordered)
            .tint(.yellow)
            .disabled(!activeGwentShouldShowHandMode)

            Text(activeGwentTurnText)
                .font(layout.isCompact ? .caption2.bold() : .caption.bold())
                .foregroundStyle(activeGwentShouldShowHandMode ? .yellow : .white.opacity(0.58))
                .lineLimit(1)
                .minimumScaleFactor(0.68)

            Spacer(minLength: 0)

            if isSubmittingGwentAction {
                ProgressView()
                    .controlSize(.small)
                    .tint(.yellow)
            }

            passButton(match: match, layout: layout)
        }
    }

    private func handCommandBar(match: [String: JSONValue], layout: GwentTableLayout) -> some View {
        HStack(spacing: layout.isCompact ? 6 : 8) {
            Button {
                withAnimation(.spring(response: 0.24, dampingFraction: 0.84)) {
                    handExpanded = false
                }
            } label: {
                Image(systemName: "chevron.down")
                    .font(layout.isCompact ? .caption.bold() : .subheadline.bold())
                    .frame(width: layout.actionButtonHeight, height: layout.actionButtonHeight)
            }
            .buttonStyle(.plain)
            .foregroundStyle(.yellow)
            .background(.yellow.opacity(0.24))
            .overlay(
                RoundedRectangle(cornerRadius: 7)
                    .stroke(.yellow.opacity(0.28), lineWidth: 1)
            )
            .clipShape(RoundedRectangle(cornerRadius: 7))
            .accessibilityLabel("Свернуть руку")

            Text(activeGwentTurnText)
                .font(layout.isCompact ? .caption2.bold() : .caption.bold())
                .foregroundStyle(activeGwentCanPlay ? .yellow : .white.opacity(0.58))
                .lineLimit(1)
                .minimumScaleFactor(0.68)

            if isSubmittingGwentAction {
                ProgressView()
                    .controlSize(.small)
                    .tint(.yellow)
            }

            Spacer(minLength: 0)

            passButton(match: match, layout: layout)

            if activeGwentCanUseLeader {
                Button {
                    showLeaderActivation(match: match)
                } label: {
                    Label("Лидер", systemImage: "crown.fill")
                        .font(layout.isCompact ? .caption2.bold() : .caption.bold())
                        .frame(width: layout.isTightPhone ? 78 : (layout.isCompact ? 90 : 104), height: layout.actionButtonHeight)
                }
                .buttonStyle(.plain)
                .foregroundStyle(.black)
                .background(.yellow.opacity(0.92))
                .overlay(
                    RoundedRectangle(cornerRadius: 7)
                        .stroke(.yellow.opacity(0.48), lineWidth: 1)
                )
                .clipShape(RoundedRectangle(cornerRadius: 7))
            }
        }
        .frame(height: layout.actionButtonHeight)
    }

    private func passButton(match: [String: JSONValue], layout: GwentTableLayout) -> some View {
        Button {
            Task { await pass(match: match) }
        } label: {
            Label("Пас", systemImage: "hand.raised.fill")
                .font(layout.isCompact ? .caption2.bold() : .caption.bold())
                .frame(width: layout.isTightPhone ? 70 : (layout.isCompact ? 84 : 100), height: layout.actionButtonHeight)
        }
        .buttonStyle(.plain)
        .foregroundStyle(activeGwentCanPass ? .yellow : .white.opacity(0.38))
        .background(activeGwentCanPass ? .orange.opacity(0.36) : .white.opacity(0.08))
        .overlay(
            RoundedRectangle(cornerRadius: 7)
                .stroke(activeGwentCanPass ? .orange.opacity(0.38) : .white.opacity(0.10), lineWidth: 1)
        )
        .clipShape(RoundedRectangle(cornerRadius: 7))
        .disabled(!activeGwentCanPass)
    }

    private func handCardsScroll(canPlay: Bool, layout: GwentTableLayout, actionMode: Bool) -> some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: layout.handCardSpacing) {
                if activeGwentHand.isEmpty {
                    Text("Рука пуста")
                        .font(.caption.bold())
                        .foregroundStyle(.white.opacity(0.58))
                        .frame(width: layout.handCardWidth, height: layout.handCardHeight)
                        .overlay(
                            RoundedRectangle(cornerRadius: 8)
                                .stroke(.white.opacity(0.16), style: StrokeStyle(lineWidth: 1, dash: [4, 4]))
                        )
                } else {
                    ForEach(activeGwentHand, id: \.self) { cardId in
                        let isSelected = selectedCardId == cardId
                        Button {
                            withAnimation(.spring(response: 0.24, dampingFraction: 0.86)) {
                                selectedCardId = isSelected ? nil : cardId
                                if !isSelected {
                                    boardFocusSide = boardFocusSide(for: cardId)
                                }
                            }
                        } label: {
                            handCard(cardId, selected: isSelected, enabled: canPlay, layout: layout)
                                .opacity(actionMode && !isSelected ? 0.66 : 1)
                                .offset(y: isSelected ? -layout.selectedHandLift : 0)
                        }
                        .buttonStyle(.plain)
                        .disabled(!canPlay)
                        .onDrag {
                            selectedCardId = cardId
                            boardFocusSide = boardFocusSide(for: cardId)
                            return NSItemProvider(object: cardId as NSString)
                        }
                    }
                }
            }
            .padding(.horizontal, 2)
            .padding(.top, actionMode ? layout.selectedHandLift + 2 : 0)
        }
    }

    private func selectedCardActionHeader(cardId: String, match: [String: JSONValue], layout: GwentTableLayout) -> some View {
        HStack(alignment: .center, spacing: layout.isTightPhone ? 8 : 10) {
            selectedCardEffectSummary(cardId: cardId, layout: layout)
                .frame(maxWidth: .infinity, alignment: .leading)

            selectedCardControls(cardId: cardId, match: match, layout: layout)
                .frame(width: layout.selectedActionControlsWidth, alignment: .trailing)

            if isSubmittingGwentAction {
                ProgressView()
                    .controlSize(.small)
                    .tint(.yellow)
            }
        }
        .padding(.horizontal, layout.isTightPhone ? 6 : 8)
        .padding(.vertical, layout.isTightPhone ? 2 : 4)
        .frame(height: layout.actionPanelHeight)
        .background(selectedCardActionColor(cardId).opacity(0.14))
        .overlay(
            RoundedRectangle(cornerRadius: 8)
                .stroke(selectedCardActionColor(cardId).opacity(0.42), lineWidth: 1)
        )
        .clipShape(RoundedRectangle(cornerRadius: 8))
    }

    private func selectedCardEffectSummary(cardId: String, layout: GwentTableLayout) -> some View {
        let effects = selectedCardEffectKeys(cardId)
        return ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: layout.isTightPhone ? 5 : 7) {
                if effects.isEmpty {
                    HStack(spacing: layout.isTightPhone ? 5 : 6) {
                        Image(systemName: selectedCardActionIcon(cardId))
                            .font(.system(size: layout.isTightPhone ? 11 : 13, weight: .black))
                        Text("Выставление")
                            .font(layout.isCompact ? .caption.bold() : .subheadline.bold())
                    }
                    .foregroundStyle(.white)
                    .padding(.horizontal, layout.isTightPhone ? 8 : 10)
                    .frame(height: layout.isCompact ? 26 : 30)
                    .background(.black.opacity(0.32))
                    .overlay(
                        Capsule()
                            .stroke(.white.opacity(0.18), lineWidth: 1)
                    )
                    .clipShape(Capsule())
                } else {
                    ForEach(effects, id: \.self) { effect in
                        HStack(spacing: layout.isTightPhone ? 4 : 5) {
                            Image(systemName: gwentEffectIcon(effect))
                                .font(.system(size: layout.isTightPhone ? 11 : 13, weight: .black))
                                .frame(width: layout.isTightPhone ? 18 : 21, height: layout.isTightPhone ? 18 : 21)
                                .background(.white.opacity(0.18))
                                .clipShape(Circle())

                            if !layout.isTightPhone {
                                Text(gwentEffectBadge(effect))
                                    .font(.system(size: layout.isCompact ? 11 : 12, weight: .black))
                                    .lineLimit(1)
                                    .minimumScaleFactor(0.68)
                            }
                        }
                        .foregroundStyle(effect == "clear_weather" ? .black : .white)
                        .padding(.leading, layout.isTightPhone ? 3 : 5)
                        .padding(.trailing, layout.isTightPhone ? 3 : 8)
                        .frame(height: layout.isCompact ? 26 : 30)
                        .background(gwentEffectColor(effect).opacity(effect == "clear_weather" ? 0.92 : 0.74))
                        .overlay(
                            Capsule()
                                .stroke(.white.opacity(0.28), lineWidth: 1)
                        )
                        .clipShape(Capsule())
                        .accessibilityLabel(gwentEffectTitle(effect))
                    }
                }
            }
            .frame(height: layout.actionButtonHeight)
        }
    }

    private func handCard(
        _ cardId: String,
        selected: Bool,
        enabled: Bool,
        layout providedLayout: GwentTableLayout? = nil,
        featured: Bool = false
    ) -> some View {
        let layout = providedLayout ?? fallbackTableLayout
        let meta = gwentCardMeta(cardId)
        let row = meta?.row ?? "card"
        let effects = meta.map(gwentCardEffects) ?? []
        let primaryEffect = effects.first
        let cardWidth = featured ? layout.focusedHandCardWidth : layout.handCardWidth
        let cardHeight = featured ? layout.focusedHandCardHeight : layout.handCardHeight

        return ZStack(alignment: .topLeading) {
            gwentBattleArtwork(cardId: cardId, row: row, compact: layout.isCompact)

            LinearGradient(
                colors: [
                    .black.opacity(0.08),
                    .black.opacity(0.28),
                    .black.opacity(0.84)
                ],
                startPoint: .top,
                endPoint: .bottom
            )

            VStack(alignment: .leading, spacing: layout.isTightPhone ? 3 : 4) {
                HStack(spacing: 4) {
                    Text(gwentBattleCardBadgeText(card: meta, strength: meta?.strength, row: row))
                        .font(.system(size: featured ? 10 : (layout.isCompact ? 11 : 14), weight: .black, design: .rounded))
                        .foregroundStyle(.black)
                        .frame(width: featured ? 21 : (layout.isCompact ? 22 : 26), height: featured ? 21 : (layout.isCompact ? 22 : 26))
                        .background(
                            Circle()
                                .fill(gwentBattleCardBadgeColor(card: meta, row: row))
                                .overlay(Circle().stroke(.orange.opacity(0.82), lineWidth: 1.3))
                        )

                    Spacer(minLength: 0)

                    Image(systemName: gwentRowIcon(row))
                        .font(.system(size: featured ? 8 : (layout.isCompact ? 9 : 11), weight: .black))
                        .foregroundStyle(.white.opacity(0.88))
                        .frame(width: featured ? 17 : (layout.isCompact ? 18 : 21), height: featured ? 17 : (layout.isCompact ? 18 : 21))
                        .background(.black.opacity(0.46))
                        .clipShape(Circle())

                    if let primaryEffect {
                        Image(systemName: gwentEffectIcon(primaryEffect))
                            .font(.system(size: featured ? 8 : (layout.isCompact ? 9 : 11), weight: .black))
                            .foregroundStyle(.white)
                            .frame(width: featured ? 17 : (layout.isCompact ? 18 : 21), height: featured ? 17 : (layout.isCompact ? 18 : 21))
                            .background(gwentEffectColor(primaryEffect).opacity(0.92))
                            .clipShape(Circle())
                    }
                }

                Spacer(minLength: 0)

                Text(gwentCardTitle(cardId))
                    .font(featured ? .system(size: 9, weight: .black) : (layout.isCompact ? .caption2.bold() : .caption.bold()))
                    .foregroundStyle(.white)
                    .lineLimit(2)
                    .minimumScaleFactor(0.62)
                    .frame(maxWidth: .infinity, minHeight: featured ? 18 : (layout.isTightPhone ? 20 : 24))
                    .padding(.horizontal, 4)
                    .background(.black.opacity(0.56))
                    .clipShape(RoundedRectangle(cornerRadius: 4))

                if !layout.isTightPhone && !featured {
                    Text(primaryEffect.map(gwentEffectLabel) ?? handCardPlacementLabel(cardId, row: row))
                        .font(.system(size: 8, weight: .bold))
                        .foregroundStyle(.white.opacity(0.82))
                        .lineLimit(1)
                        .minimumScaleFactor(0.58)
                }
            }
            .padding(layout.handCardPadding)
        }
        .foregroundStyle(enabled ? .white : .white.opacity(0.42))
        .frame(width: cardWidth, height: cardHeight)
        .background(.black.opacity(0.36))
        .overlay(
            RoundedRectangle(cornerRadius: 8)
                .stroke(selected ? .yellow.opacity(0.92) : gwentRowColor(row).opacity(0.36), lineWidth: selected ? 2 : 1)
        )
        .scaleEffect(selected ? 1.05 : 1)
        .clipShape(RoundedRectangle(cornerRadius: 8))
        .shadow(color: selected ? .yellow.opacity(0.28) : .clear, radius: 8, y: 2)
    }

    private func selectedCardControls(cardId: String, match: [String: JSONValue], layout: GwentTableLayout) -> some View {
        let placements = selectedCardPlacements(cardId)
        return ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: layout.isCompact ? 5 : 6) {
                ForEach(placements) { placement in
                    Button {
                        Task {
                            await play(
                                cardId: cardId,
                                on: placement.row,
                                match: match
                            )
                        }
                    } label: {
                        Label(placement.title, systemImage: gwentPlacementIcon(placement))
                            .font(.caption2.bold())
                            .frame(height: layout.isCompact ? 24 : 28)
                    }
                    .buttonStyle(.bordered)
                    .tint(placement.isOpponent ? .orange : .yellow)
                    .disabled(isSubmittingGwentAction)
                }

                Button {
                    withAnimation(.spring(response: 0.22, dampingFraction: 0.9)) {
                        selectedCardId = nil
                    }
                } label: {
                    Image(systemName: "xmark")
                        .font(.caption.bold())
                        .frame(width: layout.isCompact ? 24 : 28, height: layout.isCompact ? 24 : 28)
                }
                .buttonStyle(.bordered)
                .tint(.white.opacity(0.65))
            }
            .frame(height: layout.actionButtonHeight)
        }
    }

    private func boardCardTile(
        _ value: JSONValue,
        playerId: String,
        row boardRow: String,
        rowCards: [JSONValue],
        layout: GwentTableLayout,
        highlighted: Bool = false,
        dimmed: Bool = false
    ) -> some View {
        let cardId = gwentCardId(value)
        let meta = gwentCardMeta(cardId)
        let row = boardRow.isEmpty ? (meta?.row ?? value.objectValue?.string("row", default: "card") ?? "card") : boardRow
        let strength = gwentBoardCardDisplayStrength(value, row: row, playerId: playerId, rowCards: rowCards)
        let effects = gwentBoardCardEffects(value, meta: meta)
        let primaryEffect = effects.first

        return HStack(spacing: layout.isTightPhone ? 5 : 6) {
            Text(gwentBattleCardBadgeText(card: meta, strength: strength, row: row))
                .font(.system(size: layout.isTightPhone ? 13 : (layout.isCompact ? 14 : 16), weight: .black, design: .rounded))
                .foregroundStyle(.black)
                .lineLimit(1)
                .minimumScaleFactor(0.55)
                .frame(width: layout.boardCardBadgeSize, height: layout.boardCardBadgeSize)
                .background(
                    Circle()
                        .fill(gwentBattleCardBadgeColor(card: meta, row: row))
                        .overlay(Circle().stroke(.orange.opacity(0.78), lineWidth: 1.1))
                )

            VStack(alignment: .leading, spacing: 1) {
                Text(gwentCardTitle(cardId))
                    .font(.system(size: layout.boardCardTitleFontSize, weight: .black))
                    .foregroundStyle(.white)
                    .lineLimit(2)
                    .minimumScaleFactor(0.56)
                    .multilineTextAlignment(.leading)
                    .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .leading)
            }
            .frame(maxWidth: .infinity, alignment: .leading)

            if let primaryEffect {
                let info = cardEffectInfo(effect: primaryEffect, cardId: cardId, row: row, playerId: playerId)
                Button {
                    withAnimation(.spring(response: 0.22, dampingFraction: 0.88)) {
                        activeEffectInfo = info
                    }
                } label: {
                    Image(systemName: gwentEffectIcon(primaryEffect))
                        .font(.system(size: layout.isTightPhone ? 7 : 8, weight: .black))
                        .foregroundStyle(info.usesDarkText ? .black : .white)
                        .frame(width: layout.boardCardEffectSize, height: layout.boardCardEffectSize)
                        .background(gwentEffectColor(primaryEffect).opacity(0.92))
                        .clipShape(Circle())
                }
                .buttonStyle(.plain)
                .accessibilityLabel("Эффект карты: \(info.title)")
            }
        }
        .padding(.leading, layout.isTightPhone ? 6 : 7)
        .padding(.trailing, layout.isTightPhone ? 4 : 6)
        .padding(.vertical, layout.isTightPhone ? 2 : 3)
        .foregroundStyle(.white)
        .frame(width: layout.boardCardWidth, height: layout.boardCardHeight, alignment: .leading)
        .background(
            LinearGradient(
                colors: [
                    gwentRowColor(row).opacity(0.30),
                    Color(red: 0.07, green: 0.055, blue: 0.045).opacity(0.96),
                    .black.opacity(0.88)
                ],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
        )
        .overlay(alignment: .leading) {
            Rectangle()
                .fill(gwentRowColor(row).opacity(0.82))
                .frame(width: highlighted ? 4 : 3)
        }
        .overlay(
            RoundedRectangle(cornerRadius: 7)
                .stroke(highlighted ? .yellow.opacity(0.94) : gwentRowColor(row).opacity(0.44), lineWidth: highlighted ? 2 : 1)
        )
        .scaleEffect(highlighted ? 1.05 : 1)
        .opacity(dimmed ? 0.42 : 1)
        .shadow(color: highlighted ? .yellow.opacity(0.34) : .clear, radius: 8, y: 2)
        .clipShape(RoundedRectangle(cornerRadius: 7))
    }

    @ViewBuilder
    private func gwentBattleArtwork(cardId: String, row: String, compact: Bool) -> some View {
        if let assetName = gwentArtworkAssetName(cardId) {
            GeometryReader { proxy in
                Image(assetName)
                    .resizable()
                    .aspectRatio(contentMode: .fill)
                    .frame(width: proxy.size.width, height: proxy.size.height, alignment: .top)
                    .clipped()
            }
        } else {
            ZStack {
                LinearGradient(
                    colors: [
                        gwentRowColor(row).opacity(0.34),
                        Color(red: 0.10, green: 0.075, blue: 0.052),
                        .black.opacity(0.78)
                    ],
                    startPoint: .topLeading,
                    endPoint: .bottomTrailing
                )
                Image(systemName: gwentBattleArtworkIcon(cardId: cardId, row: row))
                    .font(.system(size: compact ? 18 : 26, weight: .semibold))
                    .foregroundStyle(gwentRowColor(row).opacity(0.74))
                    .shadow(color: .black.opacity(0.7), radius: 2, y: 1)
            }
        }
    }

    private func emptyRowLabel(_ row: String, layout: GwentTableLayout) -> some View {
        Text(gwentRowLabel(row))
            .font(.caption2.bold())
            .foregroundStyle(.white.opacity(0.36))
            .frame(width: layout.emptyRowWidth, height: layout.boardCardHeight)
            .overlay(
                RoundedRectangle(cornerRadius: 7)
                    .stroke(gwentRowColor(row).opacity(0.22), style: StrokeStyle(lineWidth: 1, dash: [4, 4]))
            )
    }

    private var mulliganPrepSection: some View {
        let openingHand = openingGwentHand
        let decks = availableGwentDecks
        return VStack(alignment: .leading, spacing: 8) {
            if !decks.isEmpty {
                Picker("Колода", selection: $selectedDeckId) {
                    ForEach(decks) { deck in
                        Text(gwentDeckTitle(deck)).tag(deck.deckId)
                    }
                }
                .pickerStyle(.menu)
                .tint(.yellow)

                if let deck = selectedGwentDeck {
                    HStack(spacing: 8) {
                        VStack(alignment: .leading, spacing: 4) {
                            Text("\(deck.cardIds.count) карт · \(gwentFactionLabel(gwentDeckFaction(deck))) · лидер: \(gwentCardTitle(deck.leaderCardId))")
                                .font(.caption2)
                                .foregroundStyle(.white.opacity(0.58))
                                .lineLimit(1)
                                .minimumScaleFactor(0.72)
                            deckSummaryStrip(deck)
                            Text(gwentFactionAbilityLabel(gwentDeckFaction(deck)))
                                .font(.caption2.bold())
                                .foregroundStyle(.yellow.opacity(0.88))
                                .lineLimit(1)
                                .minimumScaleFactor(0.72)
                        }
                        Spacer(minLength: 8)
                        Button {
                            showingDeckReview = true
                        } label: {
                            Label("Состав", systemImage: "rectangle.stack")
                                .font(.caption.bold())
                        }
                        .buttonStyle(.bordered)
                        .tint(.yellow)

                        Button {
                            Task { await saveSelectedDeck(deck) }
                        } label: {
                            Label(isSavingDeck ? "Сохр..." : "Сохранить", systemImage: "square.and.arrow.down")
                                .font(.caption.bold())
                        }
                        .buttonStyle(.bordered)
                        .tint(.green)
                        .disabled(isSavingDeck || !gwentDeckWarnings(gwentDeckMetrics(deck)).isEmpty)
                    }
                }
            }

            if shouldShowFirstTurnChoice {
                firstTurnChoiceControl
            }

            HStack {
                Text("Замена карт")
                    .font(.caption.bold())
                Spacer()
                Text("\(selectedMulliganCardIds.count)/2")
                    .font(.caption.monospacedDigit().bold())
                    .foregroundStyle(selectedMulliganCardIds.isEmpty ? .white.opacity(0.58) : .yellow)
            }
            if openingHand.isEmpty {
                Text("Колода не найдена")
                    .font(.caption)
                    .foregroundStyle(.white.opacity(0.52))
                    .frame(maxWidth: .infinity, alignment: .leading)
            } else {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 8) {
                        ForEach(openingHand, id: \.self) { cardId in
                            Button {
                                toggleMulligan(cardId)
                            } label: {
                                handCard(
                                    cardId,
                                    selected: selectedMulliganCardIds.contains(cardId),
                                    enabled: true
                                )
                                .frame(width: 96, height: 78)
                            }
                            .buttonStyle(.plain)
                        }
                    }
                }
            }
        }
        .padding(10)
        .frame(maxWidth: 620)
        .background(.black.opacity(0.22))
        .overlay(
            RoundedRectangle(cornerRadius: 8)
                .stroke(.white.opacity(0.12), lineWidth: 1)
        )
        .clipShape(RoundedRectangle(cornerRadius: 8))
    }

    private func deckSummaryStrip(_ deck: GwentDeck) -> some View {
        let metrics = gwentDeckMetrics(deck)
        return HStack(spacing: 6) {
            deckTextChip(gwentFactionLabel(gwentDeckFaction(deck)))
            deckMetricChip("Отряды", metrics.units, ok: metrics.units >= 22)
            deckMetricChip("Особые", metrics.specials, ok: metrics.specials <= 10)
            deckMetricChip("Герои", metrics.heroes, ok: true)
            deckMetricChip("Ряды", metrics.activeRows, ok: metrics.activeRows >= 2)
        }
    }

    private func deckMetricChip(_ title: String, _ value: Int, ok: Bool) -> some View {
        HStack(spacing: 3) {
            Text(title)
            Text("\(value)")
                .font(.caption2.monospacedDigit().bold())
        }
        .font(.caption2.bold())
        .foregroundStyle(ok ? .white.opacity(0.78) : .orange)
        .padding(.horizontal, 6)
        .frame(height: 22)
        .background(ok ? .black.opacity(0.22) : .orange.opacity(0.16))
        .clipShape(RoundedRectangle(cornerRadius: 7))
    }

    private func deckTextChip(_ title: String) -> some View {
        Text(title)
            .font(.caption2.bold())
            .foregroundStyle(.white.opacity(0.78))
            .padding(.horizontal, 6)
            .frame(height: 22)
            .background(.black.opacity(0.22))
            .clipShape(RoundedRectangle(cornerRadius: 7))
    }

    private func factionBadge(_ faction: String) -> some View {
        Text(gwentFactionLabel(faction))
            .font(.caption2.bold())
            .foregroundStyle(.yellow.opacity(0.9))
            .lineLimit(1)
            .minimumScaleFactor(0.68)
            .padding(.horizontal, 7)
            .padding(.vertical, 4)
            .frame(maxWidth: .infinity)
            .background(.yellow.opacity(0.12))
            .clipShape(RoundedRectangle(cornerRadius: 7))
            .accessibilityLabel(gwentFactionAbilityLabel(faction))
    }

    @ViewBuilder
    private var firstTurnChoiceControl: some View {
        let opponent = opponentPlayerId
        if !ownPlayerId.isEmpty, !opponent.isEmpty {
            VStack(alignment: .leading, spacing: 6) {
                Text("Первый ход")
                    .font(.caption.bold())
                    .foregroundStyle(.white.opacity(0.74))
                Picker("Первый ход", selection: Binding(
                    get: { selectedPreferredStartingPlayerId.isEmpty ? ownPlayerId : selectedPreferredStartingPlayerId },
                    set: { selectedPreferredStartingPlayerId = $0 }
                )) {
                    Text("Я").tag(ownPlayerId)
                    Text(gwentPlayerName(opponent)).tag(opponent)
                }
                .pickerStyle(.segmented)
                Text("Бонус Скоя'таэлей: выбери, кто откроет первый раунд.")
                    .font(.caption2)
                    .foregroundStyle(.white.opacity(0.56))
                    .lineLimit(1)
                    .minimumScaleFactor(0.72)
            }
        }
    }

    private func challengeStartPanel(_ challenge: [String: JSONValue]) -> some View {
        let readyPlayers = challengeReadyPlayers(challenge)
        let missingPlayers = challengeMissingPlayers(challenge)
        let ownReady = readyPlayers.contains(ownPlayerId)
        let ownSubmittedDeckId = challenge.object("prep")?.object("deck_ids_by_player")?.string(ownPlayerId) ?? ""
        let ownSubmittedStartingPlayerId = challenge.object("prep")?.object("preferred_starting_player_ids_by_player")?.string(ownPlayerId) ?? ""
        let requestedDeckId = selectedDeckIdForRequest ?? ""
        let requestedStartingPlayerId = preferredStartingPlayerIdForRequest(challenge) ?? ""
        let deckChanged = !requestedDeckId.isEmpty && requestedDeckId != ownSubmittedDeckId
        let startingPlayerChanged = requestedStartingPlayerId != ownSubmittedStartingPlayerId
        let canSubmitReady = activeGwentCanStart && (!ownReady || !selectedMulliganCardIds.isEmpty || deckChanged || startingPlayerChanged)

        return VStack(spacing: 14) {
            Image(systemName: "flag.checkered.2.crossed")
                .font(.system(size: 44, weight: .bold))
                .foregroundStyle(.yellow)

            Text("\(gwentPlayerName(challenge.string("challenger_id"))) против \(gwentPlayerName(challenge.string("target_id")))")
                .font(.title3.bold())
                .foregroundStyle(.white)
                .lineLimit(1)

            Text(gwentStatusLabel(challenge.string("status", default: "queued")))
                .font(.subheadline)
                .foregroundStyle(.white.opacity(0.66))

            if let stake = stake(from: challenge) {
                stakeBanner(stake, prefix: "На кону")
                    .frame(maxWidth: 420)
            }

            VStack(spacing: 8) {
                readinessRow(
                    playerId: challenge.string("challenger_id"),
                    isReady: readyPlayers.contains(challenge.string("challenger_id"))
                )
                readinessRow(
                    playerId: challenge.string("target_id"),
                    isReady: readyPlayers.contains(challenge.string("target_id"))
                )
                if !missingPlayers.isEmpty {
                    Text("Ждем: \(missingPlayers.map(gwentPlayerName).joined(separator: ", "))")
                        .font(.caption)
                        .foregroundStyle(.white.opacity(0.58))
                }
            }
            .frame(maxWidth: 420)

            mulliganPrepSection

            HStack(spacing: 12) {
                Button {
                    Task {
                        await model.prepareGwentChallenge(
                            id: challenge.string("challenge_id"),
                            mulligans: Array(selectedMulliganCardIds),
                            deckId: selectedDeckIdForRequest,
                            preferredStartingPlayerId: preferredStartingPlayerIdForRequest(challenge)
                        )
                        selectedMulliganCardIds.removeAll()
                    }
                } label: {
                    Label(
                        ownReady && selectedMulliganCardIds.isEmpty ? "Готовность отправлена" : (ownReady ? "Обновить готовность" : "Готов"),
                        systemImage: "checkmark.seal.fill"
                    )
                        .frame(width: 180, height: 42)
                }
                .buttonStyle(.borderedProminent)
                .disabled(!canSubmitReady)

                Button {
                    Task {
                        await model.refusePvpChallenge(
                            id: challenge.string("challenge_id"),
                            reason: refusalReason
                        )
                    }
                } label: {
                    Label("Отказ", systemImage: "xmark.circle")
                        .frame(width: 120, height: 42)
                }
                .buttonStyle(.bordered)
                .disabled(!activeGwentCanStart)
            }
        }
        .padding(22)
        .background(.black.opacity(0.28))
        .clipShape(RoundedRectangle(cornerRadius: 8))
    }

    private func readinessRow(playerId: String, isReady: Bool) -> some View {
        HStack(spacing: 8) {
            Image(systemName: isReady ? "checkmark.circle.fill" : "circle.dashed")
                .foregroundStyle(isReady ? .green : .white.opacity(0.42))
            Text(gwentPlayerName(playerId))
                .font(.caption.bold())
                .foregroundStyle(.white)
            Spacer()
            Text(isReady ? "готов" : "готовится")
                .font(.caption2.bold())
                .foregroundStyle(isReady ? .green : .white.opacity(0.58))
        }
        .padding(.horizontal, 10)
        .frame(height: 34)
        .background(.black.opacity(0.22))
        .clipShape(RoundedRectangle(cornerRadius: 8))
    }

    private func matchResolutionPanel(_ match: [String: JSONValue]) -> some View {
        let status = match.string("status", default: "active")
        let winnerId = match.string("winner_id")
        let isWinner = winnerId == ownPlayerId
        let roundLosses = match.object("round_losses") ?? [:]
        let ownRoundWins = roundLosses.int(opponentPlayerId)
        let opponentRoundWins = roundLosses.int(ownPlayerId)

        return VStack(spacing: 14) {
            Image(systemName: isWinner ? "crown.fill" : "flag.checkered")
                .font(.system(size: 48, weight: .bold))
                .foregroundStyle(isWinner ? .yellow : .orange)

            Text(status == "finished" ? "Матч завершен" : "Партия сыграна")
                .font(.title2.bold())
                .foregroundStyle(.white)

            Text(matchWinnerSummary(winnerId))
                .font(.subheadline.bold())
                .foregroundStyle(isWinner ? .green : .white.opacity(0.72))

            if let stake = stake(from: match) ?? gwentStateRoot?.object("stake_transfer") ?? activeStake {
                stakeBanner(stake, prefix: stakeResultPrefix(stake, status: status))
                    .frame(maxWidth: 380)
            }

            HStack(spacing: 10) {
                resolutionMetric("Ваши раунды", "\(ownRoundWins)")
                resolutionMetric("Раунды соперника", "\(opponentRoundWins)")
            }

            if status == "awaiting_finish", !winnerId.isEmpty {
                Button {
                    Task { await finish(match: match, winnerId: winnerId) }
                } label: {
                    Label(isWinner ? "Забрать победу" : "Подтвердить результат", systemImage: "checkmark.seal.fill")
                        .frame(width: 220, height: 44)
                }
                .buttonStyle(.borderedProminent)
                .tint(isWinner ? .green : .orange)
            }

            HStack(spacing: 10) {
                if status == "finished" {
                    Button {
                        Task { await model.startGwentBotMatch() }
                    } label: {
                        Label("Новая тренировка", systemImage: "play.fill")
                            .frame(width: 190, height: 40)
                    }
                    .buttonStyle(.borderedProminent)
                    .tint(.orange)
                }

                Button {
                    Task { await model.refreshPvpState() }
                } label: {
                    Label("Обновить", systemImage: "arrow.clockwise")
                        .frame(width: 150, height: 40)
                }
                .buttonStyle(.bordered)
            }
        }
        .padding(24)
        .background(.black.opacity(0.32))
        .overlay(
            RoundedRectangle(cornerRadius: 8)
                .stroke((isWinner ? Color.yellow : Color.orange).opacity(0.42), lineWidth: 1)
        )
        .clipShape(RoundedRectangle(cornerRadius: 8))
    }

    private func matchWinnerSummary(_ winnerId: String) -> String {
        if winnerId.isEmpty {
            return "Нужна проверка результата"
        }
        if winnerId == ownPlayerId {
            return "Вы победили"
        }
        return "\(gwentPlayerName(winnerId)) победил"
    }

    private func resolutionMetric(_ title: String, _ value: String) -> some View {
        VStack(spacing: 4) {
            Text(value)
                .font(.title3.bold())
            Text(title)
                .font(.caption)
                .foregroundStyle(.white.opacity(0.58))
        }
        .foregroundStyle(.white)
        .frame(width: 150, height: 58)
        .background(.black.opacity(0.22))
        .clipShape(RoundedRectangle(cornerRadius: 8))
    }

    private var emptyTablePanel: some View {
        VStack(spacing: 12) {
            Image(systemName: "suit.club")
                .font(.system(size: 46, weight: .bold))
                .foregroundStyle(.yellow)
            Text("Нет активной партии")
                .font(.title3.bold())
            Text("Обнови столы в Wi-Fi зоне или создай вызов на экране Гвинта.")
                .font(.subheadline)
                .foregroundStyle(.white.opacity(0.66))
                .multilineTextAlignment(.center)
            mulliganPrepSection
            Button {
                Task { await model.refreshPvpTables() }
            } label: {
                Label("Обновить", systemImage: "arrow.clockwise")
                    .frame(width: 160, height: 40)
            }
            .buttonStyle(.borderedProminent)

            Button {
                Task {
                    await model.startGwentBotMatch(
                        mulligans: Array(selectedMulliganCardIds),
                        deckId: selectedDeckIdForRequest
                    )
                    selectedMulliganCardIds.removeAll()
                }
            } label: {
                Label("Против компьютера", systemImage: "cpu")
                    .frame(width: 190, height: 40)
            }
            .buttonStyle(.bordered)
            .tint(.yellow)
        }
        .foregroundStyle(.white)
        .padding(22)
        .background(.black.opacity(0.28))
        .clipShape(RoundedRectangle(cornerRadius: 8))
    }

    private var portraitRotationPrompt: some View {
        VStack(spacing: 16) {
            HStack {
                Spacer()
                Button {
                    dismiss()
                } label: {
                    Image(systemName: "xmark")
                        .font(.headline.bold())
                        .frame(width: 40, height: 36)
                }
                .buttonStyle(.plain)
                .background(.black.opacity(0.28))
                .clipShape(RoundedRectangle(cornerRadius: 8))
            }
            .padding(.horizontal, 18)
            .padding(.top, 18)

            Spacer()

            Image(systemName: "iphone.landscape")
                .font(.system(size: 62, weight: .bold))
                .foregroundStyle(.yellow)

            Text("Поверни iPhone")
                .font(.title.bold())
                .foregroundStyle(.white)

            Text("Стол Гвинта откроется в горизонтальном режиме: рука снизу, ряды в центре, счет по краям.")
                .font(.subheadline)
                .foregroundStyle(.white.opacity(0.68))
                .multilineTextAlignment(.center)
                .padding(.horizontal, 34)

            Button {
                Task { await model.refreshPvpState() }
            } label: {
                Label("Обновить стол", systemImage: "arrow.clockwise")
                    .frame(width: 190, height: 42)
            }
            .buttonStyle(.bordered)
            .tint(.yellow)

            Spacer()
        }
    }

    private var pileInspectionSheet: some View {
        let playerId = inspectedPilePlayerId ?? ownPlayerId
        let cards = deckState(playerId: playerId).arrayStrings("graveyard")

        return NavigationStack {
            ScrollView {
                LazyVGrid(columns: [GridItem(.adaptive(minimum: 132), spacing: 10)], spacing: 10) {
                    if cards.isEmpty {
                        Text("Сброс пуст")
                            .font(.subheadline.bold())
                            .foregroundStyle(.secondary)
                            .frame(maxWidth: .infinity, minHeight: 120)
                    } else {
                        ForEach(cards, id: \.self) { cardId in
                            handCard(cardId, selected: false, enabled: false)
                                .frame(width: 132, height: 96)
                        }
                    }
                }
                .padding(16)
            }
            .background(Color(red: 0.08, green: 0.07, blue: 0.05))
            .navigationTitle(inspectedPileTitle)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Готово") {
                        inspectedPilePlayerId = nil
                    }
                }
            }
        }
        .preferredColorScheme(.dark)
    }

    private var deckReviewSheet: some View {
        let deck = selectedGwentDeck
        let metrics = deck.map(gwentDeckMetrics)

        return NavigationStack {
            List {
                if let deck, let metrics {
                    Section("Колода") {
                        LabeledContent("Название", value: gwentDeckTitle(deck))
                        LabeledContent("Фракция", value: gwentFactionLabel(gwentDeckFaction(deck)))
                        LabeledContent("Бонус", value: gwentFactionAbilityLabel(gwentDeckFaction(deck)))
                        LabeledContent("Лидер", value: gwentCardTitle(deck.leaderCardId))
                        LabeledContent("Карт", value: "\(deck.cardIds.count)")
                        LabeledContent("Отряды / особые", value: "\(metrics.units) / \(metrics.specials)")
                        LabeledContent("Герои", value: "\(metrics.heroes)")
                    }

                    let warnings = gwentDeckWarnings(metrics)
                    if !warnings.isEmpty {
                        Section("Проверка") {
                            ForEach(warnings, id: \.self) { warning in
                                Label(warning, systemImage: "exclamationmark.triangle.fill")
                                    .foregroundStyle(.orange)
                            }
                        }
                    }

                    Section("Ряды") {
                        ForEach(["melee", "ranged", "siege"], id: \.self) { row in
                            LabeledContent(gwentRowLabel(row), value: "\(metrics.rows[row, default: 0])")
                        }
                    }

                    Section("Карты") {
                        ForEach(deck.cardIds, id: \.self) { cardId in
                            deckReviewRow(cardId)
                        }
                    }
                } else {
                    Section {
                        Text("Колода не найдена")
                            .foregroundStyle(.secondary)
                    }
                }
            }
            .navigationTitle("Состав колоды")
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    if let deck, let metrics {
                        Button {
                            Task { await saveSelectedDeck(deck) }
                        } label: {
                            Label("Сохранить", systemImage: "square.and.arrow.down")
                        }
                        .disabled(isSavingDeck || !gwentDeckWarnings(metrics).isEmpty)
                    }
                }
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Готово") {
                        showingDeckReview = false
                    }
                }
            }
        }
        .preferredColorScheme(.dark)
    }

    private func deckReviewRow(_ cardId: String) -> some View {
        let meta = gwentCardMeta(cardId)
        return HStack(spacing: 12) {
            Image(systemName: gwentRowIcon(meta?.row ?? "special"))
                .foregroundStyle(gwentRowColor(meta?.row ?? "special"))
                .frame(width: 26)
            VStack(alignment: .leading, spacing: 2) {
                Text(gwentCardTitle(cardId))
                    .font(.subheadline.bold())
                Text(deckCardDetail(cardId))
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            Spacer()
            Text(meta.map { "\($0.strength)" } ?? "-")
                .font(.headline.monospacedDigit().bold())
                .foregroundStyle(gwentRowColor(meta?.row ?? "special"))
        }
    }

    private func targetSelectionSheet(_ selection: GwentTargetSelection) -> some View {
        NavigationStack {
            List {
                Section {
                    ForEach(Array(selection.targets.enumerated()), id: \.offset) { _, target in
                        Button {
                            Task { await submitTargetedPlay(selection, target: target) }
                        } label: {
                            HStack(spacing: 12) {
                                Image(systemName: gwentRowIcon(target.string("row", default: "melee")))
                                    .foregroundStyle(gwentRowColor(target.string("row", default: "melee")))
                                    .frame(width: 28)
                                VStack(alignment: .leading, spacing: 3) {
                                    Text(gwentCardTitle(target.string("card_id")))
                                        .font(.subheadline.bold())
                                    Text("\(gwentRowLabel(target.string("row", default: "melee"))) · сила \(target.int("strength"))")
                                        .font(.caption)
                                        .foregroundStyle(.secondary)
                                }
                            }
                        }
                        .disabled(isSubmittingGwentAction)
                    }
                } header: {
                    Text(selection.title)
                }
            }
            .navigationTitle(gwentCardTitle(selection.cardId))
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Отмена") {
                        pendingTargetSelection = nil
                    }
                }
            }
        }
        .preferredColorScheme(.dark)
    }

    private func leaderDiscardSelectionSheet(_ selection: GwentLeaderDiscardSelection) -> some View {
        NavigationStack {
            List {
                Section {
                    ForEach(selection.hand, id: \.self) { cardId in
                        Button {
                            if selectedLeaderDiscardIds.contains(cardId) {
                                selectedLeaderDiscardIds.remove(cardId)
                            } else if selectedLeaderDiscardIds.count < 2 {
                                selectedLeaderDiscardIds.insert(cardId)
                            }
                        } label: {
                            HStack(spacing: 12) {
                                Image(systemName: selectedLeaderDiscardIds.contains(cardId) ? "checkmark.circle.fill" : "circle")
                                    .foregroundStyle(selectedLeaderDiscardIds.contains(cardId) ? .yellow : .secondary)
                                    .frame(width: 28)
                                VStack(alignment: .leading, spacing: 3) {
                                    Text(gwentCardTitle(cardId))
                                        .font(.subheadline.bold())
                                    Text(deckCardDetail(cardId))
                                        .font(.caption)
                                        .foregroundStyle(.secondary)
                                }
                            }
                        }
                        .disabled(isSubmittingGwentAction)
                    }
                } header: {
                    Text("Выбери 2 карты для сброса")
                }
            }
            .navigationTitle(gwentCardTitle(selection.cardId))
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button("Отмена") {
                        selectedLeaderDiscardIds.removeAll()
                        pendingLeaderDiscardSelection = nil
                    }
                }
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Сыграть") {
                        Task { await submitLeaderDiscardPlay(selection) }
                    }
                    .disabled(selectedLeaderDiscardIds.count != 2 || isSubmittingGwentAction)
                }
            }
        }
        .preferredColorScheme(.dark)
    }

    private var gwentTableBackground: some View {
        ZStack {
            LinearGradient(
                colors: [
                    Color(red: 0.10, green: 0.08, blue: 0.05),
                    Color(red: 0.19, green: 0.12, blue: 0.06),
                    Color(red: 0.04, green: 0.11, blue: 0.10)
                ],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )

            Rectangle()
                .fill(.black.opacity(0.18))

            VStack(spacing: 0) {
                Color.black.opacity(0.18)
                Color.clear
                Color.black.opacity(0.18)
            }
        }
    }
}

private extension GwentTableView {
    var compactLandscapeTable: Bool {
        verticalSizeClass == .compact || model.screenshotMode
    }

    var fallbackTableLayout: GwentTableLayout {
        let bounds = UIScreen.main.bounds
        let landscapeViewport = CGSize(
            width: max(bounds.width, bounds.height),
            height: min(bounds.width, bounds.height)
        )
        return GwentTableLayout(
            viewport: landscapeViewport,
            safeAreaInsets: EdgeInsets(),
            compactHeight: compactLandscapeTable,
            selectionMode: activeGwentShouldShowHandMode && handExpanded
        )
    }

    var gwentStateRoot: [String: JSONValue]? {
        if let root = model.pvpPlayerState?.objectValue {
            return root
        }
        return model.lastPvpActionResult?.objectValue
    }

    var activeChallenge: [String: JSONValue]? {
        guard let root = gwentStateRoot else { return nil }
        if let activeChallenge = root.object("active_challenge") {
            return activeChallenge
        }
        if let challenge = root.object("challenge") {
            return challenge
        }
        return root["challenge_id"] == nil ? nil : root
    }

    func challengeReadyPlayers(_ challenge: [String: JSONValue]) -> [String] {
        challenge.object("prep")?.arrayStrings("ready_players") ?? []
    }

    func challengeMissingPlayers(_ challenge: [String: JSONValue]) -> [String] {
        if let missing = challenge.object("prep")?.arrayStrings("missing_players"), !missing.isEmpty {
            return missing
        }
        let ready = Set(challengeReadyPlayers(challenge))
        return [challenge.string("challenger_id"), challenge.string("target_id")]
            .filter { !$0.isEmpty && !ready.contains($0) }
    }

    var activeMatch: [String: JSONValue]? {
        guard let root = gwentStateRoot else { return nil }
        if let activeMatch = root.object("active_match") {
            return activeMatch
        }
        if let recentMatch = root.object("recent_match") {
            return recentMatch
        }
        if let match = root.object("match") {
            return match
        }
        return root["match_id"] == nil ? nil : root
    }

    var activeStake: [String: JSONValue]? {
        if let match = activeMatch, let stake = stake(from: match) {
            return stake
        }
        if let challenge = activeChallenge, let stake = stake(from: challenge) {
            return stake
        }
        if let root = gwentStateRoot {
            return root.object("stake_transfer") ?? root.object("stake")
        }
        return nil
    }

    var activeRound: [String: JSONValue]? {
        guard let root = gwentStateRoot else { return nil }
        return root.object("current_round") ?? root.object("round")
    }

    var roundState: [String: JSONValue]? {
        if let activeRound {
            return activeRound.object("round_state") ?? activeRound
        }
        return gwentStateRoot?.object("round_state")
    }

    var roundStatus: String {
        roundState?.string("status", default: "pending_player_submissions") ?? "pending_player_submissions"
    }

    var ownPlayerId: String {
        model.player?.playerId ?? ""
    }

    var opponentPlayerId: String {
        let ids = playerIds
        if let opponent = ids.first(where: { $0 != ownPlayerId }) {
            return opponent
        }
        if let challenge = activeChallenge {
            let challenger = challenge.string("challenger_id")
            let target = challenge.string("target_id")
            return challenger == ownPlayerId ? target : challenger
        }
        return ""
    }

    var playerIds: [String] {
        if let board = roundState?.object("board") {
            let ids = board.keys.filter { $0.hasPrefix("p_") }.sorted()
            if !ids.isEmpty {
                return ids
            }
        }
        if let deckState = activeMatch?.object("deck_state") {
            return deckState.keys.filter { $0.hasPrefix("p_") }.sorted()
        }
        return ownPlayerId.isEmpty ? [] : [ownPlayerId]
    }

    var activeGwentHand: [String] {
        if let root = gwentStateRoot {
            let endpointHand = root.arrayStrings("player_hand")
            if !endpointHand.isEmpty {
                return endpointHand
            }
        }
        return deckState(playerId: ownPlayerId).arrayStrings("hand")
    }

    var openingGwentHand: [String] {
        guard let deck = selectedGwentDeck ?? availableGwentDecks.first else { return [] }
        return Array(deck.cardIds.prefix(10))
    }

    var availableGwentDecks: [GwentDeck] {
        guard let player = model.player else { return [] }
        var decksById: [String: GwentDeck] = [:]
        for deck in model.snapshot?.gwentDecks ?? [] where deck.playerId == player.playerId {
            decksById[deck.deckId] = deck
        }
        for deck in model.runtimeGwentDecks where deck.playerId == player.playerId {
            decksById[deck.deckId] = deck
        }
        return decksById.values.sorted { $0.deckId < $1.deckId }
    }

    var selectedGwentDeck: GwentDeck? {
        let decks = availableGwentDecks
        guard !decks.isEmpty else { return nil }
        if let deck = decks.first(where: { $0.deckId == selectedDeckId }) {
            return deck
        }
        return decks.first
    }

    var selectedDeckIdForRequest: String? {
        let deckId = (selectedGwentDeck?.deckId ?? selectedDeckId)
            .trimmingCharacters(in: .whitespacesAndNewlines)
        return deckId.isEmpty ? nil : deckId
    }

    var shouldShowFirstTurnChoice: Bool {
        guard activeChallenge != nil, let selectedGwentDeck else { return false }
        return gwentDeckFaction(selectedGwentDeck).lowercased() == "scoiatael"
    }

    func preferredStartingPlayerIdForRequest(_ challenge: [String: JSONValue]) -> String? {
        guard let selectedGwentDeck,
              gwentDeckFaction(selectedGwentDeck).lowercased() == "scoiatael"
        else { return nil }
        let candidates = [
            challenge.string("challenger_id"),
            challenge.string("target_id"),
        ].filter { !$0.isEmpty }
        let selected = selectedPreferredStartingPlayerId.trimmingCharacters(in: .whitespacesAndNewlines)
        if candidates.contains(selected) {
            return selected
        }
        return ownPlayerId.isEmpty ? candidates.first : ownPlayerId
    }

    func normalizeSelectedDeck() {
        let decks = availableGwentDecks
        guard !decks.isEmpty else {
            selectedDeckId = ""
            selectedMulliganCardIds.removeAll()
            return
        }
        if !decks.contains(where: { $0.deckId == selectedDeckId }) {
            selectedDeckId = decks[0].deckId
            selectedMulliganCardIds.removeAll()
        }
        normalizePreferredStartingPlayer()
    }

    func applyTableScreenshotArgumentsIfNeeded() {
        #if DEBUG
        guard !appliedTableScreenshotArguments else { return }
        appliedTableScreenshotArguments = true
        let arguments = ProcessInfo.processInfo.arguments
        guard let cardIndex = arguments.firstIndex(of: "--gwent-selected-card") else { return }
        let valueIndex = arguments.index(after: cardIndex)
        guard arguments.indices.contains(valueIndex) else { return }
        let cardId = arguments[valueIndex].trimmingCharacters(in: .whitespacesAndNewlines)
        guard !cardId.isEmpty else { return }
        selectedCardId = cardId
        handExpanded = true
        #endif
    }

    func normalizePreferredStartingPlayer() {
        guard let selectedGwentDeck,
              gwentDeckFaction(selectedGwentDeck).lowercased() == "scoiatael"
        else {
            selectedPreferredStartingPlayerId = ""
            return
        }
        let candidates = [ownPlayerId, opponentPlayerId].filter { !$0.isEmpty }
        if !candidates.contains(selectedPreferredStartingPlayerId) {
            selectedPreferredStartingPlayerId = ownPlayerId.isEmpty ? (candidates.first ?? "") : ownPlayerId
        }
    }

    func saveSelectedDeck(_ deck: GwentDeck) async {
        guard !isSavingDeck else { return }
        isSavingDeck = true
        defer { isSavingDeck = false }
        if let savedDeck = await model.saveGwentDeck(deck) {
            selectedDeckId = savedDeck.deckId
        }
    }

    var activeGwentRoundNumber: Int {
        if let legal = gwentStateRoot?.object("legal_actions"), legal.int("round_number") > 0 {
            return legal.int("round_number")
        }
        if let activeRound, activeRound.int("round_number") > 0 {
            return activeRound.int("round_number")
        }
        return 1
    }

    var isSubmittingGwentAction: Bool {
        pendingGwentActionId != nil
    }

    var activeGwentTurnPlayerId: String {
        if let legalActions {
            return legalActions.string("turn_player_id")
        }
        return roundState?.string("turn_player_id") ?? ""
    }

    var activeGwentTurnKey: String {
        [
            activeMatch?.string("match_id") ?? "",
            "r\(activeGwentRoundNumber)",
            roundState?.string("phase") ?? "",
            activeGwentTurnPlayerId,
            roundState?.string("updated_at") ?? roundState?.string("created_at") ?? ""
        ].joined(separator: "|")
    }

    var activeGwentTurnIsActive: Bool {
        guard activeMatch?.string("status", default: "active") == "active" else { return false }
        guard roundState?.string("phase") == "active_turn" else { return false }
        return !activeGwentTurnPlayerId.isEmpty
    }

    var activeGwentIsPlayerTurn: Bool {
        guard let legalActions else {
            let turnPlayerId = activeGwentTurnPlayerId
            return !turnPlayerId.isEmpty && turnPlayerId == ownPlayerId
        }
        return jsonBool(legalActions, key: "is_player_turn")
    }

    var activeGwentShouldShowHandMode: Bool {
        (activeGwentIsPlayerTurn && (activeGwentCanPlay || activeGwentCanPass || activeGwentCanUseLeader))
            || (model.screenshotMode && selectedCardId != nil)
    }

    var serverTurnStartedAt: Date? {
        for key in ["turn_started_at", "updated_at", "created_at"] {
            let value = roundState?.string(key).trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
            if let date = parseGwentDate(value) {
                return date
            }
        }
        return nil
    }

    var activeTurnDeadline: Date? {
        guard activeGwentTurnIsActive else { return nil }
        let startedAt = serverTurnStartedAt ?? localTurnStartedAt
        return startedAt?.addingTimeInterval(TimeInterval(turnLimitSeconds))
    }

    var activeTurnCountdownSeconds: Int? {
        guard let deadline = activeTurnDeadline else { return nil }
        let remaining = Int(ceil(deadline.timeIntervalSince(countdownNow)))
        return min(turnLimitSeconds, max(0, remaining))
    }

    var turnCountdownPrefix: String {
        activeGwentIsPlayerTurn ? "Ваш ход" : "Ход соперника"
    }

    var activeGwentCanPlay: Bool {
        guard !isSubmittingGwentAction else { return false }
        guard let root = gwentStateRoot else { return false }
        if let legal = root.object("legal_actions") {
            return jsonBool(legal, key: "can_play_card")
        }
        guard let match = activeMatch,
              match.string("status", default: "active") != "finished",
              !ownPlayerId.isEmpty
        else { return false }
        return !(roundState?.arrayStrings("ready_players").contains(ownPlayerId) ?? false)
    }

    var activeGwentCanPass: Bool {
        guard !isSubmittingGwentAction else { return false }
        guard let legalActions else { return activeGwentCanPlay }
        return jsonBool(legalActions, key: "can_pass")
    }

    var legalActions: [String: JSONValue]? {
        gwentStateRoot?.object("legal_actions")
    }

    var activeGwentCanUseLeader: Bool {
        guard !isSubmittingGwentAction else { return false }
        guard let legalActions else { return false }
        return jsonBool(legalActions, key: "can_use_leader")
    }

    var activeGwentTurnText: String {
        if isSubmittingGwentAction {
            return "Отправляю ход на сервер..."
        }
        guard let legalActions else { return "Ожидание состояния стола" }
        if jsonBool(legalActions, key: "is_player_turn") {
            return "Ваш ход: сыграйте карту на ряд или пасуйте"
        }
        let turnPlayer = legalActions.string("turn_player_id")
        if !turnPlayer.isEmpty {
            return "Ходит \(gwentPlayerName(turnPlayer))"
        }
        return gwentStatusLabel(roundStatus)
    }

    var activeGwentCanStart: Bool {
        guard let root = gwentStateRoot else { return false }
        if let legal = root.object("legal_actions") {
            return jsonBool(legal, key: "can_start")
        }
        guard let challenge = activeChallenge else { return false }
        return ["assigned", "queued", "deferred"].contains(challenge.string("status"))
    }

    var tableTitle: String {
        if activeMatch != nil {
            return "Гвинт: \(gwentPlayerName(ownPlayerId)) vs \(gwentPlayerName(opponentPlayerId))"
        }
        if activeChallenge != nil {
            return "Вызов на Гвинт"
        }
        return "Стол Гвинта"
    }

    var tableSubtitle: String {
        if let match = activeMatch {
            return gwentStatusLabel(match.string("status", default: "active"))
        }
        if let challenge = activeChallenge {
            return gwentStatusLabel(challenge.string("status", default: "queued"))
        }
        return "Wi-Fi sync, ставки и мастерская проверка остаются на сервере"
    }

    func activeGwentPlayerSubmitted(_ root: [String: JSONValue]) -> Bool {
        if let round = activeRound, jsonBool(round, key: "player_submitted") {
            return true
        }
        guard !ownPlayerId.isEmpty else { return false }
        return roundState?.arrayStrings("ready_players").contains(ownPlayerId) ?? false
    }

    func syncHandModeForTurn(animated: Bool = true) {
        let updates = {
            if activeGwentShouldShowHandMode {
                handExpanded = true
                syncBoardFocusForSelectedCard()
            } else {
                handExpanded = false
                selectedCardId = nil
                boardFocusSide = .own
                pendingLeaderActivation = nil
            }
        }
        if animated {
            withAnimation(.spring(response: 0.26, dampingFraction: 0.86)) {
                updates()
            }
        } else {
            updates()
        }
    }

    func syncTurnTimerForCurrentState(now: Date = Date()) {
        let key = activeGwentTurnKey
        countdownNow = now
        guard observedTurnKey != key else { return }
        observedTurnKey = key
        autoPassTurnKey = nil
        localTurnStartedAt = activeGwentTurnIsActive ? (serverTurnStartedAt ?? now) : nil
    }

    func handleTurnTimerTick(_ now: Date) {
        syncTurnTimerForCurrentState(now: now)
        maybeAutoPassTimedOutTurn()
    }

    func maybeAutoPassTimedOutTurn() {
        guard !model.screenshotMode,
              activeGwentIsPlayerTurn,
              activeGwentCanPass,
              let remaining = activeTurnCountdownSeconds,
              remaining == 0,
              let match = activeMatch
        else { return }
        let turnKey = activeGwentTurnKey
        guard autoPassTurnKey != turnKey else { return }
        autoPassTurnKey = turnKey
        Task { await autoPassTimedOutTurn(match: match, turnKey: turnKey) }
    }

    @MainActor
    func autoPassTimedOutTurn(match: [String: JSONValue], turnKey: String) async {
        guard turnKey == activeGwentTurnKey, activeGwentIsPlayerTurn, activeGwentCanPass else { return }
        model.infoMessage = "Время хода истекло: пас."
        await pass(match: match)
    }

    func syncBoardFocusForSelectedCard() {
        guard let selectedCardId else {
            boardFocusSide = .own
            return
        }
        boardFocusSide = boardFocusSide(for: selectedCardId)
    }

    func boardFocusSide(for cardId: String) -> GwentBoardFocusSide {
        cardTargetsOpponentSide(cardId) ? .opponent : .own
    }

    func deckState(playerId: String) -> [String: JSONValue] {
        activeMatch?.object("deck_state")?.object(playerId) ?? [:]
    }

    func gwentFactionForPlayer(_ playerId: String) -> String {
        let state = deckState(playerId: playerId)
        let stateFaction = state.string("faction").trimmingCharacters(in: .whitespacesAndNewlines)
        if !stateFaction.isEmpty {
            return stateFaction
        }
        let deckId = state.string("deck_id").trimmingCharacters(in: .whitespacesAndNewlines)
        if !deckId.isEmpty,
           let deck = model.snapshot?.gwentDecks.first(where: { $0.deckId == deckId }) {
            return gwentDeckFaction(deck)
        }
        if playerId == ownPlayerId, let selectedGwentDeck {
            return gwentDeckFaction(selectedGwentDeck)
        }
        if let deck = model.snapshot?.gwentDecks.first(where: { $0.playerId == playerId }) {
            return gwentDeckFaction(deck)
        }
        return ""
    }

    func board(playerId: String) -> [String: JSONValue] {
        roundState?.object("board")?.object(playerId) ?? [:]
    }

    func boardCards(playerId: String, row: String) -> [JSONValue] {
        board(playerId: playerId).array(row)
    }

    func playerTotal(playerId: String) -> Int {
        if let total = roundState?.object("total_scores")?.int(playerId), total > 0 {
            return total
        }
        return ownRows.reduce(0) { partial, row in
            partial + rowScore(playerId: playerId, row: row, cards: boardCards(playerId: playerId, row: row))
        }
    }

    func rowScore(playerId: String, row: String, cards: [JSONValue]) -> Int {
        if let score = roundState?.object("row_scores")?.object(playerId)?.int(row) {
            return score
        }
        return gwentRowTotal(cards)
    }

    func roundLosses(_ playerId: String) -> Int {
        activeMatch?.object("round_losses")?.int(playerId) ?? 0
    }

    func roundWins(_ playerId: String) -> Int {
        let rounds = activeMatch?.array("rounds").compactMap(\.objectValue) ?? []
        let resolvedRounds = rounds.filter { round in
            !round.string("winner_id").isEmpty || jsonBool(round, key: "tie")
        }
        if !resolvedRounds.isEmpty {
            return resolvedRounds.filter { $0.string("winner_id") == playerId }.count
        }
        return playerIds
            .filter { $0 != playerId }
            .reduce(0) { partial, opponentId in
                partial + roundLosses(opponentId)
            }
    }

    func roundHistoryText(_ match: [String: JSONValue]) -> String {
        let rounds = match.array("rounds").compactMap(\.objectValue)
        let resolved = rounds
            .filter { round in
                round["winner_id"] != nil || jsonBool(round, key: "tie")
            }
            .sorted { lhs, rhs in
                lhs.int("round_number") < rhs.int("round_number")
            }
        guard !resolved.isEmpty else { return "" }
        return resolved.prefix(3).map { round in
            let number = round.int("round_number")
            if jsonBool(round, key: "tie") {
                return "R\(number): ничья"
            }
            let winnerId = round.string("winner_id")
            if winnerId == ownPlayerId {
                return "R\(number): Вы"
            }
            if winnerId == opponentPlayerId {
                return "R\(number): соперник"
            }
            return "R\(number): \(gwentPlayerName(winnerId))"
        }
        .joined(separator: " · ")
    }

    func scoreColor(for playerId: String) -> Color {
        if playerId == ownPlayerId {
            return .green
        }
        return .orange
    }

    func playerReadiness(_ playerId: String) -> String {
        if let passed = roundState?.object("passed"), jsonBool(passed, key: playerId) {
            return "Пас"
        }
        if roundState?.string("turn_player_id") == playerId {
            return playerId == ownPlayerId ? "Ваш ход" : "Ходит"
        }
        return "Ожидает"
    }

    func readinessColor(_ playerId: String) -> Color {
        if let passed = roundState?.object("passed"), jsonBool(passed, key: playerId) {
            return .orange
        }
        if roundState?.string("turn_player_id") == playerId {
            return .yellow
        }
        return .white.opacity(0.58)
    }

    func toggleMulligan(_ cardId: String) {
        if selectedMulliganCardIds.contains(cardId) {
            selectedMulliganCardIds.remove(cardId)
            return
        }
        guard selectedMulliganCardIds.count < 2 else {
            model.errorMessage = "Можно заменить не больше двух карт."
            return
        }
        selectedMulliganCardIds.insert(cardId)
    }

    func runGwentPollingLoop() async {
        guard !model.screenshotMode else { return }
        guard !model.playerCode.isEmpty else { return }
        await model.refreshPvpState(silent: true)
        while !Task.isCancelled {
            guard shouldAutoPollGwentTable else { return }
            try? await Task.sleep(nanoseconds: 3_000_000_000)
            guard !Task.isCancelled, !model.playerCode.isEmpty else { return }
            await model.refreshPvpState(silent: true)
        }
    }

    var shouldAutoPollGwentTable: Bool {
        if let match = activeMatch {
            return !isMatchResolutionVisible(match)
        }
        return activeChallenge != nil
    }

    func isMatchResolutionVisible(_ match: [String: JSONValue]) -> Bool {
        ["awaiting_finish", "finished", "needs_master_review"].contains(match.string("status"))
    }

    func finish(match: [String: JSONValue], winnerId: String) async {
        await model.finishGwentMatch(
            matchId: match.string("match_id"),
            winnerId: winnerId
        )
    }

    @MainActor
    func submitGwentAction(
        matchId: String,
        roundNumber: Int,
        action: String,
        cardId: String? = nil,
        row: String? = nil,
        targetCardId: String? = nil,
        discardCardIds: [String]? = nil,
        reviveCardId: String? = nil,
        reviveRow: String? = nil
    ) async {
        guard pendingGwentActionId == nil else { return }
        let actionId = makeGwentActionId(
            matchId: matchId,
            roundNumber: roundNumber,
            action: action
        )
        pendingGwentActionId = actionId
        defer { pendingGwentActionId = nil }

        await model.recordGwentAction(
            matchId: matchId,
            roundNumber: roundNumber,
            action: action,
            cardId: cardId,
            row: row,
            targetCardId: targetCardId,
            discardCardIds: discardCardIds,
            reviveCardId: reviveCardId,
            reviveRow: reviveRow,
            actionId: actionId
        )
    }

    func makeGwentActionId(matchId: String, roundNumber: Int, action: String) -> String {
        let parts = [
            "ios",
            safeActionIdPart(ownPlayerId),
            safeActionIdPart(matchId),
            "r\(roundNumber)",
            safeActionIdPart(action),
            UUID().uuidString.lowercased()
        ]
        return parts.joined(separator: "-")
    }

    func safeActionIdPart(_ value: String) -> String {
        let allowed = "abcdefghijklmnopqrstuvwxyz0123456789-_"
        let compact = value
            .lowercased()
            .map { allowed.contains($0) ? $0 : "-" }
        let result = String(compact)
            .trimmingCharacters(in: CharacterSet(charactersIn: "-_"))
        return result.isEmpty ? "na" : result
    }

    @MainActor
    func play(cardId: String, on row: String?, match: [String: JSONValue]) async {
        guard activeGwentCanPlay else { return }
        let normalizedRow = row?.trimmingCharacters(in: .whitespacesAndNewlines)
        let actionRow = normalizedRow?.isEmpty == true ? nil : normalizedRow
        if actionRow == nil && !legalRows(for: cardId).isEmpty {
            model.errorMessage = "Для \(gwentCardTitle(cardId)) нужен боевой ряд."
            return
        }
        guard actionRow == nil || cardCanPlay(cardId, on: actionRow ?? "") else {
            model.errorMessage = "\(gwentCardTitle(cardId)) нельзя сыграть в ряд «\(gwentRowLabel(actionRow ?? ""))»."
            return
        }
        if let action = playableAction(for: cardId),
           action.string("target_kind") == "own_non_hero_unit",
           action.array("targets").isEmpty {
            model.errorMessage = "Для \(gwentCardTitle(cardId)) нужна своя обычная карта на поле."
            return
        }
        if let selection = targetSelectionIfNeeded(cardId: cardId, row: actionRow, match: match) {
            pendingTargetSelection = selection
            return
        }
        await submitGwentAction(
            matchId: match.string("match_id"),
            roundNumber: activeGwentRoundNumber,
            action: "play_card",
            cardId: cardId,
            row: actionRow,
            targetCardId: defaultTargetCardId(for: cardId),
            reviveCardId: defaultReviveCardId(for: cardId)
        )
        selectedCardId = nil
    }

    @MainActor
    func submitTargetedPlay(_ selection: GwentTargetSelection, target: [String: JSONValue]) async {
        let targetKind = selection.targetKind
        let leaderTargetKinds: Set<String> = ["leader_own_graveyard_unit", "leader_opponent_graveyard_unit"]
        await submitGwentAction(
            matchId: selection.matchId,
            roundNumber: selection.roundNumber,
            action: selection.action,
            cardId: selection.cardId,
            row: selection.row,
            targetCardId: targetKind == "own_non_hero_unit" || leaderTargetKinds.contains(targetKind) ? target.string("card_id") : nil,
            discardCardIds: selection.discardCardIds.isEmpty ? nil : selection.discardCardIds,
            reviveCardId: targetKind == "graveyard_unit" ? target.string("card_id") : nil
        )
        selectedCardId = nil
        pendingTargetSelection = nil
    }

    @MainActor
    func submitLeaderDiscardPlay(_ selection: GwentLeaderDiscardSelection) async {
        let discardIds = Array(selectedLeaderDiscardIds).sorted()
        guard discardIds.count == 2 else { return }
        await submitGwentAction(
            matchId: selection.matchId,
            roundNumber: selection.roundNumber,
            action: "use_leader",
            cardId: selection.cardId,
            targetCardId: selection.drawCardId,
            discardCardIds: discardIds
        )
        selectedCardId = nil
        selectedLeaderDiscardIds.removeAll()
        pendingLeaderDiscardSelection = nil
    }

    @MainActor
    func pass(match: [String: JSONValue]) async {
        await submitGwentAction(
            matchId: match.string("match_id"),
            roundNumber: activeGwentRoundNumber,
            action: "pass"
        )
        selectedCardId = nil
    }

    func showLeaderActivation(match: [String: JSONValue]) {
        guard activeGwentCanUseLeader else { return }
        let leaderCardId = legalActions?.string("leader_card_id") ?? ""
        guard !leaderCardId.isEmpty else { return }
        withAnimation(.spring(response: 0.22, dampingFraction: 0.88)) {
            activeEffectInfo = nil
            pendingLeaderActivation = GwentLeaderActivation(
                match: match,
                leaderCardId: leaderCardId,
                effectInfo: leaderActivationInfo(cardId: leaderCardId)
            )
        }
    }

    func leaderActivationInfo(cardId: String) -> GwentEffectInfo {
        let card = gwentCardMeta(cardId)
        let effect = (card.map(gwentCardEffects)?.first ?? "")
            .trimmingCharacters(in: .whitespacesAndNewlines)
            .lowercased()
        let body = card?.effectText.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        let resolvedBody: String
        if !body.isEmpty {
            resolvedBody = body
        } else if effect.isEmpty {
            resolvedBody = "Активируйте способность лидера как особый эффект матча."
        } else {
            resolvedBody = gwentEffectDescription(effect, row: nil, playerId: ownPlayerId, cardTitle: gwentCardTitle(cardId))
        }
        return GwentEffectInfo(
            id: "leader-activation:\(cardId):\(effect)",
            title: effect.isEmpty ? "Способность лидера" : gwentEffectTitle(effect),
            subtitle: gwentCardTitle(cardId),
            body: resolvedBody,
            icon: effect.isEmpty ? "crown.fill" : gwentEffectIcon(effect),
            badge: "Лидер",
            color: effect.isEmpty ? .yellow : gwentEffectColor(effect),
            usesDarkText: false
        )
    }

    @MainActor
    func useLeader(match: [String: JSONValue]) async {
        pendingLeaderActivation = nil
        let leaderCardId = legalActions?.string("leader_card_id") ?? ""
        guard !leaderCardId.isEmpty else { return }
        let leaderEffect = gwentCardMeta(leaderCardId).map(gwentCardEffects)?.first ?? ""
        switch leaderEffect {
        case "leader_emhyr_graveyard_theft":
            let targets = leaderGraveyardTargets(playerId: opponentPlayerId)
            guard !targets.isEmpty else {
                model.errorMessage = "В сбросе соперника нет обычной карты для лидера."
                return
            }
            pendingTargetSelection = GwentTargetSelection(
                action: "use_leader",
                matchId: match.string("match_id"),
                roundNumber: activeGwentRoundNumber,
                cardId: leaderCardId,
                row: nil,
                targetKind: "leader_opponent_graveyard_unit",
                discardCardIds: [],
                targets: targets
            )
            return
        case "leader_eredin_graveyard_return":
            let targets = leaderGraveyardTargets(playerId: ownPlayerId)
            guard !targets.isEmpty else {
                model.errorMessage = "В вашем сбросе нет обычной карты для лидера."
                return
            }
            pendingTargetSelection = GwentTargetSelection(
                action: "use_leader",
                matchId: match.string("match_id"),
                roundNumber: activeGwentRoundNumber,
                cardId: leaderCardId,
                row: nil,
                targetKind: "leader_own_graveyard_unit",
                discardCardIds: [],
                targets: targets
            )
            return
        case "leader_eredin_discard_draw":
            let hand = activeGwentHand
            let drawPile = deckState(playerId: ownPlayerId).arrayStrings("draw_pile")
            guard hand.count >= 2, let drawCardId = drawPile.first else {
                model.errorMessage = "Для лидера нужны две карты в руке и карта в колоде."
                return
            }
            selectedLeaderDiscardIds = []
            pendingLeaderDiscardSelection = GwentLeaderDiscardSelection(
                matchId: match.string("match_id"),
                roundNumber: activeGwentRoundNumber,
                cardId: leaderCardId,
                hand: hand,
                drawCardId: drawCardId
            )
            return
        default:
            break
        }
        await submitGwentAction(
            matchId: match.string("match_id"),
            roundNumber: activeGwentRoundNumber,
            action: "use_leader",
            cardId: leaderCardId,
            row: "melee"
        )
        selectedCardId = nil
    }

    func handleCardDrop(
        _ providers: [NSItemProvider],
        row: String,
        isOpponent: Bool,
        match: [String: JSONValue]
    ) -> Bool {
        guard activeGwentCanPlay else { return false }
        guard let provider = providers.first(where: { $0.canLoadObject(ofClass: NSString.self) }) else {
            return false
        }
        provider.loadObject(ofClass: NSString.self) { object, _ in
            guard let cardId = object as? String else { return }
            Task { @MainActor in
                guard cardCanUseBoardSide(cardId, isOpponent: isOpponent) else {
                    model.errorMessage = wrongSideMessage(for: cardId)
                    dropTargetRow = nil
                    return
                }
                await play(cardId: cardId, on: row, match: match)
                dropTargetRow = nil
            }
        }
        return true
    }

    func rowDropKey(_ row: String, isOpponent: Bool) -> String {
        "\(isOpponent ? "opponent" : "own"):\(row)"
    }

    func cardCanUseBoardSide(_ cardId: String, isOpponent: Bool) -> Bool {
        cardTargetsOpponentSide(cardId) == isOpponent
    }

    func cardTargetsOpponentSide(_ cardId: String) -> Bool {
        if let action = playableAction(for: cardId) {
            return action.string("effect") == "spy" || action.arrayStrings("effects").contains("spy")
        }
        guard let meta = gwentCardMeta(cardId) else { return false }
        return meta.effect == "spy" || meta.abilityTags.contains("spy")
    }

    func handCardPlacementLabel(_ cardId: String, row: String) -> String {
        cardTargetsOpponentSide(cardId) ? "К сопернику · \(gwentRowLabel(row))" : gwentRowLabel(row)
    }

    func selectedCardPlacements(_ cardId: String) -> [GwentCardPlacement] {
        let isOpponent = cardTargetsOpponentSide(cardId)
        let rows = legalRows(for: cardId)
        if rows.isEmpty {
            return [
                GwentCardPlacement(
                    row: nil,
                    isOpponent: isOpponent,
                    title: isOpponent ? "К сопернику" : "Сыграть"
                )
            ]
        }
        return rows.map { row in
            GwentCardPlacement(
                row: row,
                isOpponent: isOpponent,
                title: isOpponent ? "Им: \(shortRowLabel(row))" : shortRowLabel(row)
            )
        }
    }

    func selectedCardCanPlay(row: String, isOpponent: Bool) -> Bool {
        guard activeGwentCanPlay, let selectedCardId else { return false }
        guard !selectedCardNeedsBoardTarget(selectedCardId) else { return false }
        let rows = legalRows(for: selectedCardId)
        guard !rows.isEmpty else { return false }
        return cardCanUseBoardSide(selectedCardId, isOpponent: isOpponent)
            && rows.contains(row)
    }

    func wrongSideMessage(for cardId: String) -> String {
        cardTargetsOpponentSide(cardId)
            ? "\(gwentCardTitle(cardId)) играется на сторону соперника."
            : "\(gwentCardTitle(cardId)) играется на вашу сторону."
    }

    func gwentPlacementIcon(_ placement: GwentCardPlacement) -> String {
        if let row = placement.row {
            return gwentRowIcon(row)
        }
        return placement.isOpponent ? "arrow.up.right.square" : "sparkles"
    }

    func shortRowLabel(_ row: String) -> String {
        switch row.lowercased() {
        case "melee":
            return "Ближний"
        case "ranged":
            return "Дальний"
        case "siege":
            return "Осада"
        default:
            return gwentRowLabel(row)
        }
    }

    func stake(from object: [String: JSONValue]) -> [String: JSONValue]? {
        object.object("stake") ?? object.object("stake_json")
    }

    func stakeIsPractice(_ stake: [String: JSONValue]) -> Bool {
        stake.string("asset_type").lowercased() == "practice"
    }

    func stakeLabel(_ stake: [String: JSONValue]) -> String {
        let assetType = stake.string("asset_type").lowercased()
        let assetId = stake.string("asset_id")
        let quantity = stake.int("quantity", default: stake.int("amount", default: 1))
        if assetType == "practice" {
            return "Тренировка без ставки"
        }
        if assetType == "gold" {
            return "\(quantity)g"
        }
        let assetName = readableIdentifier(assetId, droppingPrefixes: ["item_", "card_", "artifact_", "rare_"])
        return quantity > 1
            ? "\(assetTypeLabel(assetType)) \(assetName) x\(quantity)"
            : "\(assetTypeLabel(assetType)) \(assetName)"
    }

    func formatTurnCountdown(_ seconds: Int) -> String {
        let clamped = max(0, seconds)
        return "\(clamped / 60):\(String(format: "%02d", clamped % 60))"
    }

    func parseGwentDate(_ value: String) -> Date? {
        let trimmed = value.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return nil }
        let iso = ISO8601DateFormatter()
        iso.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        if let date = iso.date(from: trimmed) {
            return date
        }
        iso.formatOptions = [.withInternetDateTime]
        return iso.date(from: trimmed)
    }

    func stakeStatusLabel(_ stake: [String: JSONValue]) -> String {
        switch stake.string("status").lowercased() {
        case "locked":
            return "escrow"
        case "applied":
            return "выдано"
        case "refunded":
            return "возврат"
        case "not_applied":
            return "review"
        case "", "unknown":
            return stake.string("asset_type").lowercased() == "practice" ? "practice" : "ставка"
        default:
            return readableIdentifier(stake.string("status"))
        }
    }

    func stakeResultPrefix(_ stake: [String: JSONValue], status: String) -> String {
        if stake.string("status").lowercased() == "applied" || status == "finished" {
            return "Итог ставки"
        }
        return "Ставка"
    }

    func assetTypeLabel(_ assetType: String) -> String {
        switch assetType.lowercased() {
        case "gold":
            return "золото"
        case "item":
            return "предмет"
        case "card":
            return "карта"
        case "artifact":
            return "артефакт"
        case "material":
            return "материал"
        case "trophy":
            return "трофей"
        case "order_token":
            return "знак заказа"
        case "practice":
            return "тренировка"
        default:
            return readableIdentifier(assetType)
        }
    }

    func stakeIcon(_ stake: [String: JSONValue]) -> String {
        switch stake.string("asset_type").lowercased() {
        case "gold":
            return "crown.fill"
        case "card":
            return "rectangle.stack.fill"
        case "artifact":
            return "sparkles"
        case "practice":
            return "cpu"
        default:
            return "seal.fill"
        }
    }

    func stakeColor(_ stake: [String: JSONValue]) -> Color {
        switch stake.string("status").lowercased() {
        case "applied":
            return .green
        case "not_applied":
            return .orange
        case "refunded":
            return .cyan
        default:
            return stake.string("asset_type").lowercased() == "practice" ? .orange : .yellow
        }
    }

    func gwentDeckTitle(_ deck: GwentDeck) -> String {
        let playerName = gwentPlayerName(deck.playerId)
        let faction = gwentFactionLabel(gwentDeckFaction(deck))
        if !playerName.isEmpty {
            return "\(playerName) - \(faction)"
        }
        return faction
    }

    func gwentDeckFaction(_ deck: GwentDeck) -> String {
        if let leader = gwentCardMeta(deck.leaderCardId) {
            let faction = leader.faction.trimmingCharacters(in: .whitespacesAndNewlines)
            if !faction.isEmpty {
                return faction
            }
        }
        let factions = deck.cardIds.compactMap { cardId -> String? in
            guard let faction = gwentCardMeta(cardId)?.faction.lowercased(),
                  !faction.isEmpty,
                  faction != "neutral"
            else { return nil }
            return faction
        }
        let counts = Dictionary(grouping: factions, by: { $0 }).mapValues(\.count)
        return counts.max { left, right in left.value < right.value }?.key ?? "neutral"
    }

    func gwentFactionLabel(_ faction: String) -> String {
        switch faction.lowercased() {
        case "northern":
            return "Север"
        case "nilfgaard":
            return "Нильфгаард"
        case "scoiatael", "scoia'tael":
            return "Скоя'таэли"
        case "monsters":
            return "Чудовища"
        case "skellige":
            return "Скеллиге"
        case "neutral", "":
            return "Нейтральная"
        default:
            return readableIdentifier(faction)
        }
    }

    func gwentFactionAbilityLabel(_ faction: String) -> String {
        switch faction.lowercased() {
        case "northern":
            return "+1 карта после выигранного раунда"
        case "nilfgaard":
            return "ничья считается победой фракции"
        case "scoiatael", "scoia'tael":
            return "контроль первого хода"
        case "monsters":
            return "одна unit-карта остается после раунда"
        case "skellige":
            return "возврат карт из сброса в третьем раунде"
        default:
            return "без фракционного бонуса"
        }
    }

    func gwentDeckMetrics(_ deck: GwentDeck) -> GwentDeckMetrics {
        var rows = ["melee": 0, "ranged": 0, "siege": 0]
        var units = 0
        var specials = 0
        var heroes = 0
        for cardId in deck.cardIds {
            guard let meta = gwentCardMeta(cardId) else { continue }
            if meta.type.lowercased() == "unit" {
                units += 1
                if rows[meta.row] != nil {
                    rows[meta.row, default: 0] += 1
                }
            } else if meta.type.lowercased() == "special" {
                specials += 1
            }
            if meta.effect.lowercased() == "hero" {
                heroes += 1
            }
        }
        return GwentDeckMetrics(units: units, specials: specials, heroes: heroes, rows: rows)
    }

    func gwentDeckWarnings(_ metrics: GwentDeckMetrics) -> [String] {
        var warnings: [String] = []
        if metrics.units < 22 {
            warnings.append("Нужно минимум 22 карты отрядов.")
        }
        if metrics.specials > 10 {
            warnings.append("Особых карт должно быть не больше 10.")
        }
        if metrics.activeRows < 2 {
            warnings.append("Колода почти не покрывает боевые ряды.")
        }
        return warnings
    }

    func deckCardDetail(_ cardId: String) -> String {
        guard let meta = gwentCardMeta(cardId) else {
            return readableIdentifier(cardId)
        }
        let effect = meta.effectText.isEmpty
            ? gwentEffectSummary(meta)
            : meta.effectText
        return "\(gwentRowLabel(meta.row)) · \(gwentTypeLabel(meta.type)) · \(effect)"
    }

    func gwentTypeLabel(_ type: String) -> String {
        switch type.lowercased() {
        case "unit":
            return "отряд"
        case "special":
            return "особая карта"
        case "leader":
            return "лидер"
        default:
            return readableIdentifier(type)
        }
    }

    func gwentEffectLabel(_ effect: String) -> String {
        switch effect.lowercased() {
        case "none":
            return "без эффекта"
        case "hero":
            return "герой"
        case "spy":
            return "шпион"
        case "medic":
            return "лекарь"
        case "muster":
            return "сбор"
        case "morale":
            return "боевой дух"
        case "bond", "tight_bond":
            return "связка"
        case "agile":
            return "гибкая"
        case "weather_melee", "biting_frost":
            return "погода: ближний ряд"
        case "weather_ranged", "impenetrable_fog":
            return "погода: дальний ряд"
        case "weather_siege", "torrential_rain":
            return "погода: осада"
        case "clear_weather":
            return "ясная погода"
        case "commanders_horn":
            return "командирский рог"
        case "decoy":
            return "чучело"
        case "scorch":
            return "казнь"
        case "scorch_melee":
            return "казнь ближнего ряда"
        case "scorch_ranged":
            return "казнь дальнего ряда"
        case "scorch_siege":
            return "казнь осады"
        case "leader_foltest_fog":
            return "Фольтест: туман"
        case "leader_foltest_clear_weather":
            return "Фольтест: ясная погода"
        case "leader_foltest_siege_horn":
            return "Фольтест: рог осады"
        case "leader_foltest_siege_scorch":
            return "Фольтест: казнь осады"
        case "leader_emhyr_spy_hand":
            return "Эмгыр: разведка"
        case "leader_emhyr_rain":
            return "Эмгыр: ливень"
        case "leader_emhyr_graveyard_theft":
            return "Эмгыр: карта из сброса"
        case "leader_emhyr_cancel_leader":
            return "Эмгыр: запрет лидера"
        case "leader_francesca_draw":
            return "Францеска: добор"
        case "leader_francesca_frost":
            return "Францеска: мороз"
        case "leader_francesca_melee_scorch":
            return "Францеска: казнь ближнего ряда"
        case "leader_francesca_ranged_horn":
            return "Францеска: рог дальнего ряда"
        case "leader_eredin_graveyard_return":
            return "Эредин: вернуть из сброса"
        case "leader_eredin_melee_horn":
            return "Эредин: рог ближнего ряда"
        case "leader_eredin_discard_draw":
            return "Эредин: сброс и добор"
        case "leader_eredin_weather":
            return "Эредин: погода"
        case "leader_crach_graveyard_shuffle":
            return "Крах: замешать сброс"
        case "coin_toss_first_turn":
            return "жребий первого хода"
        case "faction_northern_realms_draw":
            return "бонус Севера: добор карты"
        case "faction_nilfgaard_tie_win":
            return "бонус Нильфгаарда: победа при ничьей"
        case "faction_scoiatael_choose_first":
            return "бонус Скоя'таэлей: выбор первого хода"
        case "faction_monsters_keep_unit":
            return "бонус Чудовищ: оставить отряд"
        case "faction_skellige_round_three_restore":
            return "бонус Скеллиге: вернуть отряды"
        default:
            return readableIdentifier(effect)
        }
    }

    func cardCanPlay(_ cardId: String, on row: String) -> Bool {
        let rows = legalRows(for: cardId)
        return rows.isEmpty || rows.contains(row)
    }

    func legalRows(for cardId: String) -> [String] {
        if let action = playableAction(for: cardId) {
            let rows = action.arrayStrings("allowed_rows")
            if !rows.isEmpty {
                return rows
            }
        }
        guard let meta = gwentCardMeta(cardId) else { return ownRows }
        let effects = [meta.effect] + meta.abilityTags
        if effects.contains("agile") {
            return ["melee", "ranged"]
        }
        if meta.type == "special" {
            return effects.contains("commanders_horn") ? ownRows : []
        }
        return ownRows.contains(meta.row) ? [meta.row] : ownRows
    }

    func playableAction(for cardId: String) -> [String: JSONValue]? {
        legalActions?
            .array("playable_cards")
            .compactMap(\.objectValue)
            .first { $0.string("card_id") == cardId }
    }

    func targetSelectionIfNeeded(cardId: String, row: String?, match: [String: JSONValue]) -> GwentTargetSelection? {
        guard let action = playableAction(for: cardId) else { return nil }
        let targetKind = action.string("target_kind")
        guard !targetKind.isEmpty, targetKind != "null" else { return nil }
        let targets = action.array("targets").compactMap(\.objectValue)
        if targets.isEmpty {
            return nil
        }
        return GwentTargetSelection(
            action: "play_card",
            matchId: match.string("match_id"),
            roundNumber: activeGwentRoundNumber,
            cardId: cardId,
            row: row,
            targetKind: targetKind,
            discardCardIds: [],
            targets: targets
        )
    }

    func defaultTargetCardId(for cardId: String) -> String? {
        guard let action = playableAction(for: cardId), action.string("target_kind") == "own_non_hero_unit" else {
            return nil
        }
        return action.array("targets").compactMap(\.objectValue).first?.string("card_id")
    }

    func defaultReviveCardId(for cardId: String) -> String? {
        guard let action = playableAction(for: cardId), action.string("target_kind") == "graveyard_unit" else {
            return nil
        }
        return action.array("targets").compactMap(\.objectValue).first?.string("card_id")
    }

    func leaderGraveyardTargets(playerId: String) -> [[String: JSONValue]] {
        deckState(playerId: playerId).arrayStrings("graveyard").compactMap { cardId in
            guard let meta = gwentCardMeta(cardId),
                  meta.type.lowercased() == "unit",
                  !gwentCardEffects(meta).contains("hero")
            else { return nil }
            return [
                "card_id": .string(cardId),
                "row": .string(meta.row),
                "strength": .int(meta.strength),
                "effect": .string(meta.effect)
            ]
        }
    }

    func rowBackground(_ row: String) -> Color {
        gwentRowColor(row).opacity(0.12)
    }

    func boardRowBackground(row: String, playable: Bool, effectTarget: Bool) -> Color {
        if playable {
            return .yellow.opacity(0.24)
        }
        if effectTarget, let selectedCardId {
            return selectedCardActionColor(selectedCardId).opacity(0.18)
        }
        return rowBackground(row)
    }

    func boardRowBackgroundView(
        row: String,
        activeEffects: [GwentEffectInfo],
        playable: Bool,
        effectTarget: Bool
    ) -> some View {
        let hasWeather = activeEffects.contains { $0.id.hasPrefix("weather:") }
        let hasHorn = activeEffects.contains { $0.id.hasPrefix("horn:") }
        return ZStack {
            boardRowBackground(row: row, playable: playable, effectTarget: effectTarget)

            if hasWeather {
                LinearGradient(
                    colors: [
                        .blue.opacity(0.36),
                        .cyan.opacity(0.16),
                        .blue.opacity(0.28)
                    ],
                    startPoint: .leading,
                    endPoint: .trailing
                )
            }

            if hasHorn {
                LinearGradient(
                    colors: [
                        .clear,
                        .orange.opacity(0.26),
                        .yellow.opacity(0.18)
                    ],
                    startPoint: .leading,
                    endPoint: .trailing
                )
            }
        }
    }

    func boardRowStrokeColor(
        row: String,
        activeEffects: [GwentEffectInfo],
        playable: Bool,
        effectTarget: Bool
    ) -> Color {
        if playable {
            return .yellow.opacity(0.82)
        }
        if effectTarget, let selectedCardId {
            return selectedCardActionColor(selectedCardId).opacity(0.68)
        }
        if let effect = activeEffects.first {
            return effect.color.opacity(0.78)
        }
        return gwentRowColor(row).opacity(0.38)
    }

    func activeWeatherRows() -> Set<String> {
        Set(roundState?.arrayStrings("weather_rows") ?? [])
    }

    func activeHornRows(playerId: String) -> Set<String> {
        Set(roundState?.object("horn_rows")?.arrayStrings(playerId) ?? [])
    }

    func activeWeatherEffectInfos() -> [GwentEffectInfo] {
        let rows = activeWeatherRows()
        return ownRows
            .filter { rows.contains($0) }
            .map { activeWeatherEffectInfo(row: $0) }
    }

    func privateRevealEffectInfo() -> GwentEffectInfo? {
        let reveals = deckState(playerId: ownPlayerId).array("private_reveals").compactMap(\.objectValue)
        guard let latestReveal = reveals.last else { return nil }
        let cardIds = latestReveal.arrayStrings("card_ids")
        guard !cardIds.isEmpty else { return nil }
        let titles = cardIds.map(gwentCardTitle)
        return GwentEffectInfo(
            id: "private-reveal:\(cardIds.joined(separator: ","))",
            title: gwentEffectTitle("leader_emhyr_spy_hand"),
            subtitle: "Раскрыто карт: \(cardIds.count)",
            body: titles.joined(separator: ", "),
            icon: gwentEffectIcon("leader_emhyr_spy_hand"),
            badge: "\(cardIds.count)",
            color: gwentEffectColor("leader_emhyr_spy_hand"),
            usesDarkText: false
        )
    }

    func activeRowEffects(playerId: String, row: String) -> [GwentEffectInfo] {
        var effects: [GwentEffectInfo] = []
        if activeWeatherRows().contains(row) {
            effects.append(activeWeatherEffectInfo(row: row))
        }
        if activeHornRows(playerId: playerId).contains(row) {
            effects.append(activeHornEffectInfo(playerId: playerId, row: row))
        }
        return effects
    }

    func activeWeatherEffectInfo(row: String) -> GwentEffectInfo {
        let effect = activeWeatherEffectKey(for: row)
        let rowLabel = shortRowLabel(row).lowercased()
        return GwentEffectInfo(
            id: "weather:\(row):\(effect)",
            title: gwentEffectTitle(effect),
            subtitle: "Влияет на \(rowLabel) ряд у обоих игроков",
            body: gwentEffectDescription(effect, row: row, playerId: nil, cardTitle: nil),
            icon: gwentEffectIcon(effect),
            badge: gwentEffectBadge(effect),
            color: gwentEffectColor(effect),
            usesDarkText: false
        )
    }

    func activeHornEffectInfo(playerId: String, row: String) -> GwentEffectInfo {
        GwentEffectInfo(
            id: "horn:\(playerId):\(row)",
            title: gwentEffectTitle("commanders_horn"),
            subtitle: "\(gwentPlayerName(playerId)): \(shortRowLabel(row).lowercased()) ряд",
            body: gwentEffectDescription("commanders_horn", row: row, playerId: playerId, cardTitle: nil),
            icon: gwentEffectIcon("commanders_horn"),
            badge: gwentEffectBadge("commanders_horn"),
            color: gwentEffectColor("commanders_horn"),
            usesDarkText: false
        )
    }

    func cardEffectInfo(effect: String, cardId: String, row: String?, playerId: String?) -> GwentEffectInfo {
        let normalizedEffect = effect.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        return GwentEffectInfo(
            id: "card:\(cardId):\(normalizedEffect)",
            title: gwentEffectTitle(normalizedEffect),
            subtitle: gwentCardTitle(cardId),
            body: gwentEffectDescription(normalizedEffect, row: row, playerId: playerId, cardTitle: gwentCardTitle(cardId)),
            icon: gwentEffectIcon(normalizedEffect),
            badge: gwentEffectBadge(normalizedEffect),
            color: gwentEffectColor(normalizedEffect),
            usesDarkText: normalizedEffect == "clear_weather"
        )
    }

    func activeWeatherEffectKey(for row: String) -> String {
        let appliedEffects = roundState?.array("effects_applied").compactMap(\.objectValue) ?? []
        for effectRecord in appliedEffects.reversed() {
            let effect = effectRecord.string("effect").trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
            if weatherAffectedRows([effect]).contains(row) {
                return effect
            }

            let weatherCardId = effectRecord.string("weather_card_id").trimmingCharacters(in: .whitespacesAndNewlines)
            if let card = gwentCardMeta(weatherCardId) {
                for cardEffect in gwentCardEffects(card) where weatherAffectedRows([cardEffect]).contains(row) {
                    return cardEffect
                }
            }
        }
        return fallbackWeatherEffect(for: row)
    }

    func fallbackWeatherEffect(for row: String) -> String {
        switch row.lowercased() {
        case "melee":
            return "weather_melee"
        case "ranged":
            return "weather_ranged"
        case "siege":
            return "weather_siege"
        default:
            return "weather_melee"
        }
    }

    func gwentEffectTitle(_ effect: String) -> String {
        switch effect.lowercased() {
        case "weather_melee", "biting_frost":
            return "Мороз"
        case "weather_ranged", "impenetrable_fog":
            return "Туман"
        case "weather_siege", "torrential_rain":
            return "Ливень"
        case "clear_weather":
            return "Ясная погода"
        case "commanders_horn":
            return "Командирский рог"
        case "decoy":
            return "Чучело"
        case "scorch":
            return "Казнь"
        case "scorch_melee":
            return "Казнь ближнего ряда"
        case "scorch_ranged":
            return "Казнь дальнего ряда"
        case "scorch_siege":
            return "Казнь осады"
        default:
            let label = gwentEffectLabel(effect)
            guard let first = label.first else { return label }
            return String(first).uppercased() + label.dropFirst()
        }
    }

    func gwentEffectBadge(_ effect: String) -> String {
        switch effect.lowercased() {
        case "weather_melee", "biting_frost":
            return "Мороз"
        case "weather_ranged", "impenetrable_fog":
            return "Туман"
        case "weather_siege", "torrential_rain":
            return "Ливень"
        case "clear_weather":
            return "Ясно"
        case "commanders_horn":
            return "Рог"
        case "decoy":
            return "Чучело"
        case "scorch", "scorch_melee", "scorch_ranged", "scorch_siege":
            return "Казнь"
        case "bond", "tight_bond":
            return "Связка"
        case "morale":
            return "Дух"
        case "muster":
            return "Сбор"
        case "medic":
            return "Лекарь"
        case "spy":
            return "Шпион"
        case "hero":
            return "Герой"
        default:
            return gwentEffectLabel(effect)
        }
    }

    func gwentEffectDescription(_ effect: String, row: String?, playerId: String?, cardTitle: String?) -> String {
        let rowLabel = row.map { shortRowLabel($0).lowercased() } ?? "выбранный"
        let playerLabel = playerId.map(gwentPlayerName) ?? "этой стороны"
        switch effect.lowercased() {
        case "weather_melee", "biting_frost", "weather_ranged", "impenetrable_fog", "weather_siege", "torrential_rain":
            return "Обычные карты в \(rowLabel) ряду у обоих игроков считаются силой 1. Герои не ослабляются. Ясная погода снимает этот эффект."
        case "clear_weather":
            return "Снимает всю активную погоду со всех боевых рядов. Уже сыгранные роги, герои и прочие способности остаются на столе."
        case "commanders_horn":
            return "Удваивает силу обычных отрядов в \(rowLabel) ряду игрока \(playerLabel). Герои не меняются; при погоде обычная карта сначала становится силой 1, потом удваивается."
        case "decoy":
            return "Верните один свой обычный отряд со стола в руку и положите чучело на его место. Героя так вернуть нельзя."
        case "scorch":
            return "Убирает с поля самые сильные обычные отряды. Герои не сгорают."
        case "scorch_melee":
            return "Убирает самые сильные обычные отряды в ближнем ряду. Герои не сгорают."
        case "scorch_ranged":
            return "Убирает самые сильные обычные отряды в дальнем ряду. Герои не сгорают."
        case "scorch_siege":
            return "Убирает самые сильные обычные отряды в осадном ряду. Герои не сгорают."
        case "hero":
            return "Герой не подвержен погоде, рогу, казни и большинству способностей. Его сила остается напечатанной на карте."
        case "spy":
            return "Шпион кладется на сторону соперника, но дает вам добор карт. Очки шпиона получает сторона, на которой он лежит."
        case "medic":
            return "Позволяет вернуть один обычный отряд из своего сброса на стол. Герои обычно не выбираются целью лекаря."
        case "muster":
            return "Когда карта выходит на стол, она подтягивает связанные карты той же группы, если они доступны в колоде или руке."
        case "morale":
            return "Дает +1 к силе другим обычным отрядам в этом же ряду. Сам носитель боевого духа себя не усиливает."
        case "bond", "tight_bond":
            return "Одинаковые или связанные отряды усиливают друг друга в одном ряду. Чем больше таких карт рядом, тем выше сила группы."
        case "agile":
            return "Гибкую карту можно сыграть в ближний или дальний ряд."
        case "leader_foltest_fog":
            return "Достает из колоды Непроницаемый туман и сразу применяет его."
        case "leader_foltest_clear_weather":
            return "Убирает все погодные эффекты со стола."
        case "leader_foltest_siege_horn":
            return "Удваивает силу вашего осадного ряда как командирский рог."
        case "leader_foltest_siege_scorch":
            return "Казнит сильнейшие обычные карты осадного ряда соперника при сумме ряда 10+."
        case "leader_emhyr_spy_hand":
            return "Показывает три случайные карты в руке соперника."
        case "leader_emhyr_rain":
            return "Достает из колоды Ливень и сразу применяет его."
        case "leader_emhyr_graveyard_theft":
            return "Берет одну обычную карту из сброса соперника в вашу руку."
        case "leader_emhyr_cancel_leader":
            return "Запрещает сопернику использовать способность его лидера."
        case "leader_francesca_draw":
            return "Дает одну дополнительную карту в начале партии."
        case "leader_francesca_frost":
            return "Достает из колоды Мороз и сразу применяет его."
        case "leader_francesca_melee_scorch":
            return "Казнит сильнейшие обычные карты ближнего ряда соперника при сумме ряда 10+."
        case "leader_francesca_ranged_horn":
            return "Удваивает силу вашего дальнего ряда как командирский рог."
        case "leader_eredin_graveyard_return":
            return "Возвращает одну обычную карту из вашего сброса в руку."
        case "leader_eredin_melee_horn":
            return "Удваивает силу вашего ближнего ряда как командирский рог."
        case "leader_eredin_discard_draw":
            return "Сбрасывает две карты из руки и добирает одну карту из колоды."
        case "leader_eredin_weather":
            return "Достает из колоды первую погодную карту и сразу применяет ее."
        default:
            if effect.hasPrefix("leader_") {
                return gwentEffectLabel(effect)
            }
            if let cardTitle {
                return "\(cardTitle): \(gwentEffectLabel(effect))."
            }
            return gwentEffectLabel(effect)
        }
    }

    func selectedCardEffectKeys(_ cardId: String) -> [String] {
        if let meta = gwentCardMeta(cardId) {
            return gwentCardEffects(meta)
        }
        guard let action = playableAction(for: cardId) else { return [] }
        var seen: Set<String> = []
        var result: [String] = []
        for rawEffect in [action.string("effect")] + action.arrayStrings("effects") {
            let effect = rawEffect.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
            guard !effect.isEmpty, effect != "none", !seen.contains(effect) else { continue }
            seen.insert(effect)
            result.append(effect)
        }
        return result
    }

    func selectedCardActionIcon(_ cardId: String) -> String {
        if let effect = selectedCardEffectKeys(cardId).first {
            return gwentEffectIcon(effect)
        }
        return gwentRowIcon(gwentCardMeta(cardId)?.row ?? "special")
    }

    func selectedCardActionColor(_ cardId: String) -> Color {
        let effects = selectedCardEffectKeys(cardId)
        if effects.contains("decoy") || selectedCardNeedsBoardTarget(cardId) {
            return .gray
        }
        if effects.contains("bond") || effects.contains("tight_bond") {
            return .red
        }
        if effects.contains("commanders_horn") {
            return .orange
        }
        if effects.contains(where: isWeatherEffect) {
            return .cyan
        }
        if effects.contains("hero") {
            return .yellow
        }
        if let effect = effects.first {
            return gwentEffectColor(effect)
        }
        return .yellow
    }

    func selectedRowEffectLabel(row: String) -> String {
        guard let selectedCardId else { return "" }
        let effects = selectedCardEffectKeys(selectedCardId)
        if effects.contains("commanders_horn") {
            return "Рог"
        }
        if effects.contains(where: isWeatherEffect) {
            return "Погода"
        }
        return shortRowLabel(row)
    }

    func selectedCardNeedsBoardTarget(_ cardId: String) -> Bool {
        if playableAction(for: cardId)?.string("target_kind") == "own_non_hero_unit" {
            return true
        }
        return selectedCardEffectKeys(cardId).contains("decoy")
    }

    func selectedCardPlaysWithoutSpecificRow(_ cardId: String) -> Bool {
        legalRows(for: cardId).isEmpty
    }

    func selectedCardHighlightsRow(row: String, playerId: String, isOpponent: Bool) -> Bool {
        guard let selectedCardId else { return false }
        let effects = selectedCardEffectKeys(selectedCardId)
        if effects.contains("commanders_horn") {
            return !isOpponent && ownRows.contains(row)
        }
        if effects.contains(where: isWeatherEffect) {
            return weatherAffectedRows(effects).contains(row)
        }
        return false
    }

    var selectedCardDimsUnrelatedBoardCards: Bool {
        guard let selectedCardId else { return false }
        let effects = selectedCardEffectKeys(selectedCardId)
        return selectedCardNeedsBoardTarget(selectedCardId)
            || effects.contains("bond")
            || effects.contains("tight_bond")
    }

    func selectedCardHighlightsAnyCard(in cards: [JSONValue], playerId: String) -> Bool {
        cards.contains { selectedBoardCardIsHighlighted($0, playerId: playerId) }
    }

    func selectedBoardCardIsHighlighted(_ value: JSONValue, playerId: String) -> Bool {
        guard let selectedCardId else { return false }
        let targetCardId = gwentCardId(value)
        if selectedCardNeedsBoardTarget(selectedCardId) {
            guard playerId == ownPlayerId else { return false }
            let targetIds = selectedCardTargetIds(selectedCardId)
            if !targetIds.isEmpty {
                return targetIds.contains(targetCardId)
            }
            guard let targetMeta = gwentCardMeta(targetCardId) else { return false }
            return targetMeta.type.lowercased() == "unit" && !gwentCardEffects(targetMeta).contains("hero")
        }
        guard playerId == ownPlayerId,
              let selectedReference = selectedCardBondReference(selectedCardId),
              let targetMeta = gwentCardMeta(targetCardId)
        else { return false }
        return cardMatchesBondReference(targetMeta, reference: selectedReference)
    }

    func selectedCardTargetIds(_ cardId: String) -> Set<String> {
        guard let action = playableAction(for: cardId) else { return [] }
        return Set(action.array("targets").compactMap(\.objectValue).map { $0.string("card_id") })
    }

    func selectedCardBondReference(_ cardId: String) -> String? {
        guard let card = gwentCardMeta(cardId) else { return nil }
        let effects = gwentCardEffects(card)
        guard effects.contains("bond") || effects.contains("tight_bond") else { return nil }
        let bondGroup = card.bondGroup.trimmingCharacters(in: .whitespacesAndNewlines)
        if !bondGroup.isEmpty {
            return "bond:\(bondGroup)"
        }
        let nameGroup = card.nameGroup.trimmingCharacters(in: .whitespacesAndNewlines)
        return nameGroup.isEmpty ? nil : "name:\(nameGroup)"
    }

    func cardMatchesBondReference(_ card: GwentCard, reference: String) -> Bool {
        if reference.hasPrefix("bond:") {
            return card.bondGroup == String(reference.dropFirst("bond:".count))
        }
        if reference.hasPrefix("name:") {
            return card.nameGroup == String(reference.dropFirst("name:".count))
        }
        return false
    }

    func isWeatherEffect(_ effect: String) -> Bool {
        switch effect.lowercased() {
        case "weather_melee", "biting_frost", "weather_ranged", "impenetrable_fog", "weather_siege", "torrential_rain":
            return true
        default:
            return false
        }
    }

    func weatherAffectedRows(_ effects: [String]) -> Set<String> {
        var rows: Set<String> = []
        for effect in effects {
            switch effect.lowercased() {
            case "weather_melee", "biting_frost":
                rows.insert("melee")
            case "weather_ranged", "impenetrable_fog":
                rows.insert("ranged")
            case "weather_siege", "torrential_rain":
                rows.insert("siege")
            default:
                continue
            }
        }
        return rows
    }

    func jsonBool(_ object: [String: JSONValue], key: String) -> Bool {
        guard let value = object[key] else { return false }
        if case .bool(let boolValue) = value {
            return boolValue
        }
        return value.stringValue == "true"
    }

    func gwentCardId(_ value: JSONValue) -> String {
        if let object = value.objectValue {
            return object.string("card_id", default: "card")
        }
        return value.stringValue ?? "card"
    }

    func gwentCardStrength(_ value: JSONValue) -> Int? {
        if let object = value.objectValue {
            let cardId = gwentCardId(value)
            for key in ["effective_strength", "current_strength", "modified_strength", "score", "strength", "base_strength"] {
                if let strength = object[key]?.intValue {
                    return normalizedPayloadStrength(strength, key: key, cardId: cardId)
                }
            }
        }
        return gwentCardMeta(gwentCardId(value))?.strength
    }

    func gwentBoardCardBaseStrength(_ value: JSONValue) -> Int? {
        if let object = value.objectValue {
            let cardId = gwentCardId(value)
            for key in ["base_strength", "strength", "card_strength"] {
                if let strength = object[key]?.intValue {
                    return normalizedPayloadStrength(strength, key: key, cardId: cardId)
                }
            }
        }
        return gwentCardMeta(gwentCardId(value))?.strength
    }

    func gwentBoardCardProvidedStrength(_ value: JSONValue) -> Int? {
        guard let object = value.objectValue else { return nil }
        for key in ["effective_strength", "current_strength", "modified_strength", "score"] {
            if let strength = object[key]?.intValue {
                return strength
            }
        }
        return nil
    }

    func gwentBoardCardDisplayStrength(
        _ value: JSONValue,
        row: String,
        playerId: String,
        rowCards: [JSONValue]
    ) -> Int? {
        if let provided = gwentBoardCardProvidedStrength(value) {
            return provided
        }
        guard let base = gwentBoardCardBaseStrength(value) else { return nil }

        let cardId = gwentCardId(value)
        let meta = gwentCardMeta(cardId)
        let effects = gwentBoardCardEffects(value, meta: meta)
        guard !effects.contains("hero") else { return base }

        var strength = base
        let weatherRows = Set(roundState?.arrayStrings("weather_rows") ?? [])
        if weatherRows.contains(row) {
            strength = 1
        }

        if effects.contains("bond") || effects.contains("tight_bond") {
            let group = gwentBoardCardGroup(value, meta: meta, key: "bond_group", fallback: cardId)
            let bondCount = rowCards.filter { candidate in
                guard !gwentBoardCardIsRemoved(candidate) else { return false }
                let candidateMeta = gwentCardMeta(gwentCardId(candidate))
                let candidateEffects = gwentBoardCardEffects(candidate, meta: candidateMeta)
                guard candidateEffects.contains("bond") || candidateEffects.contains("tight_bond") else { return false }
                return gwentBoardCardGroup(candidate, meta: candidateMeta, key: "bond_group", fallback: gwentCardId(candidate)) == group
            }.count
            strength *= max(1, bondCount)
        }

        let hornRows = Set(roundState?.object("horn_rows")?.arrayStrings(playerId) ?? [])
        if hornRows.contains(row) {
            strength *= 2
        }

        if !effects.contains("morale") {
            let moraleCount = rowCards.filter { candidate in
                guard !gwentBoardCardIsRemoved(candidate) else { return false }
                return gwentBoardCardEffects(candidate, meta: gwentCardMeta(gwentCardId(candidate))).contains("morale")
            }.count
            strength += moraleCount
        }

        return strength
    }

    func gwentBoardCardEffects(_ value: JSONValue, meta: GwentCard?) -> [String] {
        var seen: Set<String> = []
        var result: [String] = []

        func append(_ raw: String) {
            let effect = raw.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
            guard !effect.isEmpty, effect != "none", !seen.contains(effect) else { return }
            seen.insert(effect)
            result.append(effect)
        }

        if let object = value.objectValue {
            for effect in object.arrayStrings("effects") {
                append(effect)
            }
            append(object.string("effect"))
            if jsonBool(object, key: "hero") {
                append("hero")
            }
        }
        if let meta {
            for effect in gwentCardEffects(meta) {
                append(effect)
            }
        }
        return result
    }

    func gwentBoardCardGroup(_ value: JSONValue, meta: GwentCard?, key: String, fallback: String) -> String {
        if let rawGroup = value.objectValue?.string(key) {
            let group = rawGroup.trimmingCharacters(in: .whitespacesAndNewlines)
            if !group.isEmpty {
                return group
            }
        }
        if key == "bond_group" {
            let bondGroup = meta?.bondGroup.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
            if !bondGroup.isEmpty {
                return bondGroup
            }
        }
        let nameGroup = meta?.nameGroup.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        return nameGroup.isEmpty ? fallback : nameGroup
    }

    func gwentBoardCardIsRemoved(_ value: JSONValue) -> Bool {
        guard let object = value.objectValue else { return false }
        return jsonBool(object, key: "removed")
    }

    func gwentCardMeta(_ cardId: String) -> GwentCard? {
        let snapshotCard = model.snapshot?.gwentCards.first { $0.cardId == cardId }
        if let snapshotCard, !snapshotCard.displayName.isEmpty {
            return snapshotCard
        }
        return GwentStaticCatalog.card(cardId) ?? snapshotCard
    }

    func normalizedPayloadStrength(_ strength: Int, key: String, cardId: String) -> Int {
        guard strength == 0,
              ["strength", "base_strength", "card_strength"].contains(key),
              let meta = gwentCardMeta(cardId),
              meta.type.lowercased() == "unit",
              meta.strength > 0
        else {
            return strength
        }
        return meta.strength
    }

    func gwentRowTotal(_ cards: [JSONValue]) -> Int {
        cards.reduce(0) { partial, value in
            partial + (gwentCardStrength(value) ?? 0)
        }
    }

    func gwentCardTitle(_ cardId: String) -> String {
        if let meta = gwentCardMeta(cardId), !meta.displayName.isEmpty {
            return meta.displayName
        }
        let knownTitles = [
            "gwent_leader_wolf": "Наставник Школы Волка",
            "gwent_leader_nilfgaard": "Посол Империи",
            "gwent_leader_scoiatael": "Старейшина леса",
            "gwent_unit_01": "Реданский пехотинец",
            "gwent_unit_02": "Зигфрид из Денесле",
            "gwent_unit_03": "Боец Синих Полос",
            "gwent_unit_04": "Боец Синих Полос",
            "gwent_unit_05": "Каэдвенский осадный мастер",
            "gwent_unit_06": "Принц Стеннис",
            "gwent_unit_07": "Кейра Мец",
            "gwent_unit_08": "Сабрина Глевиссиг",
            "gwent_unit_09": "Лекарь Бурой Хоругви",
            "gwent_unit_10": "Детмольд",
            "gwent_unit_11": "Осадная башня",
            "gwent_unit_12": "Охотник на драконов из Кринфрида",
            "gwent_unit_13": "Баллиста",
            "gwent_unit_14": "Требушет",
            "gwent_unit_15": "Осадная команда",
            "gwent_unit_16": "Катапульта",
            "gwent_unit_17": "Барклай Эльс",
            "gwent_unit_18": "Краснолюд-застрельщик",
            "gwent_unit_19": "Накер",
            "gwent_unit_20": "Накер",
            "gwent_unit_21": "Шилярд Фиц-Эстерлен",
            "gwent_unit_22": "Осадный техник",
            "gwent_weather_frost": "Мороз",
            "gwent_weather_fog": "Непроницаемый туман",
            "gwent_weather_rain": "Ливень",
            "gwent_clear_weather": "Ясная погода",
            "gwent_horn": "Командирский рог",
            "gwent_decoy": "Чучело",
            "gwent_scorch": "Казнь"
        ]
        if let title = knownTitles[cardId] {
            return title
        }
        if cardId.hasPrefix("gwent_unit_") {
            return "Отряд"
        }
        if cardId.hasPrefix("gwent_weather_") {
            return "Погодная карта"
        }
        if cardId.hasPrefix("gwent_leader_") {
            return "Лидер"
        }
        if cardId.hasPrefix("rare_gwent_") {
            return "Редкая карта Гвинта"
        }
        if cardId.hasPrefix("nr_") {
            return "Карта Северных королевств"
        }
        if cardId.hasPrefix("ng_") {
            return "Карта Нильфгаарда"
        }
        if cardId.hasPrefix("sc_") {
            return "Карта Скоя'таэлей"
        }
        if cardId.hasPrefix("mo_") {
            return "Карта чудовищ"
        }
        if cardId.hasPrefix("neutral_") || cardId.hasPrefix("gwent_") {
            return "Карта Гвинта"
        }
        return "Карта"
    }

    func gwentEffectSummary(_ card: GwentCard) -> String {
        let labels = gwentCardEffects(card).map(gwentEffectLabel)
        return labels.isEmpty ? "без эффекта" : labels.joined(separator: " · ")
    }

    func gwentCardEffects(_ card: GwentCard) -> [String] {
        var seen: Set<String> = []
        var result: [String] = []
        for rawEffect in [card.effect] + card.abilityTags {
            let effect = rawEffect.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
            guard !effect.isEmpty, effect != "none", !seen.contains(effect) else { continue }
            seen.insert(effect)
            result.append(effect)
        }
        return result
    }

    func gwentRowLabel(_ row: String) -> String {
        switch row.lowercased() {
        case "melee":
            return "Ближний"
        case "ranged":
            return "Дальний"
        case "siege":
            return "Осадный"
        case "weather":
            return "Погода"
        case "special":
            return "Особая"
        case "leader":
            return "Лидер"
        default:
            return readableIdentifier(row)
        }
    }

    func gwentStatusLabel(_ status: String) -> String {
        switch status.lowercased() {
        case "active":
            return "активен"
        case "open":
            return "свободен"
        case "queued":
            return "в очереди"
        case "disabled_by_throttle", "paused":
            return "закрыт лимитом"
        case "created", "pending", "published":
            return "ожидает старта"
        case "accepted", "in_progress", "in_match":
            return "матч идет"
        case "round_in_progress":
            return "раунд идет"
        case "pending_player_submissions":
            return "ждем ход"
        case "submitted_pending_sync":
            return "ожидает синхронизации"
        case "needs_master_review":
            return "нужна проверка мастера"
        case "completed", "resolved", "finished":
            return "завершено"
        case "refused", "cancelled":
            return "отменено"
        case "", "unknown":
            return "неизвестно"
        default:
            return readableIdentifier(status)
        }
    }

    func gwentPlayerName(_ playerId: String) -> String {
        if let player = model.player, player.playerId == playerId {
            return player.displayName
        }
        if let player = model.snapshot?.players.first(where: { $0.playerId == playerId }) {
            return player.displayName
        }
        let knownNames = [
            "p_gwent_bot_training": "Тренировочный соперник",
            "p_witcher_1": "Ведьмак Волк",
            "p_witcher_2": "Ведьмак Грифон",
            "p_witcher_3": "Ведьмак Медведь",
            "p_witcher_4": "Ведьмак Кот",
            "p_witcher_5": "Ведьмак Мантикора"
        ]
        return knownNames[playerId] ?? readableIdentifier(playerId, droppingPrefixes: ["p_"])
    }

    func shortGameCode(_ value: String) -> String {
        let trimmed = value.trimmingCharacters(in: .whitespacesAndNewlines)
        if trimmed.isEmpty {
            return "нет кода"
        }
        switch trimmed.lowercased() {
        case "ios_demo_challenge", "demo_challenge":
            return "Демо-вызов"
        case "ios_demo_match", "demo_match":
            return "Демо-матч"
        default:
            break
        }
        if trimmed.contains("_") {
            return readableIdentifier(trimmed, droppingPrefixes: ["demo_"])
        }
        return trimmed.count <= 12 ? trimmed : String(trimmed.suffix(8))
    }

    func readableIdentifier(_ value: String, droppingPrefixes prefixes: [String] = []) -> String {
        var cleaned = value.trimmingCharacters(in: .whitespacesAndNewlines)
        for prefix in prefixes where cleaned.hasPrefix(prefix) {
            cleaned.removeFirst(prefix.count)
            break
        }
        let words = cleaned
            .split(separator: "_")
            .map(String.init)
            .filter { !$0.isEmpty }
        if words.isEmpty {
            return cleaned.isEmpty ? "нет данных" : cleaned
        }
        return words.map { word in
            guard let first = word.first else { return word }
            return String(first).uppercased() + word.dropFirst()
        }.joined(separator: " ")
    }

    func gwentRowColor(_ row: String) -> Color {
        switch row.lowercased() {
        case "melee":
            return .red
        case "ranged":
            return .teal
        case "siege":
            return .indigo
        case "weather":
            return .cyan
        case "special":
            return .orange
        case "leader":
            return .yellow
        default:
            return .secondary
        }
    }

    func gwentRowIcon(_ row: String) -> String {
        switch row.lowercased() {
        case "melee":
            return "shield.lefthalf.filled"
        case "ranged":
            return "scope"
        case "siege":
            return "building.columns"
        case "weather":
            return "cloud"
        case "special":
            return "sparkles"
        case "leader":
            return "crown"
        default:
            return "suit.club"
        }
    }

    func gwentBattleArtworkIcon(cardId: String, row: String) -> String {
        if let meta = gwentCardMeta(cardId) {
            switch meta.effect.lowercased() {
            case "spy":
                return "eye"
            case "medic":
                return "cross.case"
            case "hero":
                return "star.fill"
            case "muster", "morale":
                return "flag.fill"
            case "commanders_horn":
                return "horn"
            case "decoy":
                return "arrow.uturn.backward.circle"
            case "scorch", "scorch_melee", "scorch_ranged", "scorch_siege":
                return "flame.fill"
            default:
                break
            }
        }
        return gwentRowIcon(row)
    }

    func gwentBattleCardBadgeText(card: GwentCard?, strength: Int?, row: String) -> String {
        let type = card?.type.lowercased() ?? ""
        let normalizedRow = row.lowercased()
        if type == "leader" || normalizedRow == "leader" {
            return "Л"
        }
        if normalizedRow == "weather" {
            return "П"
        }
        if type == "special" || normalizedRow == "special" {
            return "О"
        }
        return "\(strength ?? card?.strength ?? 0)"
    }

    func gwentBattleCardBadgeColor(card: GwentCard?, row: String) -> Color {
        let type = card?.type.lowercased() ?? ""
        let normalizedRow = row.lowercased()
        let effects = card.map(gwentCardEffects) ?? []
        if type == "leader" || normalizedRow == "leader" || effects.contains("hero") {
            return .yellow
        }
        if normalizedRow == "weather" {
            return .cyan
        }
        if type == "special" || normalizedRow == "special" {
            return .orange
        }
        return .white
    }

    func gwentEffectIcon(_ effect: String) -> String {
        switch effect.lowercased() {
        case "none":
            return "circle"
        case "hero":
            return "star.fill"
        case "spy":
            return "eye.fill"
        case "medic":
            return "cross.case.fill"
        case "muster":
            return "person.3.fill"
        case "morale":
            return "flag.fill"
        case "bond", "tight_bond":
            return "link"
        case "agile":
            return "arrow.left.arrow.right"
        case "weather_melee", "biting_frost":
            return "snowflake"
        case "weather_ranged", "impenetrable_fog":
            return "cloud.fog.fill"
        case "weather_siege", "torrential_rain":
            return "cloud.rain.fill"
        case "clear_weather":
            return "sun.max.fill"
        case "commanders_horn":
            return "horn"
        case "decoy":
            return "arrow.uturn.backward.circle.fill"
        case "scorch", "scorch_melee", "scorch_ranged", "scorch_siege":
            return "flame.fill"
        default:
            return effect.hasPrefix("leader_") ? "crown.fill" : "sparkles"
        }
    }

    func gwentEffectColor(_ effect: String) -> Color {
        switch effect.lowercased() {
        case "none":
            return .white.opacity(0.34)
        case "hero":
            return .yellow
        case "spy":
            return .purple
        case "medic":
            return .green
        case "muster":
            return .orange
        case "morale":
            return .mint
        case "bond", "tight_bond":
            return .red
        case "agile":
            return .cyan
        case "weather_melee", "biting_frost", "weather_ranged", "impenetrable_fog", "weather_siege", "torrential_rain":
            return .blue
        case "clear_weather":
            return .yellow
        case "commanders_horn":
            return .orange
        case "decoy":
            return .gray
        case "scorch", "scorch_melee", "scorch_ranged", "scorch_siege":
            return .red
        default:
            return effect.hasPrefix("leader_") ? .yellow : .indigo
        }
    }

    func gwentArtworkAssetName(_ cardId: String) -> String? {
        let normalizedCardId = cardId.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !normalizedCardId.isEmpty else { return nil }
        let assetName = "gwent_card_art_\(normalizedCardId)"
        return UIImage(named: assetName) == nil ? nil : assetName
    }
}
