import SwiftUI
import UIKit
import UniformTypeIdentifiers

private struct GwentTargetSelection: Identifiable {
    let id = UUID()
    let matchId: String
    let roundNumber: Int
    let cardId: String
    let row: String?
    let targetKind: String
    let targets: [[String: JSONValue]]

    var title: String {
        switch targetKind {
        case "own_non_hero_unit":
            return "Выбери карту, которую вернет приманка"
        case "graveyard_unit":
            return "Выбери карту из сброса для медика"
        default:
            return "Выбери цель"
        }
    }
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

    init(viewport: CGSize, safeAreaInsets: EdgeInsets, compactHeight: Bool) {
        self.viewport = viewport
        self.safeAreaInsets = safeAreaInsets

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
        let leading = max(max(safeAreaInsets.leading, baseHorizontal), notchFallback)
        let trailing = max(max(safeAreaInsets.trailing, baseHorizontal), notchFallback)
        let top = max(safeAreaInsets.top, baseVertical)
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
        isTightPhone ? 26 : (isCompact ? 28 : 32)
    }

    var playerRailWidth: CGFloat {
        isTightPhone ? 58 : (isCompact ? 70 : 92)
    }

    var railSpacing: CGFloat {
        isTightPhone ? 3 : (isCompact ? 4 : 7)
    }

    var weatherStripHeight: CGFloat {
        isTightPhone ? 22 : (isCompact ? 24 : 30)
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
        isTightPhone ? 36 : (isCompact ? 40 : 50)
    }

    var boardAreaHeight: CGFloat {
        max(170, contentHeight - tableHeaderHeight - handExpandedHeight - (tableStackSpacing * 2))
    }

    var boardRowHeight: CGFloat {
        let fitted = floor((boardAreaHeight - weatherStripHeight - (boardRowSpacing * 6)) / 6)
        switch density {
        case .tightPhone:
            return min(34, max(28, fitted))
        case .phone:
            return min(40, max(32, fitted))
        case .regular:
            return min(52, max(44, fitted))
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
        isTightPhone ? 66 : (isCompact ? 78 : 98)
    }

    var boardCardHeight: CGFloat {
        max(20, boardRowHeight - (isCompact ? 8 : 14))
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
        isTightPhone ? 80 : (isCompact ? 92 : 106)
    }

    var handCardHeight: CGFloat {
        let available = handExpandedHeight - actionButtonHeight - (handStripPadding * 2) - handInternalSpacing
        switch density {
        case .tightPhone:
            return max(46, min(62, available))
        case .phone:
            return max(56, min(72, available))
        case .regular:
            return 82
        }
    }
}

struct GwentTableView: View {
    @EnvironmentObject private var model: AppModel
    @Environment(\.dismiss) private var dismiss
    @Environment(\.verticalSizeClass) private var verticalSizeClass
    @State private var selectedCardId: String?
    @State private var handExpanded = true
    @State private var dropTargetRow: String?
    @State private var inspectedPilePlayerId: String?
    @State private var inspectedPileTitle = "Сброс"
    @State private var pendingTargetSelection: GwentTargetSelection?
    @State private var selectedMulliganCardIds: Set<String> = []
    @State private var selectedDeckId = ""
    @State private var selectedPreferredStartingPlayerId = ""
    @State private var showingDeckReview = false
    @State private var isSavingDeck = false
    @State private var refusalReason = "safety_stop"
    @State private var pendingGwentActionId: String?

    private let ownRows = ["melee", "ranged", "siege"]
    private let opponentRows = ["siege", "ranged", "melee"]

    var body: some View {
        GeometryReader { proxy in
            let isLandscape = proxy.size.width > proxy.size.height
            let layout = GwentTableLayout(
                viewport: proxy.size,
                safeAreaInsets: proxy.safeAreaInsets,
                compactHeight: compactLandscapeTable
            )

            ZStack {
                gwentTableBackground
                    .ignoresSafeArea()

                if isLandscape {
                    landscapeTable(layout: layout)
                } else {
                    portraitRotationPrompt
                }
            }
            .frame(width: proxy.size.width, height: proxy.size.height)
            .ignoresSafeArea()
        }
        .background(GwentOrientationRequester(orientations: .landscape))
        .statusBarHidden()
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
        .sheet(isPresented: $showingDeckReview) {
            deckReviewSheet
        }
        .task {
            await runGwentPollingLoop()
        }
        .onAppear {
            normalizeSelectedDeck()
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
    }

    private func landscapeTable(layout: GwentTableLayout) -> some View {
        VStack(spacing: layout.tableStackSpacing) {
            tableHeader(layout: layout)

            if let match = activeMatch, isMatchResolutionVisible(match) {
                matchResolutionPanel(match)
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else if let match = activeMatch {
                let opponentId = opponentPlayerId
                HStack(spacing: layout.tableColumnSpacing) {
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
                .frame(maxWidth: .infinity, maxHeight: .infinity)

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

            if let stake = activeStake {
                stakePill(stake)
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
        let losses = roundLosses(playerId)
        return HStack(spacing: 5) {
            ForEach(0..<2, id: \.self) { index in
                Image(systemName: index < losses ? "diamond.fill" : "diamond")
                    .font(.caption2.bold())
                    .foregroundStyle(index < losses ? .red.opacity(0.92) : .white.opacity(0.44))
            }
        }
        .frame(height: 18)
        .padding(.horizontal, 6)
        .background(.black.opacity(0.2))
        .clipShape(RoundedRectangle(cornerRadius: 7))
        .accessibilityLabel("Поражения в раундах: \(losses) из 2")
    }

    private func boardRow(playerId: String, row: String, isOpponent: Bool, layout: GwentTableLayout) -> some View {
        let cards = boardCards(playerId: playerId, row: row)
        let isPlayableTarget = selectedCardCanPlay(row: row, isOpponent: isOpponent)
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

            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: layout.isCompact ? 4 : 5) {
                    if cards.isEmpty {
                        emptyRowLabel(row, layout: layout)
                    } else {
                        ForEach(Array(cards.prefix(10).enumerated()), id: \.offset) { _, card in
                            boardCardTile(card, layout: layout)
                        }
                    }
                }
                .frame(maxWidth: .infinity, alignment: isOpponent ? .trailing : .leading)
            }
        }
        .padding(layout.isTightPhone ? 3 : (layout.isCompact ? 4 : 5))
        .frame(height: layout.boardRowHeight)
        .background(rowBackground(row))
        .overlay(
            RoundedRectangle(cornerRadius: 8)
                .stroke(
                    dropTargetRow == rowDropKey(row, isOpponent: isOpponent)
                        ? .yellow.opacity(0.92)
                        : (isPlayableTarget ? .yellow.opacity(0.72) : gwentRowColor(row).opacity(0.38)),
                    lineWidth: dropTargetRow == rowDropKey(row, isOpponent: isOpponent) || isPlayableTarget ? 2 : 1
                )
        )
        .clipShape(RoundedRectangle(cornerRadius: 8))
        .contentShape(Rectangle())
        .onTapGesture {
            guard let match = activeMatch, let selectedCardId else { return }
            guard cardCanUseBoardSide(selectedCardId, isOpponent: isOpponent) else {
                model.errorMessage = wrongSideMessage(for: selectedCardId)
                return
            }
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
        return HStack(spacing: layout.isCompact ? 6 : 8) {
            Text("Раунд \(roundNumber)")
                .font(layout.isCompact ? .caption2.bold() : .caption.bold())
            Divider()
                .frame(height: layout.isCompact ? 14 : 18)
                .overlay(.white.opacity(0.25))
            Label("Погода", systemImage: "cloud")
                .font(.caption2.bold())
                .foregroundStyle(.cyan.opacity(0.95))
            if !history.isEmpty, !layout.isTightPhone {
                Divider()
                    .frame(height: layout.isCompact ? 14 : 18)
                    .overlay(.white.opacity(0.25))
                Text(history)
                    .font(.caption2.bold())
                    .foregroundStyle(.white.opacity(0.62))
                    .lineLimit(1)
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

    private func handStrip(match: [String: JSONValue], layout: GwentTableLayout) -> some View {
        let canPlay = activeGwentCanPlay
        return VStack(spacing: layout.handInternalSpacing) {
            HStack(spacing: layout.isCompact ? 6 : 8) {
                Button {
                    withAnimation(.spring(response: 0.24, dampingFraction: 0.82)) {
                        handExpanded.toggle()
                    }
                } label: {
                    Label("Рука \(activeGwentHand.count)", systemImage: handExpanded ? "chevron.down" : "chevron.up")
                        .font(layout.isCompact ? .caption2.bold() : .caption.bold())
                        .frame(width: layout.isTightPhone ? 82 : (layout.isCompact ? 96 : 112), height: layout.actionButtonHeight)
                }
                .buttonStyle(.bordered)
                .tint(.yellow)

                if let selectedCardId, canPlay {
                    selectedCardControls(cardId: selectedCardId, match: match, layout: layout)
                } else {
                    Text(activeGwentTurnText)
                        .font(layout.isCompact ? .caption2.bold() : .caption.bold())
                        .foregroundStyle(activeGwentCanPlay ? .yellow : .white.opacity(0.58))
                        .lineLimit(1)
                        .minimumScaleFactor(0.72)
                }

                if isSubmittingGwentAction {
                    ProgressView()
                        .controlSize(.small)
                        .tint(.yellow)
                }

                Spacer()

                Button {
                    Task { await pass(match: match) }
                } label: {
                    Label("Пас", systemImage: "hand.raised.fill")
                        .font(layout.isCompact ? .caption2.bold() : .caption.bold())
                        .frame(width: layout.isTightPhone ? 70 : (layout.isCompact ? 84 : 100), height: layout.actionButtonHeight)
                }
                .buttonStyle(.bordered)
                .tint(.orange)
                .disabled(!activeGwentCanPass)

                Button {
                    Task { await useLeader(match: match) }
                } label: {
                    Label("Лидер", systemImage: "crown.fill")
                        .font(layout.isCompact ? .caption2.bold() : .caption.bold())
                        .frame(width: layout.isTightPhone ? 78 : (layout.isCompact ? 90 : 104), height: layout.actionButtonHeight)
                }
                .buttonStyle(.borderedProminent)
                .tint(.yellow)
                .disabled(!activeGwentCanUseLeader)
            }

            if handExpanded {
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
                                Button {
                                    selectedCardId = selectedCardId == cardId ? nil : cardId
                                } label: {
                                    handCard(cardId, selected: selectedCardId == cardId, enabled: canPlay, layout: layout)
                                }
                                .buttonStyle(.plain)
                                .disabled(!canPlay)
                                .onDrag {
                                    selectedCardId = cardId
                                    return NSItemProvider(object: cardId as NSString)
                                }
                            }
                        }
                    }
                    .padding(.horizontal, 2)
                }
            }
        }
        .padding(layout.handStripPadding)
        .frame(height: handExpanded ? layout.handExpandedHeight : layout.handCollapsedHeight)
        .background(.black.opacity(0.26))
        .overlay(
            RoundedRectangle(cornerRadius: 8)
                .stroke(.white.opacity(0.12), lineWidth: 1)
        )
        .clipShape(RoundedRectangle(cornerRadius: 8))
    }

    private func handCard(
        _ cardId: String,
        selected: Bool,
        enabled: Bool,
        layout providedLayout: GwentTableLayout? = nil
    ) -> some View {
        let layout = providedLayout ?? fallbackTableLayout
        let meta = gwentCardMeta(cardId)
        let row = meta?.row ?? "card"

        return VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text(meta.map { String($0.strength) } ?? "-")
                    .font(layout.isCompact ? .caption.bold() : .headline.bold())
                    .foregroundStyle(gwentRowColor(row))
                Spacer()
                Image(systemName: gwentRowIcon(row))
                    .font(.caption.bold())
                    .foregroundStyle(gwentRowColor(row))
            }

            Spacer(minLength: 0)

            Text(gwentCardTitle(cardId))
                .font(layout.isCompact ? .caption2.bold() : .caption.bold())
                .lineLimit(2)
                .minimumScaleFactor(0.62)

            Text(handCardPlacementLabel(cardId, row: row))
                .font(.caption2)
                .foregroundStyle(.white.opacity(0.58))
                .lineLimit(1)
        }
        .foregroundStyle(enabled ? .white : .white.opacity(0.42))
        .padding(layout.handCardPadding)
        .frame(width: layout.handCardWidth, height: layout.handCardHeight)
        .background(
            LinearGradient(
                colors: [
                    gwentRowColor(row).opacity(selected ? 0.38 : 0.2),
                    .black.opacity(0.38)
                ],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
        )
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
                Text(gwentCardTitle(cardId))
                    .font(layout.isCompact ? .caption2.bold() : .caption.bold())
                    .foregroundStyle(.yellow)
                    .lineLimit(1)
                    .frame(maxWidth: layout.isTightPhone ? 88 : (layout.isCompact ? 116 : 150), alignment: .leading)

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
                    selectedCardId = nil
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

    private func boardCardTile(_ value: JSONValue, layout: GwentTableLayout) -> some View {
        let cardId = gwentCardId(value)
        let meta = gwentCardMeta(cardId)
        let row = meta?.row ?? value.objectValue?.string("row") ?? "card"

        return HStack(spacing: 5) {
            Text("\(gwentCardStrength(value) ?? 0)")
                .font(layout.isCompact ? .caption2.bold() : .caption.bold())
                .foregroundStyle(gwentRowColor(row))
                .frame(width: layout.isCompact ? 14 : 18)
            Text(gwentCardTitle(cardId))
                .font(.caption2.bold())
                .lineLimit(1)
                .minimumScaleFactor(0.6)
        }
        .foregroundStyle(.white)
        .padding(.horizontal, layout.isTightPhone ? 4 : (layout.isCompact ? 5 : 7))
        .frame(width: layout.boardCardWidth, height: layout.boardCardHeight, alignment: .leading)
        .background(.black.opacity(0.3))
        .overlay(
            RoundedRectangle(cornerRadius: 7)
                .stroke(gwentRowColor(row).opacity(0.44), lineWidth: 1)
        )
        .clipShape(RoundedRectangle(cornerRadius: 7))
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
            deckMetricChip("Unit", metrics.units, ok: metrics.units >= 22)
            deckMetricChip("Special", metrics.specials, ok: metrics.specials <= 10)
            deckMetricChip("Hero", metrics.heroes, ok: true)
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
                        LabeledContent("Unit / Special", value: "\(metrics.units) / \(metrics.specials)")
                        LabeledContent("Hero", value: "\(metrics.heroes)")
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
            compactHeight: compactLandscapeTable
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
        await submitGwentAction(
            matchId: selection.matchId,
            roundNumber: selection.roundNumber,
            action: "play_card",
            cardId: selection.cardId,
            row: selection.row,
            targetCardId: selection.targetKind == "own_non_hero_unit" ? target.string("card_id") : nil,
            reviveCardId: selection.targetKind == "graveyard_unit" ? target.string("card_id") : nil
        )
        selectedCardId = nil
        pendingTargetSelection = nil
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

    @MainActor
    func useLeader(match: [String: JSONValue]) async {
        await submitGwentAction(
            matchId: match.string("match_id"),
            roundNumber: activeGwentRoundNumber,
            action: "use_leader",
            cardId: legalActions?.string("leader_card_id"),
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
            return action.string("effect") == "spy"
        }
        return gwentCardMeta(cardId)?.effect == "spy"
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
        return cardCanUseBoardSide(selectedCardId, isOpponent: isOpponent)
            && cardCanPlay(selectedCardId, on: row)
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
        readableIdentifier(deck.deckId, droppingPrefixes: ["deck_", "gwent_deck_"])
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
            warnings.append("Нужно минимум 22 unit-карты.")
        }
        if metrics.specials > 10 {
            warnings.append("Special-карт должно быть не больше 10.")
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
        let effect = meta.effect == "none" ? "без эффекта" : gwentEffectLabel(meta.effect)
        return "\(gwentRowLabel(meta.row)) · \(gwentTypeLabel(meta.type)) · \(effect)"
    }

    func gwentTypeLabel(_ type: String) -> String {
        switch type.lowercased() {
        case "unit":
            return "unit"
        case "special":
            return "special"
        case "leader":
            return "leader"
        default:
            return readableIdentifier(type)
        }
    }

    func gwentEffectLabel(_ effect: String) -> String {
        switch effect.lowercased() {
        case "none":
            return "без эффекта"
        case "hero":
            return "hero"
        case "spy":
            return "spy"
        case "medic":
            return "medic"
        case "muster":
            return "muster"
        case "morale":
            return "morale"
        case "bond", "tight_bond":
            return "tight bond"
        case "agile":
            return "agile"
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
            return "приманка"
        case "scorch":
            return "казнь"
        case "leader_order_rally":
            return "приказ лидера"
        case "leader_foltest_clear_weather":
            return "Фольтест: ясная погода"
        case "leader_emhyr_graveyard_theft":
            return "Эмгыр: карта из сброса"
        case "leader_francesca_ranged_horn":
            return "Францеска: рог дальнего ряда"
        case "leader_eredin_melee_horn":
            return "Эредин: рог ближнего ряда"
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
        if meta.effect == "agile" {
            return ["melee", "ranged"]
        }
        if meta.type == "special" {
            return meta.effect == "commanders_horn" ? ownRows : []
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
            matchId: match.string("match_id"),
            roundNumber: activeGwentRoundNumber,
            cardId: cardId,
            row: row,
            targetKind: targetKind,
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

    func rowBackground(_ row: String) -> Color {
        gwentRowColor(row).opacity(0.12)
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
        if let object = value.objectValue, let strength = object["strength"]?.intValue {
            return strength
        }
        return gwentCardMeta(gwentCardId(value))?.strength
    }

    func gwentCardMeta(_ cardId: String) -> GwentCard? {
        model.snapshot?.gwentCards.first { $0.cardId == cardId }
    }

    func gwentRowTotal(_ cards: [JSONValue]) -> Int {
        cards.reduce(0) { partial, value in
            partial + (gwentCardStrength(value) ?? 0)
        }
    }

    func gwentCardTitle(_ cardId: String) -> String {
        let knownTitles = [
            "gwent_leader_wolf": "Наставник Школы Волка",
            "gwent_leader_nilfgaard": "Посол Империи",
            "gwent_leader_scoiatael": "Старейшина леса",
            "gwent_unit_01": "Серебряный клинок",
            "gwent_unit_02": "Следопыт Каэр Морхена",
            "gwent_unit_03": "Арбалетчик Темерии",
            "gwent_unit_04": "Каэдвенский копейщик",
            "gwent_unit_07": "Лучник Синих Полос",
            "gwent_unit_08": "Осадная команда",
            "gwent_weather_frost": "Белый Хлад",
            "gwent_horn": "Командирский рог"
        ]
        if let title = knownTitles[cardId] {
            return title
        }
        if cardId.hasPrefix("gwent_unit_") {
            let suffix = cardId.replacingOccurrences(of: "gwent_unit_", with: "")
            return suffix.isEmpty ? "Боевая карта" : "Боевая карта \(suffix)"
        }
        if cardId.hasPrefix("gwent_weather_") {
            return "Погода: \(readableIdentifier(cardId, droppingPrefixes: ["gwent_weather_"]))"
        }
        if let meta = gwentCardMeta(cardId), meta.type.lowercased() == "leader" {
            return "Лидер \(readableIdentifier(cardId, droppingPrefixes: ["gwent_leader_", "gwent_"]))"
        }
        return readableIdentifier(cardId, droppingPrefixes: ["gwent_"])
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
}
