import SwiftUI
#if canImport(UIKit)
import UIKit
#endif

private let gwentDeckMinUnitCards = 22
private let gwentDeckSpecialCardLimit = 10

struct HomeView: View {
    @EnvironmentObject private var model: AppModel
    @State private var selectedTab: HomeTab = .journal
    @State private var appliedInitialTab = false
    @State private var showQR = false
    @State private var showPVEMission = false
    @State private var pendingMissionPresentation = false
    @State private var showGwentTable = false
    @State private var showCharacterProgress = false
    @State private var inventoryMode: InventoryMode = .bag
    @State private var selectedMarketMaterialId = ""
    @State private var materialSellQuantity = 1
    @State private var tradeRecipient = ""
    @State private var selectedTradeAssetKey = ""
    @State private var tradeAssetType = "item"
    @State private var tradeAssetId = ""
    @State private var tradeQuantity = 1
    @State private var tradePriceGold = 0
    @State private var tradeMode = "gift"
    @State private var tradeActionId = ""
    @State private var tradeDeclineReason = "declined"
    @State private var gwentTargetId = "p_witcher_2"
    @State private var gwentStakeType = "gold"
    @State private var gwentStakeId = "gold"
    @State private var gwentGoldStakeAmount = 5
    @State private var gwentRefusalReason = "safety_stop"
    @State private var showServerSettings = false
    @State private var serverURLText = ""
    @State private var deckMode: DeckSetupMode = .builder
    @State private var deckEncyclopediaScope: DeckEncyclopediaScope = .owned
    @State private var deckRowFilter: DeckRowFilter = .all
    @State private var deckStrengthFilter: DeckStrengthFilter = .all
    @State private var deckDraftCardIds: [String] = []
    @State private var deckDraftLeaderId = ""
    @State private var deckDraftSourceFingerprint = ""
    @State private var selectedDeckCardId = ""
    @State private var showDeckCardInspector = false
    @State private var pendingDeckRemovalCardId = ""
    @State private var appliedDeckScreenshotArguments = false
    @State private var isSavingDeckDraft = false

    var body: some View {
        TabView(selection: $selectedTab) {
            journal
                .tabItem { Label("Журнал", systemImage: "book.closed") }
                .tag(HomeTab.journal)
            pvp
                .tabItem { Label("Дуэли", systemImage: "suit.club") }
                .tag(HomeTab.pvp)
            deckSetup
                .tabItem { Label("Колода", systemImage: "rectangle.stack") }
                .tag(HomeTab.deck)
            inventory
                .tabItem { Label("Инвентарь", systemImage: "backpack") }
                .tag(HomeTab.inventory)
            orders
                .tabItem { Label("Заказы", systemImage: "scroll") }
                .tag(HomeTab.orders)
        }
        .sheet(isPresented: $showQR) {
            QRScannerSheet {
                pendingMissionPresentation = true
                showQR = false
            }
        }
        .fullScreenCover(isPresented: $showPVEMission) {
            PVEMissionSheet {
                showPVEMission = false
            }
            .environmentObject(model)
        }
        .fullScreenCover(isPresented: $showGwentTable) {
            GwentTableView()
                .environmentObject(model)
        }
        .sheet(isPresented: $showDeckCardInspector) {
            if let card = selectedDeckCard {
                deckCardDetailSheet(card)
            }
        }
        .sheet(isPresented: $showServerSettings) {
            serverSettingsSheet
        }
        .sheet(isPresented: $showCharacterProgress) {
            characterProgressSheet
        }
        .onChange(of: showQR) { isPresented in
            guard !isPresented, pendingMissionPresentation else { return }
            pendingMissionPresentation = false
            if model.activePVEMission != nil {
                showPVEMission = true
            }
        }
        .onAppear {
            guard !appliedInitialTab else { return }
            appliedInitialTab = true
            if let tabName = model.screenshotInitialTab {
                applyInitialTab(named: tabName)
            }
            if model.gwentUXEnabled && model.screenshotShowsGwentTable {
                selectedTab = .pvp
                showGwentTable = true
            }
            if model.screenshotShowsQR {
                selectedTab = .journal
                showQR = true
            }
            if !model.screenshotMode {
                Task { await model.checkServerHealth() }
            }
        }
    }

    private func applyInitialTab(named tabName: String) {
        let normalized = tabName.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        switch normalized {
        case "gwent", "pvp", "gwent_games", "gwent-games":
            selectedTab = .pvp
        case "deck", "gwent_deck", "gwent-deck", "deck_setup", "deck-setup":
            selectedTab = .deck
        case "qr":
            selectedTab = .journal
            showQR = true
        case "sync", "server", "settings":
            selectedTab = .journal
        default:
            if let tab = HomeTab(rawValue: normalized) {
                selectedTab = tab
            }
        }
    }

    private var journal: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    if let player = model.player {
                        characterCard(player)
                    }

                    journalQRButton
                    currentActCard

                    if let result = model.lastPvEResult {
                        lastResultCard(result)
                    }

                    goalsCard
                }
                .padding()
            }
            .navigationTitle("Полевой журнал")
            .toolbar {
                Button {
                    serverURLText = model.serverURL.absoluteString
                    showServerSettings = true
                } label: {
                    Label("Сервер", systemImage: "gearshape")
                }
            }
        }
    }

    private var journalQRButton: some View {
        Button {
            if model.activePVEMission != nil {
                showPVEMission = true
            } else {
                showQR = true
            }
        } label: {
            Label(
                model.activePVEMission == nil ? "Сканировать QR" : "Продолжить миссию",
                systemImage: model.activePVEMission == nil ? "qrcode.viewfinder" : "scroll"
            )
                .frame(maxWidth: .infinity)
        }
        .buttonStyle(.borderedProminent)
    }

    private func characterCard(_ player: PlayerProfile) -> some View {
        Button {
            showCharacterProgress = true
        } label: {
            characterCardContent(player)
        }
        .buttonStyle(.plain)
        .overlay(alignment: .topTrailing) {
            if model.allocatableStatPoints(for: player) > 0 {
                Circle()
                    .fill(.red)
                    .frame(width: 14, height: 14)
                    .overlay(Circle().stroke(.black.opacity(0.45), lineWidth: 1))
                    .padding(10)
                    .accessibilityLabel("Доступна прокачка")
            }
        }
    }

    private func characterCardContent(_ player: PlayerProfile) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(alignment: .firstTextBaseline) {
                VStack(alignment: .leading, spacing: 4) {
                    Text(player.displayName)
                        .font(.title2.bold())
                    Text(roleLabel(player.roleType))
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                }
                Spacer()
                Text(syncStateLabel(model.syncState))
                    .font(.caption.bold())
                    .padding(.horizontal, 10)
                    .padding(.vertical, 6)
                    .background(.thinMaterial)
                    .clipShape(Capsule())
            }

            HStack {
                metric("Ур.", "\(player.level)")
                metric("Золото", "\(player.gold)g")
                metric("PvP", "\(player.challengeTokens)")
            }

            xpProgressBar(player)

            reputationRow(player)
        }
        .cardStyle()
    }

    private var characterProgressSheet: some View {
        NavigationStack {
            ScrollView {
                if let player = model.player {
                    VStack(alignment: .leading, spacing: 16) {
                        VStack(alignment: .leading, spacing: 6) {
                            Text(player.displayName)
                                .font(.title2.bold())
                            Text("Ур. \(player.level) · \(player.xp) XP")
                                .font(.subheadline)
                                .foregroundStyle(.secondary)
                        }

                        VStack(alignment: .leading, spacing: 10) {
                            HStack {
                                Text("Статы")
                                    .font(.headline)
                                Spacer()
                                Text("\(model.allocatableStatPoints(for: player))")
                                    .font(.headline.monospacedDigit())
                                    .foregroundStyle(model.allocatableStatPoints(for: player) > 0 ? .red : .secondary)
                            }
                            ForEach(AppModel.canonicalStats, id: \.self) { stat in
                                statAllocationRow(stat, player: player)
                            }
                        }
                        .cardStyle()
                    }
                    .padding()
                }
            }
            .navigationTitle("Персонаж")
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("Готово") { showCharacterProgress = false }
                }
            }
        }
    }

    private func statAllocationRow(_ stat: String, player: PlayerProfile) -> some View {
        HStack {
            Text(stat)
                .font(.body.weight(.medium))
            Spacer()
            Text("\(player.stats[stat] ?? 0)")
                .font(.headline.monospacedDigit())
                .frame(minWidth: 28, alignment: .trailing)
            Button {
                model.allocateStatPoint(stat)
            } label: {
                Image(systemName: "plus.circle.fill")
                    .imageScale(.large)
            }
            .buttonStyle(.plain)
            .disabled(!model.canAllocateStat(stat, for: player))
            .foregroundStyle(model.canAllocateStat(stat, for: player) ? .orange : .secondary)
            .accessibilityLabel("Повысить \(stat)")
        }
    }

    private func metric(_ title: String, _ value: String) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(title)
                .font(.caption)
                .foregroundStyle(.secondary)
            Text(value)
                .font(.headline)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private func xpProgressBar(_ player: PlayerProfile) -> some View {
        let progress = xpProgress(for: player)
        return VStack(alignment: .leading, spacing: 6) {
            HStack {
                Text("XP прогресс")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                Spacer()
                Text(progress.percentLabel)
                    .font(.caption.bold())
                    .foregroundStyle(.secondary)
            }
            ProgressView(value: progress.fraction)
                .tint(.orange)
                .accessibilityLabel("XP прогресс")
                .accessibilityValue(progress.accessibilityLabel)
            Text(progress.detailLabel)
                .font(.caption2)
                .foregroundStyle(.secondary)
        }
        .padding(.top, 2)
    }

    private func reputationRow(_ player: PlayerProfile) -> some View {
        HStack(alignment: .firstTextBaseline, spacing: 8) {
            Text("Добро/Зло")
                .font(.caption)
                .foregroundStyle(.secondary)
            Text(player.reputationLabel.isEmpty ? "Нейтрально" : player.reputationLabel)
                .font(.footnote.weight(.semibold))
                .foregroundStyle(.primary)
                .lineLimit(2)
                .fixedSize(horizontal: false, vertical: true)
            Spacer(minLength: 0)
        }
        .padding(.top, 2)
    }

    private func xpProgress(for player: PlayerProfile) -> XPProgress {
        let required = nextLevelCost(for: player.level)
        guard required > 0 else {
            return XPProgress(
                fraction: 1,
                percentLabel: "100%",
                detailLabel: "Максимум известной шкалы",
                accessibilityLabel: "100 процентов"
            )
        }
        let current = max(0, player.xp)
        let fraction = min(1, Double(current) / Double(required))
        let percent = Int((fraction * 100).rounded())
        return XPProgress(
            fraction: fraction,
            percentLabel: "\(percent)%",
            detailLabel: "\(current) / \(required) XP до ур. \(player.level + 1)",
            accessibilityLabel: "\(percent) процентов, \(current) из \(required) XP до следующего уровня"
        )
    }

    private func nextLevelCost(for level: Int) -> Int {
        let costs = xpLevelCosts
        let index = costs.first == 0 ? level : level - 1
        guard index >= 0, index < costs.count else { return 0 }
        return costs[index]
    }

    private var xpLevelCosts: [Int] {
        let defaultCosts = [0, 10, 25, 45, 70, 100, 135, 175, 220, 270]
        guard
            let raw = model.snapshot?.checks.xpRules.first?.string("level_thresholds"),
            !raw.isEmpty
        else { return defaultCosts }
        let parsed = raw
            .split(separator: ";")
            .compactMap { Int($0.trimmingCharacters(in: .whitespacesAndNewlines)) }
        return parsed.isEmpty ? defaultCosts : parsed
    }

    private func lastResultCard(_ result: PvESceneDraft) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Последняя сцена")
                .font(.headline)
            Text("\(result.qr.manualCode) · \(pveSceneTypeLabel(result.scenario.sceneType))")
                .font(.subheadline)
            Text(result.rollSummary)
                .font(.footnote.monospacedDigit())
                .fixedSize(horizontal: false, vertical: true)
            Text(result.resultLabel)
                .font(.title3.bold())
            Text("Награда: \(result.rewardLine)")
                .font(.footnote)
                .foregroundStyle(.secondary)
            Text("Событие сохранено на телефоне и уйдет при следующей синхронизации.")
                .font(.caption)
                .foregroundStyle(.secondary)
        }
        .cardStyle()
    }

    private var goalsCard: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Цели")
                .font(.headline)
            if let snapshot = model.snapshot, !snapshot.visibleGoals.isEmpty {
                ForEach(snapshot.visibleGoals.prefix(4)) { goal in
                    Text(goal.title)
                        .font(.subheadline)
                }
            } else {
                Text("Пока нет раскрытых личных целей.")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
            }
        }
        .cardStyle()
    }

    private var currentActCard: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Text("Текущий акт")
                    .font(.headline)
                Spacer()
                Text(currentActLabel)
                    .font(.caption.bold())
                    .padding(.horizontal, 10)
                    .padding(.vertical, 5)
                    .background(.blue.opacity(0.12))
                    .clipShape(Capsule())
                    .foregroundStyle(.secondary)
            }

            Text(currentActHint)
                .font(.footnote)
                .foregroundStyle(.secondary)
        }
        .cardStyle()
    }

    private var currentActLabel: String {
        if let actId = serverCurrentActId ?? fallbackCurrentActId {
            return actDisplayName(actId)
        }
        return "ожидает мастера"
    }

    private var currentActHint: String {
        if serverCurrentActId != nil {
            return "Акт задан мастером на сервере и обновляется на телефоне вместе с дневником."
        }
        if model.snapshot == nil {
            return "После входа и загрузки дневника телефон получит актуальное состояние игры с сервера."
        }
        return "Ждём серверное объявление акта. Будущие QR останутся закрыты до синхронизации."
    }

    private var serverCurrentActId: String? {
        let raw = model.snapshot?.actUnlockState.string("current_act_id") ?? ""
        let normalized = raw.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        return normalized.isEmpty ? nil : normalized
    }

    private var fallbackCurrentActId: String? {
        let visibleActOrder = ["final_act", "act3", "act2", "act1"]
        return visibleActOrder.first { model.effectiveUnlockedActIds.contains($0) }
    }

    private var serverSettingsSheet: some View {
        NavigationStack {
            Form {
                Section("Связь с игрой") {
                    Label(syncStateLabel(model.syncState), systemImage: syncStateIcon(model.syncState))
                    Text("Адрес игры: \(model.serverURL.absoluteString)")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    Text(model.serverConnectionLabel)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    Text(model.pendingEvents.isEmpty ? "Все события отправлены." : "На телефоне ждут отправки: \(model.pendingEvents.count)")
                        .font(.caption)
                        .foregroundStyle(.secondary)

                    if let info = model.infoMessage {
                        Text(info)
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                    if let error = model.errorMessage {
                        Text(error)
                            .font(.caption)
                            .foregroundStyle(.red)
                    }

                    Button {
                        Task { await model.checkServerHealth() }
                    } label: {
                        Label("Проверить связь", systemImage: "network")
                    }

                    Button {
                        Task { await model.refreshSnapshot() }
                    } label: {
                        Label("Обновить дневник", systemImage: "square.and.arrow.down")
                    }

                    Button {
                        Task { await model.syncPendingEvents() }
                    } label: {
                        Label("Отправить события", systemImage: "arrow.triangle.2.circlepath")
                    }
                    .disabled(model.pendingEvents.isEmpty)
                }

                Section("Сервер игры") {
                    Text("Адрес игры: \(model.serverURL.absoluteString)")
                        .font(.caption)
                        .foregroundStyle(.secondary)

                    TextField(AppModel.defaultServerURLString, text: $serverURLText)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()

                    Button {
                        if model.updateServerURL(from: serverURLText) {
                            serverURLText = model.serverURL.absoluteString
                            Task { await model.checkServerHealth() }
                        }
                    } label: {
                        Label("Сохранить и проверить", systemImage: "checkmark.circle")
                    }

                }

                Section {
                    Button("Сбросить локальную сессию", role: .destructive) {
                        model.resetLocalSession()
                        showServerSettings = false
                    }
                } footer: {
                    Text("Сброс удаляет сохраненный код, данные игры и очередь с этого iPhone. Адрес сервера остается.")
                }
            }
            .navigationTitle("Настройки")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Готово") {
                        showServerSettings = false
                    }
                }
            }
        }
    }

    private var inventory: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    Picker("Раздел", selection: $inventoryMode) {
                        ForEach(InventoryMode.allCases) { mode in
                            Text(mode.title).tag(mode)
                        }
                    }
                    .pickerStyle(.segmented)

                    switch inventoryMode {
                    case .bag:
                        bagSection
                    case .market:
                        materialMarketSection
                    case .trade:
                        tradeSection
                    }
                }
                .padding()
            }
            .navigationTitle("Инвентарь")
        }
    }

    private var bagSection: some View {
        VStack(alignment: .leading, spacing: 16) {
            materialInventoryCard
            potionInventoryCard
            ownedAssetsCard
            lockedRewardsCard
        }
    }

    private var materialInventoryCard: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Материалы")
                .font(.headline)
            if ownedMaterials.isEmpty {
                Text("Материалов в сумке пока нет.")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
            } else {
                ForEach(Array(ownedMaterials.prefix(10).enumerated()), id: \.offset) { _, row in
                    let materialId = row.string("material_id")
                    let market = marketRow(materialId: materialId)
                    inventoryAssetRow(
                        title: assetDisplayName(materialId),
                        subtitle: "\(materialCategoryLabel(row.string("category"))) · x\(row.int("quantity"))",
                        detail: materialInventoryDetail(row, market: market),
                        icon: assetIcon("material")
                    )
                }
            }
        }
        .cardStyle()
    }

    private var ownedAssetsCard: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Трофеи и квестовые вещи")
                .font(.headline)
            if ownedAssets.isEmpty {
                Text("У персонажа пока нет трофеев или квестовых вещей.")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
            } else {
                ForEach(Array(ownedAssets.prefix(8).enumerated()), id: \.offset) { _, row in
                    inventoryAssetRow(
                        title: assetDisplayName(row.string("asset_id")),
                        subtitle: "\(assetTypeLabel(row.string("asset_type"))) · \(assetStatusLabel(row.string("status"))) · x\(row.int("quantity", default: 1))",
                        detail: assetEffectLine(row.string("asset_id")),
                        icon: assetIcon(row.string("asset_type"))
                    )
                }
            }
        }
        .cardStyle()
    }

    private var catalogItemsCard: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Предметы")
                .font(.headline)
            let rows = model.snapshot?.items ?? []
            if rows.isEmpty {
                Text("Справочник предметов пока не загружен.")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
            } else {
                ForEach(Array(rows.prefix(8).enumerated()), id: \.offset) { _, row in
                    inventoryAssetRow(
                        title: assetDisplayName(row.string("item_id")),
                        subtitle: "\(assetTypeLabel(row.string("item_type"))) · тир \(row.string("tier", default: "1"))",
                        detail: effectLabel(row.string("effect_json")),
                        icon: assetIcon(row.string("item_type"))
                    )
                }
            }
        }
        .cardStyle()
    }

    private var personalCardsCard: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Особые карты")
                .font(.headline)
            let rows = model.snapshot?.cards ?? []
            if rows.isEmpty {
                Text("Карт для передачи влияния пока нет.")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
            } else {
                ForEach(Array(rows.prefix(8).enumerated()), id: \.offset) { _, row in
                    inventoryAssetRow(
                        title: row.string("name").isEmpty ? assetDisplayName(row.string("card_id")) : row.string("name"),
                        subtitle: "тир \(row.string("tier", default: "1"))",
                        detail: conversionRuleLabel(row.string("conversion_rule")),
                        icon: "rectangle.stack"
                    )
                }
            }
        }
        .cardStyle()
    }

    private var potionInventoryCard: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Зелья в сумке")
                .font(.headline)
            if ownedPotions.isEmpty {
                Text("Зелий в сумке пока нет.")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
            } else {
                ForEach(Array(ownedPotions.prefix(8).enumerated()), id: \.offset) { _, row in
                    inventoryAssetRow(
                        title: assetDisplayName(row.string("potion_id")),
                        subtitle: "x\(row.int("quantity", default: 1))",
                        detail: assetEffectLine(row.string("potion_id")),
                        icon: "cross.vial"
                    )
                }
            }
        }
        .cardStyle()
    }

    private var potionCatalogCard: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Справочник зелий")
                .font(.headline)
            let rows = model.snapshot?.potions ?? []
            if rows.isEmpty {
                Text("Справочник зелий пока не загружен.")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
            } else {
                ForEach(Array(rows.prefix(8).enumerated()), id: \.offset) { _, row in
                    inventoryAssetRow(
                        title: assetDisplayName(row.string("potion_id")),
                        subtitle: "\(gwentRarityLabel(row.string("rarity"))) · \(row.string("wholesale_cost"))g",
                        detail: effectLabel(row.string("effect_json")),
                        icon: "cross.vial"
                    )
                }
            }
        }
        .cardStyle()
    }

    private var artifactsCard: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Артефакты")
                .font(.headline)
            let rows = model.snapshot?.artifacts ?? []
            if rows.isEmpty {
                Text("Видимых артефактов нет.")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
            } else {
                ForEach(Array(rows.prefix(8).enumerated()), id: \.offset) { _, row in
                    inventoryAssetRow(
                        title: assetDisplayName(row.string("artifact_id")),
                        subtitle: gwentRarityLabel(row.string("rarity")),
                        detail: artifactHint(row),
                        icon: "sparkles"
                    )
                }
            }
        }
        .cardStyle()
    }

    private var lockedRewardsCard: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Награды на проверке")
                .font(.headline)
            let rows = model.snapshot?.rewardApprovals ?? []
            if rows.isEmpty {
                Text("Нет наград, ожидающих мастера.")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
            } else {
                ForEach(Array(rows.prefix(8).enumerated()), id: \.offset) { _, row in
                    inventoryAssetRow(
                        title: assetDisplayName(row.string("reward_id")),
                        subtitle: orderStatusLabel(row.string("status")),
                        detail: "Пока награда заблокирована: ее нельзя тратить, ставить или передавать.",
                        icon: "lock.shield"
                    )
                }
            }
        }
        .cardStyle()
    }

    private func inventoryAssetRow(title: String, subtitle: String, detail: String, icon: String) -> some View {
        HStack(alignment: .top, spacing: 10) {
            Image(systemName: icon)
                .font(.headline)
                .foregroundStyle(.blue)
                .frame(width: 28, height: 28)
                .background(.blue.opacity(0.1))
                .clipShape(RoundedRectangle(cornerRadius: 8))
            VStack(alignment: .leading, spacing: 3) {
                Text(title)
                    .font(.subheadline.bold())
                if !subtitle.isEmpty {
                    Text(subtitle)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                if !detail.isEmpty {
                    Text(detail)
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                }
            }
            Spacer(minLength: 0)
        }
        .padding(.vertical, 4)
    }

    private func assetDisplayName(_ assetId: String) -> String {
        let knownNames = [
            "mat_herbs": "Травы",
            "mat_silver_dust": "Серебряная пыль",
            "mat_alchemical_salt": "Алхимическая соль",
            "mat_rune_shard": "Рунный осколок",
            "mat_monster_blood": "Кровь чудовища",
            "mat_curse_ash": "Пепел проклятия",
            "mat_light_essence": "Светлая эссенция",
            "mat_old_metal": "Старый металл",
            "item_monster_trophy": "Трофей чудовища",
            "item_beast_fang": "Клык бестии",
            "item_curse_mark": "Метка проклятия",
            "item_order_seal": "Печать заказа",
            "item_tax_list": "Налоговый список",
            "item_secret_writ": "Тайная грамота",
            "item_cache_key": "Ключ от тайника",
            "item_debt_note": "Долговая записка",
            "item_infantry_writ": "Грамота пехоты",
            "item_guard_contract": "Контракт стражи",
            "item_cavalry_writ": "Грамота кавалерии",
            "item_siege_scheme": "Осадная схема",
            "item_secret_passage_map": "Карта тайного хода",
            "item_betrayal_proof": "Доказательство измены",
            "item_gwent_marker": "Ставка Гвинта",
            "item_final_token": "Финальная улика",
            "artifact_silver_chain": "Серебряная цепь",
            "potion_common_swallow": "Ласточка",
            "potion_common_cat": "Кошка",
            "potion_common_white_honey": "Белый мед",
            "potion_uncommon_thunderbolt": "Гром",
            "potion_uncommon_petri": "Фильтр Петри",
            "potion_rare_oriole": "Иволга",
            "potion_rare_black_blood": "Черная кровь",
            "potion_rare_clarity": "Ясность",
            "reward_pve_t1": "Награда за сцену",
            "reward_order_success": "Награда за заказ",
            "pc_infantry_t1": "Благосклонность пехоты",
            "pc_guard_t1": "Контракт стражи"
        ]
        if let name = knownNames[assetId] {
            return name
        }
        return readableIdentifier(assetId, droppingPrefixes: [
            "item_",
            "artifact_",
            "potion_",
            "reward_",
            "card_",
            "pc_",
            "mat_"
        ])
    }

    private func assetStatusLabel(_ status: String) -> String {
        switch status.lowercased() {
        case "active":
            return "активно"
        case "pending_locked", "locked", "pending_master_approval":
            return "заблокировано"
        case "spent":
            return "потрачено"
        default:
            return readableIdentifier(status)
        }
    }

    private func assetIcon(_ type: String) -> String {
        switch type.lowercased() {
        case "artifact":
            return "sparkles"
        case "card", "personal_to_army":
            return "rectangle.stack"
        case "potion":
            return "cross.vial"
        case "material":
            return "shippingbox"
        case "trophy":
            return "rosette"
        case "order_token":
            return "seal"
        case "quest_object":
            return "doc.text"
        case "strategic", "strategic_support":
            return "flag"
        case "final_evidence":
            return "checkmark.seal"
        case "pvp_stake":
            return "suit.club"
        default:
            return "bag"
        }
    }

    private func assetEffectLine(_ assetId: String) -> String {
        if let item = model.snapshot?.items.first(where: { $0.string("item_id") == assetId }) {
            return effectLabel(item.string("effect_json"))
        }
        if let potion = model.snapshot?.potions.first(where: { $0.string("potion_id") == assetId }) {
            return effectLabel(potion.string("effect_json"))
        }
        if let artifact = model.snapshot?.artifacts.first(where: { $0.string("artifact_id") == assetId }) {
            return artifactHint(artifact)
        }
        return ""
    }

    private func effectLabel(_ raw: String) -> String {
        let lower = raw.lowercased()
        if lower.contains("monster_bonus") {
            return "Бонус к охоте на чудовище."
        }
        if lower.contains("lord_influence_claim") {
            return "Доказательство для лордского влияния или сделки."
        }
        if lower.contains("order_completion_proof") {
            return "Подходит как proof для заказа."
        }
        if lower.contains("any_check_modifier_plus_1") {
            return "+1 к одному PvE-чеку."
        }
        if lower.contains("extra_hint") {
            return "Дополнительная подсказка в сцене."
        }
        if lower.contains("clear_minor_hindrance") {
            return "Снимает малую помеху сцены."
        }
        if lower.contains("strength_or_agility_modifier_plus_2") {
            return "+2 к Силе или Ловкости в сцене."
        }
        if lower.contains("mind_will_charisma_modifier_plus_2") {
            return "+2 к Разуму, Воле или Харизме."
        }
        if lower.contains("ignore_poison") {
            return "Игнорирует яд, болото или токсичную помеху."
        }
        if lower.contains("dark_or_cursed_scene_modifier_plus_4") {
            return "+4 в темной или проклятой сцене."
        }
        if lower.contains("reveal_best_scene_stat") {
            return "Показывает лучший стат для сцены."
        }
        if lower.contains("market_only") || lower.contains("sell_to_material_market") {
            return "Материал для продажи рынку."
        }
        if lower.contains("strategic_support") {
            return "Стратегическая поддержка для лордов и заказов."
        }
        if lower.contains("quest_leverage") {
            return "Квестовая улика для сделки или давления."
        }
        if lower.contains("final_evidence") {
            return "Финальная улика для развязки."
        }
        return ""
    }

    private func materialCategoryLabel(_ category: String) -> String {
        switch category.lowercased() {
        case "alchemy":
            return "алхимия"
        case "monster":
            return "чудовища"
        case "arcane":
            return "магия"
        case "dark":
            return "темное"
        case "light":
            return "светлое"
        case "strategic":
            return "стратегия"
        default:
            return readableIdentifier(category)
        }
    }

    private func materialTrendLabel(_ trend: String) -> String {
        switch trend.lowercased() {
        case "scarce":
            return "дефицит"
        case "surplus":
            return "избыток"
        case "balanced", "":
            return "ровно"
        default:
            return readableIdentifier(trend)
        }
    }

    private func materialTrendColor(_ trend: String) -> Color {
        switch trend.lowercased() {
        case "scarce":
            return .orange
        case "surplus":
            return .green
        default:
            return .blue
        }
    }

    private func conversionRuleLabel(_ rule: String) -> String {
        switch rule.lowercased() {
        case "may_transfer_to_lord_once":
            return "Можно один раз передать лорду как поддержку."
        default:
            return readableIdentifier(rule)
        }
    }

    private func artifactHint(_ row: SnapshotRow) -> String {
        let counterplay = row.string("counterplay")
        if counterplay == "can_be_stolen_by_order" {
            return "Может стать целью заказа или кражи."
        }
        return readableIdentifier(row.string("visibility"))
    }

    private var materialMarketSection: some View {
        VStack(alignment: .leading, spacing: 16) {
            VStack(alignment: .leading, spacing: 10) {
                Text("Рынок материалов")
                    .font(.headline)

                if materialMarketRows.isEmpty {
                    Label("Рынок материалов пока не загружен.", systemImage: "chart.line.downtrend.xyaxis")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                } else {
                    ForEach(Array(materialMarketRows.enumerated()), id: \.offset) { _, row in
                        materialMarketRow(row)
                    }
                }
            }
            .cardStyle()

            VStack(alignment: .leading, spacing: 10) {
                Text("Продать рынку")
                    .font(.headline)

                if materialMarketRows.isEmpty {
                    Text("Нет доступных материалов.")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                } else {
                    Picker("Материал", selection: $selectedMarketMaterialId) {
                        ForEach(Array(materialMarketRows.enumerated()), id: \.offset) { _, row in
                            let materialId = row.string("material_id")
                            Text(assetDisplayName(materialId)).tag(materialId)
                        }
                    }
                    .pickerStyle(.menu)

                    let available = selectedMarketMaterialQuantity
                    let price = selectedMaterialMarket.map(materialMarketPrice) ?? 0
                    HStack {
                        Label("В сумке: \(available)", systemImage: "shippingbox")
                        Spacer()
                        Text("\(price)g / шт.")
                            .font(.caption.monospacedDigit().bold())
                            .foregroundStyle(.secondary)
                    }
                    .font(.caption)

                    Stepper("Количество: \(materialSellQuantity)", value: $materialSellQuantity, in: 1...max(1, available))
                        .disabled(available <= 0)

                    Button {
                        Task {
                            await model.sellMaterial(
                                materialId: selectedMarketMaterialId,
                                quantity: min(materialSellQuantity, max(1, available))
                            )
                        }
                    } label: {
                        Label("Продать за \(price * min(materialSellQuantity, max(1, available)))g", systemImage: "banknote")
                            .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.borderedProminent)
                    .disabled(!canSellSelectedMaterial)
                }
            }
            .cardStyle()

            if canUsePotionMarket {
                potionMarketSection
            }

            cardMarketSection
        }
        .onAppear {
            normalizeMaterialMarketDefaults()
        }
        .onChange(of: model.snapshot?.snapshotVersion ?? "") { _ in
            normalizeMaterialMarketDefaults()
        }
    }

    private func materialMarketRow(_ row: SnapshotRow) -> some View {
        HStack(alignment: .top, spacing: 10) {
            Image(systemName: assetIcon("material"))
                .font(.headline)
                .foregroundStyle(materialTrendColor(row.string("trend")))
                .frame(width: 28, height: 28)
                .background(materialTrendColor(row.string("trend")).opacity(0.12))
                .clipShape(RoundedRectangle(cornerRadius: 8))
            VStack(alignment: .leading, spacing: 3) {
                HStack(alignment: .firstTextBaseline) {
                    Text(assetDisplayName(row.string("material_id")))
                        .font(.subheadline.bold())
                    Spacer()
                    Text("\(materialMarketPrice(row))g")
                        .font(.caption.monospacedDigit().bold())
                        .foregroundStyle(materialTrendColor(row.string("trend")))
                }
                Text("\(materialCategoryLabel(row.string("category"))) · \(materialTrendLabel(row.string("trend")))")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                let description = row.string("description")
                if !description.isEmpty {
                    Text(description)
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                }
            }
        }
        .padding(.vertical, 4)
    }

    private var potionMarketSection: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Зелья")
                .font(.headline)

            if potionMarketRows.isEmpty {
                Text("Зелья сейчас разобраны.")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
            } else {
                ForEach(Array(potionMarketRows.prefix(8).enumerated()), id: \.offset) { _, row in
                    potionMarketOfferRow(row)
                }
            }
        }
        .cardStyle()
    }

    private func potionMarketOfferRow(_ row: SnapshotRow) -> some View {
        let potionId = row.string("potion_id")
        let stock = row.int("stock")
        let cost = row.int("wholesale_cost")

        return HStack(alignment: .top, spacing: 10) {
            Image(systemName: "cross.vial")
                .font(.headline)
                .foregroundStyle(.purple)
                .frame(width: 28, height: 28)
                .background(.purple.opacity(0.12))
                .clipShape(RoundedRectangle(cornerRadius: 8))
            VStack(alignment: .leading, spacing: 3) {
                Text(assetDisplayName(potionId))
                    .font(.subheadline.bold())
                Text("\(gwentRarityLabel(row.string("rarity"))) · \(stock) шт.")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                Text(assetEffectLine(potionId))
                    .font(.caption2)
                    .foregroundStyle(.secondary)
            }
            Spacer(minLength: 8)
            Button {
                Task { await model.buyPotion(potionId: potionId, quantity: 1) }
            } label: {
                Text("\(cost)g")
                    .font(.caption.bold())
                    .monospacedDigit()
            }
            .buttonStyle(.borderedProminent)
            .disabled(stock <= 0 || cost <= 0)
        }
        .padding(.vertical, 4)
    }

    private var cardMarketSection: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Карты")
                .font(.headline)

            if cardMarketRows.isEmpty {
                Text("Подходящих карт в продаже нет.")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
            } else {
                ForEach(Array(cardMarketRows.prefix(10).enumerated()), id: \.offset) { _, row in
                    cardMarketOfferRow(row)
                }
            }
        }
        .cardStyle()
    }

    private func cardMarketOfferRow(_ row: SnapshotRow) -> some View {
        let cardId = row.string("card_id")
        let cost = row.int("unit_cost")

        return HStack(alignment: .top, spacing: 10) {
            Image(systemName: "rectangle.stack")
                .font(.headline)
                .foregroundStyle(.orange)
                .frame(width: 28, height: 28)
                .background(.orange.opacity(0.12))
                .clipShape(RoundedRectangle(cornerRadius: 8))
            VStack(alignment: .leading, spacing: 3) {
                Text(gwentCardTitle(cardId))
                    .font(.subheadline.bold())
                Text("\(gwentFactionLabel(row.string("faction"))) · \(gwentRowLabel(row.string("row"))) · сила \(row.int("strength"))")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                let effectText = row.string("effect_text")
                Text(effectText.isEmpty ? gwentEffectLabel(row.string("effect")) : effectText)
                    .font(.caption2)
                    .foregroundStyle(.secondary)
            }
            Spacer(minLength: 8)
            Button {
                Task { await model.buyMarketCard(cardId: cardId) }
            } label: {
                Text("\(cost)g")
                    .font(.caption.bold())
                    .monospacedDigit()
            }
            .buttonStyle(.borderedProminent)
            .disabled(cost <= 0)
        }
        .padding(.vertical, 4)
    }

    private var tradeSection: some View {
        VStack(alignment: .leading, spacing: 16) {
            VStack(alignment: .leading, spacing: 10) {
                Text("Передать вещь")
                    .font(.headline)

                if tradeRecipients.isEmpty {
                    Label("Нет доступных игроков для обмена.", systemImage: "person.crop.circle.badge.exclamationmark")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                } else {
                    Picker("Кому", selection: $tradeRecipient) {
                        ForEach(tradeRecipients) { player in
                            Text(player.displayName).tag(player.playerId)
                        }
                    }
                    .pickerStyle(.menu)
                }

                if transferableAssets.isEmpty {
                    Label("Нет активных вещей для передачи.", systemImage: "bag.badge.minus")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                } else {
                    Picker("Что передать", selection: tradeAssetSelection) {
                        ForEach(transferableAssets) { option in
                            Text(option.title).tag(option.id)
                        }
                    }
                    .pickerStyle(.menu)

                    if let selected = selectedTransferAsset {
                        Label(selected.detail, systemImage: assetIcon(selected.assetType))
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }

                Stepper("Количество: \(tradeQuantity)", value: $tradeQuantity, in: 1...max(1, selectedTransferAsset?.quantity ?? 1))
                Stepper("Цена: \(tradePriceGold)g", value: $tradePriceGold, in: 0...999)
                Picker("Режим", selection: $tradeMode) {
                    Text("Подарок").tag("gift")
                    Text("Продажа").tag("sell")
                    Text("Обмен").tag("exchange")
                }
                .pickerStyle(.segmented)
                Button {
                    Task {
                        guard let selected = selectedTransferAsset else { return }
                        await model.createTradeTransfer(
                            toPlayerId: tradeRecipient,
                            assetType: selected.assetType,
                            assetId: selected.assetId,
                            quantity: min(tradeQuantity, selected.quantity),
                            priceGold: tradePriceGold,
                            mode: tradeMode
                        )
                    }
                } label: {
                    Label("Создать передачу", systemImage: "paperplane")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent)
                .disabled(!canCreateTradeTransfer)
            }
            .cardStyle()

            VStack(alignment: .leading, spacing: 10) {
                Text("Входящие передачи")
                    .font(.headline)
                if incomingTradeTransfers.isEmpty {
                    Text("Входящих передач пока нет.")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                } else {
                    ForEach(Array(incomingTradeTransfers.prefix(6).enumerated()), id: \.offset) { _, row in
                        tradeTransferRow(row, incoming: true)
                    }
                }
            }
            .cardStyle()

            VStack(alignment: .leading, spacing: 10) {
                Text("Исходящие и история")
                    .font(.headline)
                let rows = outgoingTradeTransfers + completedTradeTransfers
                if rows.isEmpty {
                    Text("Истории обмена пока нет.")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                } else {
                    ForEach(Array(rows.prefix(8).enumerated()), id: \.offset) { _, row in
                        tradeTransferRow(row, incoming: false)
                    }
                }
            }
            .cardStyle()

        }
        .onAppear {
            normalizeTradeDefaults()
        }
        .onChange(of: model.snapshot?.snapshotVersion ?? "") { _ in
            normalizeTradeDefaults()
        }
    }

    private var tradeRecipients: [PlayerProfile] {
        guard let player = model.player else { return [] }
        return (model.snapshot?.players ?? [])
            .filter { $0.playerId != player.playerId }
            .sorted { lhs, rhs in
                if lhs.roleType == rhs.roleType {
                    return lhs.displayName < rhs.displayName
                }
                return roleLabel(lhs.roleType) < roleLabel(rhs.roleType)
            }
    }

    private var transferableAssets: [TransferAssetOption] {
        let assetOptions = ownedAssets.compactMap(transferAssetOption)
        let potionOptions = ownedPotions.compactMap(transferPotionOption)
        return (assetOptions + potionOptions).sorted { lhs, rhs in
            if lhs.assetType == rhs.assetType {
                return lhs.title < rhs.title
            }
            return assetTypeLabel(lhs.assetType) < assetTypeLabel(rhs.assetType)
        }
    }

    private var selectedTransferAsset: TransferAssetOption? {
        transferableAssets.first { $0.id == selectedTradeAssetKey }
    }

    private var canCreateTradeTransfer: Bool {
        tradeRecipients.contains { $0.playerId == tradeRecipient } && selectedTransferAsset != nil
    }

    private var tradeAssetSelection: Binding<String> {
        Binding(
            get: { selectedTradeAssetKey },
            set: { applyTradeAssetSelection($0) }
        )
    }

    private func applyTradeAssetSelection(_ selection: String) {
        selectedTradeAssetKey = selection
        let parts = selection.split(separator: "|", maxSplits: 1).map(String.init)
        guard parts.count == 2 else { return }
        tradeAssetType = parts[0]
        tradeAssetId = parts[1]
        if let selected = selectedTransferAsset {
            tradeQuantity = min(max(1, tradeQuantity), selected.quantity)
        }
    }

    private func normalizeTradeDefaults() {
        let recipients = tradeRecipients
        if !recipients.contains(where: { $0.playerId == tradeRecipient }) {
            tradeRecipient = recipients.first?.playerId ?? ""
        }

        let assets = transferableAssets
        if !assets.contains(where: { $0.id == selectedTradeAssetKey }) {
            if let first = assets.first {
                applyTradeAssetSelection(first.id)
            } else {
                selectedTradeAssetKey = ""
                tradeAssetId = ""
            }
        }
        if let selected = selectedTransferAsset {
            tradeQuantity = min(max(1, tradeQuantity), selected.quantity)
        } else {
            tradeQuantity = 1
        }
    }

    private func transferAssetOption(_ row: SnapshotRow) -> TransferAssetOption? {
        guard let player = model.player,
              row.string("owner_player_id") == player.playerId
        else { return nil }

        let assetType = row.string("asset_type").lowercased()
        let assetId = row.string("asset_id")
        let status = row.string("status", default: "active").lowercased()
        let quantity = row.int("quantity", default: 1)
        guard !assetId.isEmpty,
              quantity > 0,
              ["item", "artifact", "card"].contains(assetType),
              ["active", "available"].contains(status)
        else { return nil }

        return TransferAssetOption(
            assetType: assetType,
            assetId: assetId,
            quantity: quantity,
            title: assetDisplayName(assetId),
            detail: "\(assetTypeLabel(assetType)) · x\(quantity)"
        )
    }

    private func transferPotionOption(_ row: SnapshotRow) -> TransferAssetOption? {
        guard let player = model.player,
              row.string("player_id") == player.playerId
        else { return nil }

        let potionId = row.string("potion_id")
        let quantity = row.int("quantity", default: 1)
        guard !potionId.isEmpty, quantity > 0 else { return nil }

        return TransferAssetOption(
            assetType: "potion",
            assetId: potionId,
            quantity: quantity,
            title: assetDisplayName(potionId),
            detail: "зелье · x\(quantity)"
        )
    }

    private var incomingTradeTransfers: [SnapshotRow] {
        guard let playerId = model.player?.playerId else { return [] }
        return model.snapshot?.tradeTransfers.filter {
            $0.string("to_player_id") == playerId && isOpenTradeStatus($0.string("status"))
        } ?? []
    }

    private var outgoingTradeTransfers: [SnapshotRow] {
        guard let playerId = model.player?.playerId else { return [] }
        return model.snapshot?.tradeTransfers.filter {
            $0.string("from_player_id") == playerId && isOpenTradeStatus($0.string("status"))
        } ?? []
    }

    private var completedTradeTransfers: [SnapshotRow] {
        guard let playerId = model.player?.playerId else { return [] }
        return model.snapshot?.tradeTransfers.filter {
            ($0.string("from_player_id") == playerId || $0.string("to_player_id") == playerId)
                && !isOpenTradeStatus($0.string("status"))
        } ?? []
    }

    private func tradeTransferRow(_ row: SnapshotRow, incoming: Bool) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack(alignment: .firstTextBaseline) {
                Text(tradeTransferParties(row))
                    .font(.subheadline.bold())
                Spacer()
                Text(tradeStatusLabel(row.string("status")))
                    .font(.caption.bold())
                    .foregroundStyle(isOpenTradeStatus(row.string("status")) ? .orange : .secondary)
            }

            Text(tradeTransferDetail(row, incoming: incoming))
                .font(.caption)
                .foregroundStyle(.secondary)

            if incoming && isOpenTradeStatus(row.string("status")) {
                HStack {
                    Button {
                        Task { await model.acceptTradeTransfer(id: row.string("transfer_id")) }
                    } label: {
                        Label("Принять", systemImage: "checkmark.circle")
                            .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.borderedProminent)

                    Button {
                        Task {
                            await model.declineTradeTransfer(id: row.string("transfer_id"), reason: tradeDeclineReason)
                        }
                    } label: {
                        Label("Отклонить", systemImage: "xmark.circle")
                            .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.bordered)
                }
            }
        }
        .padding(.vertical, 4)
    }

    private func tradeTransferDetail(_ row: SnapshotRow, incoming: Bool) -> String {
        let quantity = max(1, row.int("quantity", default: 1))
        let price = row.int("price_gold")
        var parts = ["\(assetDisplayName(row.string("asset_id"))) x\(quantity)"]
        if price > 0 {
            parts.append("за \(price)g")
        }
        return parts.joined(separator: " · ")
    }

    private func tradeTransferParties(_ row: SnapshotRow) -> String {
        "\(playerName(row.string("from_player_id"))) -> \(playerName(row.string("to_player_id")))"
    }

    private func isOpenTradeStatus(_ status: String) -> Bool {
        ["pending", "pending_locked", "created"].contains(status.lowercased())
    }

    private func tradeStatusLabel(_ status: String) -> String {
        switch status.lowercased() {
        case "pending", "pending_locked", "created":
            return "ожидает"
        case "accepted", "completed":
            return "принято"
        case "declined", "rejected", "cancelled":
            return "отклонено"
        default:
            return readableIdentifier(status)
        }
    }

    private func tradeModeLabel(_ mode: String) -> String {
        switch mode.lowercased() {
        case "gift":
            return "подарок"
        case "sell":
            return "продажа"
        case "exchange":
            return "обмен"
        default:
            return readableIdentifier(mode)
        }
    }

    private func playerName(_ playerId: String) -> String {
        if let current = model.player, current.playerId == playerId {
            return current.displayName
        }
        if let player = model.snapshot?.players.first(where: { $0.playerId == playerId }) {
            return player.displayName
        }
        return readableIdentifier(playerId, droppingPrefixes: ["p_"])
    }

    private var qr: some View {
        QRScannerFlowView()
    }

    private var orders: some View {
        NavigationStack {
            List {
                if let snapshot = model.snapshot, !snapshot.orders.isEmpty {
                    ForEach(snapshot.orders) { order in
                        VStack(alignment: .leading, spacing: 8) {
                            HStack {
                                Text(orderTitle(order))
                                    .font(.headline)
                                Spacer()
                                Text(orderStatusLabel(order.status))
                                    .font(.caption.bold())
                                    .padding(.horizontal, 8)
                                    .padding(.vertical, 4)
                                    .background(orderStatusColor(order.status).opacity(0.14))
                                    .foregroundStyle(orderStatusColor(order.status))
                                    .clipShape(Capsule())
                            }

                            if let missionBrief = orderMissionBrief(order) {
                                Text(missionBrief)
                                    .font(.subheadline)
                                    .foregroundStyle(.primary.opacity(0.86))
                                    .fixedSize(horizontal: false, vertical: true)
                            }

                            Label(orderRewardText(order), systemImage: "seal.fill")
                                .font(.footnote.weight(.semibold))
                                .foregroundStyle(.orange)

                            if let location = orderLocationText(order) {
                                Text(location)
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                            }

                            if let progressHint = orderProgressHint(order) {
                                Text(progressHint)
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                            }

                            HStack {
                                orderActionButton(title: "Взять", icon: "hand.raised") {
                                    Task { await model.acceptOrder(order) }
                                }
                                .buttonStyle(.borderedProminent)
                                .disabled(!order.isAcceptable)

                                orderActionButton(title: "QR", icon: "qrcode.viewfinder") {
                                    showQR = true
                                }
                                .buttonStyle(.bordered)
                                .disabled(!order.isSubmittable)

                                orderActionButton(title: "Сдать", icon: "tray.and.arrow.up") {
                                    Task { await model.submitOrder(order) }
                                }
                                .buttonStyle(.bordered)
                                .disabled(!order.isSubmittable || localOrderProof(order) == nil)
                            }
                        }
                        .padding(.vertical, 6)
                    }
                } else {
                    Text("Видимых заказов пока нет.")
                        .foregroundStyle(.secondary)
                }
            }
            .navigationTitle("Заказы")
            .toolbar {
                Button("Обновить") { Task { await model.refreshSnapshot() } }
            }
        }
    }

    private func orderActionButton(title: String, icon: String, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            VStack(spacing: 3) {
                Image(systemName: icon)
                    .font(.headline)
                Text(title)
                    .font(.caption.bold())
                    .lineLimit(1)
                    .minimumScaleFactor(0.8)
            }
            .frame(maxWidth: .infinity, minHeight: 52)
        }
        .accessibilityLabel(title)
    }

    private func orderTitle(_ order: OrderSummary) -> String {
        let label = order.objectLabel.trimmingCharacters(in: .whitespacesAndNewlines)
        if !label.isEmpty,
           label != order.objectId,
           !label.lowercased().hasPrefix("interest_") {
            return label
        }
        if let scenario = orderScenario(order), let text = scenario.missionText, !text.isEmpty {
            return firstSentence(text)
        }
        return readableIdentifier(order.objectId, droppingPrefixes: ["qr_", "order_", "interest_"])
    }

    private func orderStatusLabel(_ status: String) -> String {
        switch status.lowercased() {
        case "published":
            return "доступен"
        case "addressed_pending":
            return "адресный"
        case "accepted", "in_progress", "claimed_at_prop":
            return "в работе"
        case "submitted_pending_sync":
            return "ждет связи"
        case "pending_master_approval":
            return "у мастера"
        case "completed", "resolved", "rewarded":
            return "закрыт"
        case "failed_retryable":
            return "повторить"
        case "needs_master_review":
            return "проверка"
        default:
            return readableIdentifier(status)
        }
    }

    private func orderStatusColor(_ status: String) -> Color {
        switch status.lowercased() {
        case "published", "addressed_pending", "failed_retryable":
            return .blue
        case "accepted", "in_progress", "claimed_at_prop":
            return .orange
        case "submitted_pending_sync", "pending_master_approval":
            return .purple
        case "completed", "resolved", "rewarded":
            return .green
        case "needs_master_review":
            return .red
        default:
            return .secondary
        }
    }

    private func orderVisibilityLabel(_ visibility: String) -> String {
        switch visibility.lowercased() {
        case "public":
            return "публичный заказ"
        case "addressed":
            return "личный заказ"
        default:
            return readableIdentifier(visibility)
        }
    }

    private func orderObjectTypeLabel(_ objectType: String) -> String {
        switch objectType.lowercased() {
        case "qr_object", "qr":
            return "QR-объект"
        case "territory":
            return "территория"
        case "artifact":
            return "артефакт"
        case "card":
            return "карта"
        default:
            return readableIdentifier(objectType)
        }
    }

    private func orderMissionBrief(_ order: OrderSummary) -> String? {
        let hook = order.visibleHook.trimmingCharacters(in: .whitespacesAndNewlines)
        if !hook.isEmpty {
            return hook
        }
        if let scenario = orderScenario(order), let text = scenario.missionText, !text.isEmpty {
            return text
        }
        return nil
    }

    private func orderRewardText(_ order: OrderSummary) -> String {
        let label = order.rewardLabel.trimmingCharacters(in: .whitespacesAndNewlines)
        if !label.isEmpty {
            return "Награда: \(label)"
        }
        if order.rewardGold > 0 || order.rewardXP > 0 {
            var parts: [String] = []
            if order.rewardGold > 0 {
                parts.append("\(order.rewardGold) золота")
            }
            if order.rewardXP > 0 {
                parts.append("\(order.rewardXP) опыта")
            }
            return "Награда: \(parts.joined(separator: ", "))"
        }
        if let reward = model.snapshot?.rewards.first(where: { $0.rewardId == order.escrowRewardId }) {
            var parts: [String] = []
            if reward.gold > 0 {
                parts.append("\(reward.gold) золота")
            }
            if reward.xp > 0 {
                parts.append("\(reward.xp) опыта")
            }
            if !parts.isEmpty {
                return "Награда: \(parts.joined(separator: ", "))"
            }
        }
        return "Награда указана лордом"
    }

    private func orderLocationText(_ order: OrderSummary) -> String? {
        let location = order.locationLabel.trimmingCharacters(in: .whitespacesAndNewlines)
        if !location.isEmpty, location != order.objectLabel {
            return "Место: \(location)"
        }
        return nil
    }

    private func orderScenario(_ order: OrderSummary) -> PVEScenario? {
        guard let snapshot = model.snapshot else { return nil }
        let scenarioId = order.scenarioId.trimmingCharacters(in: .whitespacesAndNewlines)
        if !scenarioId.isEmpty,
           let scenario = snapshot.pveScenarios.first(where: { $0.scenarioId == scenarioId }) {
            return scenario
        }
        let proofQrIds = Set([order.objectId, order.effectiveProofQrId].filter { !$0.isEmpty })
        guard let qr = snapshot.qrObjects.first(where: {
            proofQrIds.contains($0.qrId) || proofQrIds.contains($0.manualCode)
        }) else { return nil }
        return snapshot.pveScenarios.first(where: { $0.scenarioId == qr.scenarioId })
    }

    private func firstSentence(_ text: String) -> String {
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard let end = trimmed.firstIndex(where: { ".!?".contains($0) }) else {
            return trimmed
        }
        return String(trimmed[...end])
    }

    private func orderProgressHint(_ order: OrderSummary) -> String? {
        if hasQueuedOrderSubmission(order) {
            return "Сдача уже сохранена на телефоне. Вернись в Wi-Fi и отправь события."
        }
        if localOrderProof(order) != nil {
            return "Подтверждение найдено на телефоне. Можно сдать заказ."
        }
        if order.isSubmittable {
            return "После прохождения QR/PvE можно сдать заказ здесь."
        }
        return nil
    }

    private func localOrderProof(_ order: OrderSummary) -> QueuedEvent? {
        let proofQrIds = Set([order.objectId, order.effectiveProofQrId].filter { !$0.isEmpty })
        return model.pendingEvents.last { event in
            event.eventType == "pve_completed"
                && proofQrIds.contains(event.payload.string("qr_id"))
                && event.playerId == model.player?.playerId
        }
    }

    private func hasQueuedOrderSubmission(_ order: OrderSummary) -> Bool {
        model.pendingEvents.contains { event in
            event.eventType == "order_submission"
                && event.payload.string("order_id") == order.orderId
        }
    }

    private var pvp: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    gwentChallengeCard
                    gwentStatusNotice
                    gwentTableLauncher
                    gwentActionCard
                    pvpTablesCard
                }
                .padding()
            }
            .navigationTitle("PvP")
            .toolbar {
                Button("Обновить") { Task { await model.refreshPvpTables() } }
            }
            .task {
                await model.refreshPvpTables()
            }
        }
    }

    private var deckSetup: some View {
        NavigationStack {
            GeometryReader { proxy in
                let compact = proxy.size.width < 410

                ZStack {
                    deckScreenBackground
                        .ignoresSafeArea()

                    ScrollView {
                        VStack(alignment: .leading, spacing: compact ? 12 : 14) {
                            deckHeaderPanel(compact: compact)

                            if deckMode == .builder, let deck = draftGwentDeck {
                                deckSaveButton(deck, compact: compact)
                            }

                            Picker("Раздел", selection: $deckMode) {
                                ForEach(DeckSetupMode.allCases) { mode in
                                    Text(mode.title).tag(mode)
                                }
                            }
                            .pickerStyle(.segmented)
                            .tint(.orange)

                            switch deckMode {
                            case .builder:
                                deckBuilderPanel(compact: compact)
                            case .encyclopedia:
                                deckEncyclopediaPanel(compact: compact)
                            case .mechanics:
                                deckMechanicsPanel(compact: compact)
                            }
                        }
                        .padding(.horizontal, compact ? 12 : 16)
                        .padding(.top, 10)
                        .padding(.bottom, 24)
                    }
                }
            }
            .navigationTitle("Колода")
            .toolbarBackground(.visible, for: .navigationBar)
            .toolbarColorScheme(.dark, for: .navigationBar)
            .toolbar {
                Button("Обновить") { Task { await model.refreshPvpTables() } }
            }
            .confirmationDialog(
                "Убрать карту из колоды?",
                isPresented: deckRemovalConfirmationBinding,
                titleVisibility: .visible
            ) {
                Button("Убрать", role: .destructive) {
                    confirmDeckCardRemoval()
                }
                Button("Отмена", role: .cancel) {
                    pendingDeckRemovalCardId = ""
                }
            } message: {
                Text(deckRemovalConfirmationMessage)
            }
            .onAppear {
                syncDeckDraftIfNeeded(force: true)
                applyDeckScreenshotArgumentsIfNeeded()
            }
            .onChange(of: model.snapshot?.snapshotVersion ?? "") { _ in
                syncDeckDraftIfNeeded(force: true)
                applyDeckScreenshotArgumentsIfNeeded()
            }
            .onChange(of: model.runtimeGwentDecks.map(\.deckId).joined(separator: "|")) { _ in
                syncDeckDraftIfNeeded(force: true)
                applyDeckScreenshotArgumentsIfNeeded()
            }
        }
    }

    private var deckScreenBackground: some View {
        ZStack {
            Color(red: 0.035, green: 0.031, blue: 0.026)
            LinearGradient(
                colors: [
                    Color(red: 0.19, green: 0.12, blue: 0.055).opacity(0.84),
                    Color(red: 0.035, green: 0.05, blue: 0.04),
                    Color.black.opacity(0.96)
                ],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
            RadialGradient(
                colors: [
                    Color(red: 0.88, green: 0.45, blue: 0.16).opacity(0.24),
                    Color.clear
                ],
                center: .topTrailing,
                startRadius: 10,
                endRadius: 340
            )
            RadialGradient(
                colors: [
                    Color(red: 0.12, green: 0.34, blue: 0.26).opacity(0.24),
                    Color.clear
                ],
                center: .bottomLeading,
                startRadius: 20,
                endRadius: 360
            )
        }
    }

    private func deckHeaderPanel(compact: Bool) -> some View {
        let deck = draftGwentDeck
        let metrics = gwentDeckMetrics(cardIds: deckDraftCardIds)
        let warnings = gwentDeckWarnings(metrics)
        let availableCount = deckAvailableCards.count

        return VStack(alignment: .leading, spacing: compact ? 10 : 12) {
            HStack(alignment: .top, spacing: 10) {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Настройка колоды")
                        .font(compact ? .title2.bold() : .title.bold())
                        .foregroundStyle(.white)
                    Text(deck.map { gwentDeckTitle($0) } ?? "Колода не найдена")
                        .font(.caption.bold())
                        .foregroundStyle(.orange.opacity(0.86))
                        .lineLimit(1)
                        .minimumScaleFactor(0.74)
                }
                Spacer(minLength: 8)
                VStack(alignment: .trailing, spacing: 3) {
                    Text("\(availableCount)")
                        .font(.title2.monospacedDigit().bold())
                        .foregroundStyle(.green)
                    Text("доступно")
                        .font(.caption2.bold())
                        .foregroundStyle(.white.opacity(0.62))
                }
                .padding(.horizontal, 10)
                .padding(.vertical, 7)
                .background(.black.opacity(0.34))
                .clipShape(RoundedRectangle(cornerRadius: 6))
            }

            HStack(spacing: 7) {
                deckMetricSeal(title: "Отряды", value: "\(metrics.units)/\(gwentDeckMinUnitCards)+", ok: metrics.units >= gwentDeckMinUnitCards)
                deckMetricSeal(title: "Особые", value: "\(metrics.specials)/\(gwentDeckSpecialCardLimit)", ok: metrics.specials <= gwentDeckSpecialCardLimit)
                deckMetricSeal(title: "Герои", value: "\(metrics.heroes)", ok: true)
            }

            if !warnings.isEmpty {
                VStack(alignment: .leading, spacing: 4) {
                    ForEach(warnings, id: \.self) { warning in
                        Label(warning, systemImage: "exclamationmark.triangle.fill")
                            .font(.caption.bold())
                            .foregroundStyle(.orange)
                            .lineLimit(2)
                    }
                }
            }
        }
        .padding(compact ? 12 : 14)
        .background(deckPanelBackground)
        .overlay(deckPanelStroke)
        .clipShape(RoundedRectangle(cornerRadius: 8))
    }

    private func deckSaveButton(_ deck: GwentDeck, compact: Bool) -> some View {
        let warnings = gwentDeckWarnings(gwentDeckMetrics(cardIds: deckDraftCardIds))

        return Button {
            Task {
                await saveDeckDraft(deck)
            }
        } label: {
            Label(isSavingDeckDraft ? "Сохраняю..." : "Сохранить колоду", systemImage: "square.and.arrow.down")
                .font(compact ? .headline : .title3.bold())
                .frame(maxWidth: .infinity, minHeight: compact ? 42 : 46)
        }
        .buttonStyle(.borderedProminent)
        .tint(warnings.isEmpty ? .green : .orange)
        .disabled(isSavingDeckDraft || !warnings.isEmpty)
    }

    private func deckBuilderPanel(compact: Bool) -> some View {
        return VStack(alignment: .leading, spacing: compact ? 12 : 14) {
            if let snapshot = model.snapshot, let deck = draftGwentDeck {
                let leader = gwentCardMeta(deck.leaderCardId) ?? snapshot.gwentCards.first { $0.cardId == deck.leaderCardId }
                let faction = gwentDeckFaction(deck)

                HStack(alignment: .top, spacing: compact ? 10 : 12) {
                    if let leader {
                        Button {
                            selectedDeckCardId = leader.cardId
                        } label: {
                            gwentCardView(
                                leader,
                                selected: selectedDeckCardId == leader.cardId,
                                inDeck: true,
                                compact: compact,
                                large: true
                            )
                        }
                        .buttonStyle(.plain)
                    }

                    VStack(alignment: .leading, spacing: 8) {
                        Text("Лидер")
                            .font(.headline)
                            .foregroundStyle(.white)
                        Text(gwentFactionLabel(faction))
                            .font(.caption.bold())
                            .foregroundStyle(.yellow.opacity(0.88))
                        if let leader {
                            Text("Способность: \(gwentLeaderAbilityText(leader))")
                                .font(.caption)
                                .foregroundStyle(.white.opacity(0.76))
                                .fixedSize(horizontal: false, vertical: true)
                        }
                        Text("Бонус фракции: \(gwentFactionAbilityLabel(faction))")
                            .font(.caption)
                            .foregroundStyle(.white.opacity(0.58))
                            .fixedSize(horizontal: false, vertical: true)
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                }

                leaderComparisonList(deck: deck, compact: compact)
                deckSelectedStrip(compact: compact)
                deckFilterControls
                cardCollectionGrid(cards: filteredDeckCards, compact: compact, allowsEditing: true)
            } else {
                emptyDeckState
            }
        }
        .padding(compact ? 12 : 14)
        .background(deckPanelBackground)
        .overlay(deckPanelStroke)
        .clipShape(RoundedRectangle(cornerRadius: 8))
    }

    private func deckEncyclopediaPanel(compact: Bool) -> some View {
        let cards = filteredEncyclopediaCards
        let selected = selectedEncyclopediaCard(in: cards)

        return VStack(alignment: .leading, spacing: compact ? 12 : 14) {
            Picker("Карты энциклопедии", selection: $deckEncyclopediaScope) {
                ForEach(DeckEncyclopediaScope.allCases) { scope in
                    Text(scope.title).tag(scope)
                }
            }
            .pickerStyle(.segmented)
            .tint(.orange)

            rowFilterControl
            strengthFilterControl

            if let selected {
                deckCardInspector(selected, compact: compact)
            }

            if cards.isEmpty {
                Text(deckEncyclopediaScope.emptyMessage)
                    .font(.caption)
                    .foregroundStyle(.white.opacity(0.58))
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.vertical, 14)
            } else {
                cardCollectionGrid(
                    cards: cards,
                    compact: compact,
                    allowsEditing: false,
                    selectedCardId: selected?.cardId
                )
            }
        }
        .padding(compact ? 12 : 14)
        .background(deckPanelBackground)
        .overlay(deckPanelStroke)
        .clipShape(RoundedRectangle(cornerRadius: 8))
    }

    private func deckMechanicsPanel(compact: Bool) -> some View {
        VStack(alignment: .leading, spacing: compact ? 14 : 16) {
            VStack(alignment: .leading, spacing: 4) {
                Text("Типы и ряды")
                    .font(.headline)
                    .foregroundStyle(.white)
                Text("Эти знаки показывают, куда карта играется и чем она отличается от обычного отряда.")
                    .font(.caption)
                    .foregroundStyle(.white.opacity(0.62))
                    .fixedSize(horizontal: false, vertical: true)
            }

            VStack(spacing: 8) {
                ForEach(gwentTypeMechanics) { mechanic in
                    gwentMechanicRow(mechanic, compact: compact)
                }
            }

            VStack(alignment: .leading, spacing: 4) {
                Text("Способности")
                    .font(.headline)
                    .foregroundStyle(.white)
                Text("Такие значки появляются на самих картах и в подробностях энциклопедии.")
                    .font(.caption)
                    .foregroundStyle(.white.opacity(0.62))
                    .fixedSize(horizontal: false, vertical: true)
            }

            VStack(spacing: 8) {
                ForEach(gwentAbilityMechanics) { mechanic in
                    gwentMechanicRow(mechanic, compact: compact)
                }
            }
        }
        .padding(compact ? 12 : 14)
        .background(deckPanelBackground)
        .overlay(deckPanelStroke)
        .clipShape(RoundedRectangle(cornerRadius: 8))
    }

    private func gwentMechanicRow(_ mechanic: GwentMechanicInfo, compact: Bool) -> some View {
        HStack(alignment: .top, spacing: compact ? 9 : 11) {
            Image(systemName: mechanic.icon)
                .font(.system(size: compact ? 14 : 16, weight: .black))
                .foregroundStyle(.white)
                .frame(width: compact ? 32 : 36, height: compact ? 32 : 36)
                .background(mechanic.color.opacity(0.84))
                .clipShape(RoundedRectangle(cornerRadius: 7))
                .overlay(
                    RoundedRectangle(cornerRadius: 7)
                        .stroke(.white.opacity(0.14), lineWidth: 1)
                )
            VStack(alignment: .leading, spacing: 3) {
                Text(mechanic.title)
                    .font(.caption.bold())
                    .foregroundStyle(.white)
                Text(mechanic.detail)
                    .font(.caption2)
                    .foregroundStyle(.white.opacity(0.64))
                    .fixedSize(horizontal: false, vertical: true)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .padding(8)
        .background(.black.opacity(0.22))
        .clipShape(RoundedRectangle(cornerRadius: 8))
    }

    private var gwentTableLauncher: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 12) {
                Image(systemName: "iphone.landscape")
                    .font(.title2.bold())
                    .frame(width: 42, height: 42)
                    .background(.yellow.opacity(0.18))
                    .clipShape(RoundedRectangle(cornerRadius: 8))
                VStack(alignment: .leading, spacing: 3) {
                    Text("Открыть игровой стол")
                        .font(.headline)
                    Text("Вернуться в уже начатую партию, если кто-то вышел с экрана или перезапустил приложение.")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                        .fixedSize(horizontal: false, vertical: true)
                }
                Spacer(minLength: 0)
            }

            Button {
                showGwentTable = true
            } label: {
                Label("Открыть стол", systemImage: "rectangle.stack.badge.play")
                    .frame(maxWidth: .infinity)
            }
            .buttonStyle(.borderedProminent)
        }
        .cardStyle()
    }

    @ViewBuilder
    private var gwentStatusNotice: some View {
        if let error = model.errorMessage {
            Label(error, systemImage: "exclamationmark.triangle.fill")
                .font(.footnote)
                .foregroundStyle(.red)
                .padding()
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(.red.opacity(0.08))
                .clipShape(RoundedRectangle(cornerRadius: 8))
        } else if let info = model.infoMessage {
            Label(info, systemImage: "checkmark.circle.fill")
                .font(.footnote)
                .foregroundStyle(.secondary)
                .padding()
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(.thinMaterial)
                .clipShape(RoundedRectangle(cornerRadius: 8))
        }
    }

    private var deckPanelBackground: some ShapeStyle {
        LinearGradient(
            colors: [
                Color(red: 0.19, green: 0.13, blue: 0.075).opacity(0.9),
                Color(red: 0.055, green: 0.048, blue: 0.039).opacity(0.98)
            ],
            startPoint: .top,
            endPoint: .bottom
        )
    }

    private var deckPanelStroke: some View {
        RoundedRectangle(cornerRadius: 8)
            .stroke(
                LinearGradient(
                    colors: [.yellow.opacity(0.42), .brown.opacity(0.34), .black.opacity(0.42)],
                    startPoint: .topLeading,
                    endPoint: .bottomTrailing
                ),
                lineWidth: 1
            )
    }

    private func deckMetricSeal(title: String, value: String, ok: Bool) -> some View {
        VStack(spacing: 2) {
            Text(value)
                .font(.headline.monospacedDigit().bold())
                .foregroundStyle(ok ? .white : .orange)
                .lineLimit(1)
                .minimumScaleFactor(0.72)
            Text(title)
                .font(.caption2.bold())
                .foregroundStyle(.white.opacity(0.56))
                .lineLimit(1)
                .minimumScaleFactor(0.7)
        }
        .frame(maxWidth: .infinity, minHeight: 46)
        .background(.black.opacity(ok ? 0.26 : 0.38))
        .overlay(
            RoundedRectangle(cornerRadius: 7)
                .stroke(ok ? .white.opacity(0.1) : .orange.opacity(0.45), lineWidth: 1)
        )
        .clipShape(RoundedRectangle(cornerRadius: 7))
    }

    @ViewBuilder
    private func leaderComparisonList(deck: GwentDeck, compact: Bool) -> some View {
        let faction = gwentDeckFaction(deck)
        let leaders = leaderCards(forFaction: faction)

        if leaders.count > 1 {
            VStack(alignment: .leading, spacing: 8) {
                HStack(spacing: 8) {
                    Image(systemName: "crown.fill")
                        .font(.caption.bold())
                        .foregroundStyle(.yellow)
                    Text("Лидеры \(gwentFactionLabel(faction))")
                        .font(.caption.bold())
                        .foregroundStyle(.white.opacity(0.82))
                    Spacer(minLength: 8)
                    Text("выбор")
                        .font(.caption2.bold())
                        .foregroundStyle(.yellow.opacity(0.72))
                }

                ForEach(leaders) { leader in
                    leaderChoiceRow(
                        leader,
                        selected: leader.cardId == selectedDeckLeaderId,
                        compact: compact
                    )
                }
            }
            .padding(compact ? 8 : 10)
            .background(.black.opacity(0.18))
            .overlay(
                RoundedRectangle(cornerRadius: 8)
                    .stroke(.white.opacity(0.08), lineWidth: 1)
            )
            .clipShape(RoundedRectangle(cornerRadius: 8))
        }
    }

    private func leaderChoiceRow(_ leader: GwentCard, selected: Bool, compact: Bool) -> some View {
        Button {
            applyDeckLeader(leader.cardId)
        } label: {
            HStack(alignment: .top, spacing: compact ? 8 : 10) {
                Image(systemName: selected ? "checkmark.seal.fill" : "crown")
                    .font(.system(size: compact ? 15 : 17, weight: .black))
                    .foregroundStyle(selected ? .green : .yellow)
                    .frame(width: compact ? 28 : 32, height: compact ? 28 : 32)
                    .background(.black.opacity(0.34))
                    .clipShape(Circle())

                VStack(alignment: .leading, spacing: 3) {
                    Text(gwentCardTitle(leader.cardId))
                        .font(.caption.bold())
                        .foregroundStyle(.white)
                        .lineLimit(2)
                        .minimumScaleFactor(0.78)
                    Text(gwentLeaderAbilityText(leader))
                        .font(.caption2)
                        .foregroundStyle(.white.opacity(0.62))
                        .fixedSize(horizontal: false, vertical: true)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
            }
            .padding(compact ? 7 : 8)
            .background(selected ? .yellow.opacity(0.16) : .black.opacity(0.22))
            .overlay(
                RoundedRectangle(cornerRadius: 7)
                    .stroke(selected ? .yellow.opacity(0.64) : .white.opacity(0.08), lineWidth: 1)
            )
            .clipShape(RoundedRectangle(cornerRadius: 7))
        }
        .buttonStyle(.plain)
    }

    private func deckSelectedStrip(compact: Bool) -> some View {
        let metrics = gwentDeckMetrics(cardIds: deckDraftCardIds)

        return VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text("Карты в боевой колоде")
                    .font(.headline)
                    .foregroundStyle(.white)
                Spacer()
                Text("\(metrics.units)/\(gwentDeckMinUnitCards)+ отр. · \(metrics.specials)/\(gwentDeckSpecialCardLimit) особ.")
                    .font(.caption.monospacedDigit().bold())
                    .foregroundStyle(.white.opacity(0.72))
                    .lineLimit(1)
                    .minimumScaleFactor(0.72)
            }

            let selectedCards = deckDraftCards
            if selectedCards.isEmpty {
                Text("Нажимай на карты ниже, чтобы собрать минимум 22 отряда перед боем.")
                    .font(.caption)
                    .foregroundStyle(.white.opacity(0.58))
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.vertical, 14)
            } else {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: compact ? 8 : 10) {
                        ForEach(selectedCards) { card in
                            Button {
                                requestDeckCardRemoval(card)
                            } label: {
                                gwentCardView(
                                    card,
                                    selected: selectedDeckCardId == card.cardId,
                                    inDeck: true,
                                    compact: true,
                                    large: false
                                )
                            }
                            .buttonStyle(.plain)
                        }
                    }
                    .padding(.vertical, 6)
                }
            }
        }
    }

    private var deckFilterControls: some View {
        VStack(alignment: .leading, spacing: 8) {
            rowFilterControl
            strengthFilterControl
        }
    }

    private var rowFilterControl: some View {
        Picker("Ряд", selection: $deckRowFilter) {
            ForEach(DeckRowFilter.allCases) { filter in
                Text(filter.title).tag(filter)
            }
        }
        .pickerStyle(.segmented)
        .tint(.orange)
    }

    private var strengthFilterControl: some View {
        Picker("Сила", selection: $deckStrengthFilter) {
            ForEach(DeckStrengthFilter.allCases) { filter in
                Text(filter.title).tag(filter)
            }
        }
        .pickerStyle(.segmented)
        .tint(.yellow)
    }

    private func cardCollectionGrid(
        cards: [GwentCard],
        compact: Bool,
        allowsEditing: Bool,
        selectedCardId: String? = nil
    ) -> some View {
        let columns = [
            GridItem(.adaptive(minimum: compact ? 96 : 108, maximum: compact ? 112 : 128), spacing: compact ? 9 : 11)
        ]
        let activeSelectedCardId = selectedCardId ?? self.selectedDeckCardId

        return LazyVGrid(columns: columns, spacing: compact ? 10 : 12) {
            ForEach(cards) { card in
                let inDeck = deckDraftCardIds.contains(card.cardId) || deckDraftLeaderId == card.cardId
                Button {
                    if allowsEditing {
                        toggleDeckCard(card)
                    } else {
                        selectedDeckCardId = card.cardId
                        showDeckCardInspector = true
                    }
                } label: {
                    gwentCardView(
                        card,
                        selected: activeSelectedCardId == card.cardId,
                        inDeck: inDeck,
                        compact: compact,
                        large: false
                    )
                }
                .buttonStyle(.plain)
            }
        }
    }

    private func gwentCardView(
        _ card: GwentCard,
        selected: Bool,
        inDeck: Bool,
        compact: Bool,
        large: Bool
    ) -> some View {
        let rowColor = gwentRowColor(card.row)
        let effects = gwentCardEffects(card)
        let visibleEffects = Array(effects.prefix(large ? 4 : 3))
        let primaryEffect = effects.first
        let effectColor = primaryEffect.map(gwentEffectColor) ?? .white.opacity(0.34)
        let width: CGFloat = large ? (compact ? 112 : 124) : (compact ? 98 : 112)
        let height: CGFloat = large ? (compact ? 158 : 176) : (compact ? 146 : 160)

        return ZStack(alignment: .topLeading) {
            RoundedRectangle(cornerRadius: 8)
                .fill(
                    LinearGradient(
                        colors: [
                            rowColor.opacity(0.38),
                            Color(red: 0.13, green: 0.105, blue: 0.075),
                            Color(red: 0.035, green: 0.031, blue: 0.026)
                        ],
                        startPoint: .topLeading,
                        endPoint: .bottomTrailing
                    )
                )
                .shadow(color: selected ? rowColor.opacity(0.5) : .black.opacity(0.46), radius: selected ? 10 : 4, y: 4)

            VStack(spacing: compact ? 4 : 5) {
                ZStack {
                    RoundedRectangle(cornerRadius: 5)
                        .fill(
                            LinearGradient(
                                colors: [
                                    rowColor.opacity(0.32),
                                    Color(red: 0.09, green: 0.075, blue: 0.058),
                                    .black.opacity(0.68)
                                ],
                                startPoint: .top,
                                endPoint: .bottom
                            )
                        )
                    gwentArtworkContent(card, rowColor: rowColor, compact: compact, large: large)
                    VStack {
                        Spacer()
                        HStack {
                            Image(systemName: gwentRowIcon(card.row))
                                .font(.caption2.bold())
                                .foregroundStyle(.white.opacity(0.86))
                                .padding(5)
                                .background(.black.opacity(0.44))
                                .clipShape(Circle())
                            Spacer()
                        }
                        .padding(5)
                    }
                    if !visibleEffects.isEmpty {
                        VStack {
                            Spacer()
                            HStack(spacing: 3) {
                                Spacer(minLength: 0)
                                ForEach(visibleEffects, id: \.self) { effect in
                                    Image(systemName: gwentEffectIcon(effect))
                                        .font(.system(size: large ? 10 : 9, weight: .black))
                                        .foregroundStyle(.white)
                                        .frame(width: large ? 20 : 18, height: large ? 20 : 18)
                                        .background(gwentEffectColor(effect).opacity(0.92))
                                        .clipShape(Circle())
                                        .overlay(Circle().stroke(.black.opacity(0.42), lineWidth: 1))
                                        .shadow(color: .black.opacity(0.55), radius: 2, y: 1)
                                }
                            }
                            .padding(5)
                        }
                    }
                }
                .frame(height: large ? (compact ? 82 : 92) : (compact ? 72 : 80))
                .clipShape(RoundedRectangle(cornerRadius: 5))

                Text(gwentCardTitle(card.cardId))
                    .font(large ? .caption.bold() : .caption2.bold())
                    .foregroundStyle(.white)
                    .multilineTextAlignment(.center)
                    .lineLimit(2)
                    .minimumScaleFactor(0.62)
                    .padding(.horizontal, 4)
                    .frame(maxWidth: .infinity, minHeight: compact ? 26 : 30)
                    .background(.black.opacity(0.38))
                    .clipShape(RoundedRectangle(cornerRadius: 4))

                HStack(spacing: 3) {
                    if let primaryEffect {
                        Image(systemName: gwentEffectIcon(primaryEffect))
                            .font(.system(size: compact ? 8 : 9, weight: .black))
                    }
                    Text(gwentEffectSummary(card))
                        .lineLimit(1)
                        .minimumScaleFactor(0.56)
                }
                .font(.system(size: compact ? 8 : 9, weight: .bold))
                .foregroundStyle(primaryEffect == nil ? .white.opacity(0.58) : .white)
                .padding(.horizontal, 5)
                .frame(maxWidth: .infinity, minHeight: 17)
                .background((primaryEffect == nil ? rowColor.opacity(0.28) : effectColor.opacity(0.82)))
                .clipShape(RoundedRectangle(cornerRadius: 4))
            }
            .padding(large ? 7 : 6)

            Text(gwentCardBadgeText(card))
                .font(.system(size: large ? 18 : 16, weight: .black, design: .rounded))
                .foregroundStyle(.black)
                .frame(width: large ? 34 : 30, height: large ? 34 : 30)
                .background(
                    Circle()
                        .fill(gwentCardBadgeColor(card))
                        .overlay(Circle().stroke(.orange.opacity(0.82), lineWidth: 2))
                )
                .padding(5)

            if inDeck {
                Image(systemName: "checkmark.seal.fill")
                    .font(.headline)
                    .foregroundStyle(.green)
                    .shadow(color: .black.opacity(0.6), radius: 2)
                    .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topTrailing)
                    .padding(6)
            }
        }
        .frame(width: width, height: height)
        .overlay(
            RoundedRectangle(cornerRadius: 8)
                .stroke(selected ? .yellow.opacity(0.92) : rowColor.opacity(inDeck ? 0.68 : 0.34), lineWidth: selected ? 2.2 : 1.2)
        )
        .accessibilityLabel("\(gwentCardTitle(card.cardId)), \(deckCardDetail(card.cardId))")
    }

    @ViewBuilder
    private func gwentArtworkContent(_ card: GwentCard, rowColor: Color, compact: Bool, large: Bool) -> some View {
        if let assetName = gwentArtworkAssetName(card) {
            GeometryReader { proxy in
                Image(assetName)
                    .resizable()
                    .aspectRatio(contentMode: .fill)
                    .frame(width: proxy.size.width, height: proxy.size.height, alignment: .top)
                    .clipped()
            }
        } else {
            Image(systemName: gwentArtworkIcon(card))
                .font(.system(size: large ? 38 : (compact ? 30 : 34), weight: .semibold))
                .foregroundStyle(rowColor.opacity(0.88))
                .shadow(color: .black.opacity(0.8), radius: 3, y: 2)
        }
    }

    private func gwentArtworkAssetName(_ card: GwentCard) -> String? {
        guard let assetName = gwentArtworkAssetName(for: card.cardId) else { return nil }
        #if canImport(UIKit)
        return UIImage(named: assetName) == nil ? nil : assetName
        #else
        return assetName
        #endif
    }

    private func gwentArtworkAssetName(for cardId: String) -> String? {
        let normalizedCardId = cardId.trimmingCharacters(in: .whitespacesAndNewlines)
        return normalizedCardId.isEmpty ? nil : "gwent_card_art_\(normalizedCardId)"
    }

    private func deckCardInspector(_ card: GwentCard, compact: Bool) -> some View {
        HStack(alignment: .top, spacing: compact ? 10 : 12) {
            gwentCardView(
                card,
                selected: true,
                inDeck: deckDraftCardIds.contains(card.cardId) || deckDraftLeaderId == card.cardId,
                compact: compact,
                large: true
            )
            VStack(alignment: .leading, spacing: 8) {
                Text(gwentCardTitle(card.cardId))
                    .font(.headline)
                    .foregroundStyle(.white)
                    .lineLimit(2)
                    .minimumScaleFactor(0.74)
                Text(deckCardDetail(card.cardId))
                    .font(.caption)
                    .foregroundStyle(.white.opacity(0.68))
                    .fixedSize(horizontal: false, vertical: true)
                ViewThatFits(in: .horizontal) {
                    HStack(spacing: 6) {
                        deckPropertyChip(gwentTypeLabel(card.type), color: .orange)
                        deckPropertyChip(gwentRowLabel(card.row), color: gwentRowColor(card.row))
                        deckPropertyChip(gwentFactionLabel(card.faction), color: .yellow)
                        deckPropertyChip(gwentRarityLabel(card.rarity), color: gwentRarityColor(card.rarity))
                    }
                    VStack(alignment: .leading, spacing: 6) {
                        HStack(spacing: 6) {
                            deckPropertyChip(gwentTypeLabel(card.type), color: .orange)
                            deckPropertyChip(gwentRowLabel(card.row), color: gwentRowColor(card.row))
                        }
                        HStack(spacing: 6) {
                            deckPropertyChip(gwentFactionLabel(card.faction), color: .yellow)
                            deckPropertyChip(gwentRarityLabel(card.rarity), color: gwentRarityColor(card.rarity))
                        }
                    }
                }
                deckCardEffectRows(card)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .padding(10)
        .background(.black.opacity(0.28))
        .overlay(
            RoundedRectangle(cornerRadius: 8)
                .stroke(.white.opacity(0.1), lineWidth: 1)
        )
        .clipShape(RoundedRectangle(cornerRadius: 8))
    }

    private func deckCardEffectRows(_ card: GwentCard) -> some View {
        let effects = gwentCardEffects(card)

        return VStack(alignment: .leading, spacing: 6) {
            if effects.isEmpty {
                deckCardEffectRow(effect: "none", card: card)
            } else {
                ForEach(effects, id: \.self) { effect in
                    deckCardEffectRow(effect: effect, card: card)
                }
            }
        }
    }

    private func deckCardEffectRow(effect: String, card: GwentCard) -> some View {
        HStack(alignment: .top, spacing: 8) {
            Image(systemName: gwentEffectIcon(effect))
                .font(.caption.bold())
                .foregroundStyle(.white)
                .frame(width: 26, height: 26)
                .background(gwentEffectColor(effect).opacity(effect == "none" ? 0.26 : 0.86))
                .clipShape(RoundedRectangle(cornerRadius: 6))
            VStack(alignment: .leading, spacing: 2) {
                Text(gwentEffectLabel(effect))
                    .font(.caption.bold())
                    .foregroundStyle(.white)
                Text(gwentCardEffectRuleText(effect, card: card))
                    .font(.caption2)
                    .foregroundStyle(.white.opacity(0.64))
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
    }

    private func deckCardDetailSheet(_ card: GwentCard) -> some View {
        NavigationStack {
            ZStack {
                deckScreenBackground
                    .ignoresSafeArea()
                ScrollView {
                    VStack(alignment: .leading, spacing: 14) {
                        deckCardInspector(card, compact: false)
                    }
                    .padding()
                }
            }
            .navigationTitle("Карта")
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("Готово") {
                        showDeckCardInspector = false
                    }
                }
            }
        }
        .preferredColorScheme(.dark)
        .presentationDetents([.medium, .large])
    }

    private func deckPropertyChip(_ title: String, color: Color) -> some View {
        Text(title)
            .font(.caption2.bold())
            .foregroundStyle(color)
            .lineLimit(1)
            .minimumScaleFactor(0.66)
            .padding(.horizontal, 7)
            .frame(height: 22)
            .background(color.opacity(0.12))
            .clipShape(RoundedRectangle(cornerRadius: 5))
    }

    private var emptyDeckState: some View {
        VStack(alignment: .leading, spacing: 8) {
            Label("Колода пока не найдена в дневнике.", systemImage: "rectangle.stack.badge.questionmark")
                .font(.headline)
                .foregroundStyle(.white)
            Text("Обнови дневник в Wi-Fi зоне, чтобы получить карты и стартовую колоду персонажа.")
                .font(.caption)
                .foregroundStyle(.white.opacity(0.62))
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(.vertical, 18)
    }

    private var currentPlayerGwentDeck: GwentDeck? {
        guard let playerId = model.player?.playerId else { return nil }
        let runtimeDecks = model.runtimeGwentDecks.filter { $0.playerId == playerId }
        if let runtime = runtimeDecks.reversed().first {
            return runtime
        }
        return model.snapshot?.gwentDecks.first { $0.playerId == playerId }
    }

    private var draftGwentDeck: GwentDeck? {
        guard let player = model.player,
              let base = currentPlayerGwentDeck
        else { return nil }
        let leaderId = deckDraftLeaderId.isEmpty ? base.leaderCardId : deckDraftLeaderId
        return GwentDeck(
            deckId: base.deckId,
            playerId: player.playerId,
            leaderCardId: leaderId,
            cardIds: deckDraftCardIds
        )
    }

    private var importedPlayerGwentDecks: [GwentDeck] {
        guard let playerId = model.player?.playerId else { return [] }
        return (model.snapshot?.gwentDecks ?? []).filter { $0.playerId == playerId }
    }

    private var selectedDeckLeaderId: String {
        if !deckDraftLeaderId.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            return deckDraftLeaderId
        }
        return currentPlayerGwentDeck?.leaderCardId ?? ""
    }

    private var deckCollectionSource: GwentDeck? {
        let importedDecks = importedPlayerGwentDecks
        if let byLeader = importedDecks.first(where: { $0.leaderCardId == selectedDeckLeaderId }) {
            return byLeader
        }
        if let current = currentPlayerGwentDeck {
            if let exact = importedDecks.first(where: { $0.deckId == current.deckId }) {
                return exact
            }
            if let base = importedDecks.first(where: { current.deckId.hasSuffix("_\($0.deckId)") }) {
                return base
            }
            return current
        }
        return importedDecks.first
    }

    private var deckAvailableCards: [GwentCard] {
        deckAvailableCardIds
            .compactMap(gwentCardMeta)
            .filter { $0.type.lowercased() != "leader" && $0.row.lowercased() != "leader" }
    }

    private var deckAvailableCardIds: [String] {
        var ids: [String] = []
        var seen: Set<String> = []

        func appendUnique(_ cardIds: [String]) {
            for rawCardId in cardIds {
                let cardId = rawCardId.trimmingCharacters(in: .whitespacesAndNewlines)
                guard !cardId.isEmpty, !seen.contains(cardId) else { continue }
                seen.insert(cardId)
                ids.append(cardId)
            }
        }

        appendUnique(deckCollectionSource?.cardIds ?? [])
        appendUnique(currentPlayerGwentDeck?.cardIds ?? [])
        appendUnique(runtimeGwentDecksForCurrentPlayer.flatMap(\.cardIds))
        appendUnique(ownedRuntimeGwentCardIds)
        return ids
    }

    private var gwentCatalogCards: [GwentCard] {
        var cardsById: [String: GwentCard] = [:]
        for card in GwentStaticCatalog.allCards {
            cardsById[card.cardId] = card
        }
        for card in model.snapshot?.gwentCards ?? [] {
            if !card.displayName.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                cardsById[card.cardId] = card
            } else if cardsById[card.cardId] == nil {
                cardsById[card.cardId] = card
            }
        }
        return cardsById.values.sorted { lhs, rhs in
            if lhs.faction != rhs.faction {
                return gwentFactionLabel(lhs.faction) < gwentFactionLabel(rhs.faction)
            }
            if lhs.row != rhs.row {
                return rowSortRank(lhs.row) < rowSortRank(rhs.row)
            }
            if lhs.type != rhs.type {
                return lhs.type < rhs.type
            }
            if lhs.strength != rhs.strength {
                return lhs.strength > rhs.strength
            }
            return gwentCardTitle(lhs.cardId) < gwentCardTitle(rhs.cardId)
        }
    }

    private var availableLeaderCards: [GwentCard] {
        gwentCatalogCards
            .filter { $0.type.lowercased() == "leader" || $0.row.lowercased() == "leader" }
            .sorted { lhs, rhs in
                if lhs.faction != rhs.faction {
                    return gwentFactionLabel(lhs.faction) < gwentFactionLabel(rhs.faction)
                }
                return gwentCardTitle(lhs.cardId) < gwentCardTitle(rhs.cardId)
            }
    }

    private func leaderCards(forFaction faction: String) -> [GwentCard] {
        let normalizedFaction = faction.lowercased()
        return availableLeaderCards.filter { leader in
            leader.faction.lowercased() == normalizedFaction
        }
    }

    private var deckDraftCards: [GwentCard] {
        deckDraftCardIds.compactMap(gwentCardMeta)
    }

    private var selectedDeckCard: GwentCard? {
        gwentCardMeta(selectedDeckCardId)
            ?? deckDraftCards.first
            ?? filteredDeckCardsIncludingLeaders.first
    }

    private var filteredDeckCards: [GwentCard] {
        filterCards(deckAvailableCards)
    }

    private var filteredDeckCardsIncludingLeaders: [GwentCard] {
        filterCards(gwentCatalogCards)
    }

    private var ownedEncyclopediaCardIds: Set<String> {
        var cardIds = Set(deckAvailableCardIds)
        cardIds.formUnion(deckDraftCardIds)
        let leaderId = selectedDeckLeaderId.trimmingCharacters(in: .whitespacesAndNewlines)
        if !leaderId.isEmpty {
            cardIds.insert(leaderId)
        }
        return cardIds
    }

    private var filteredEncyclopediaCards: [GwentCard] {
        let cards = gwentCatalogCards
        switch deckEncyclopediaScope {
        case .owned:
            return filterCards(cards.filter { ownedEncyclopediaCardIds.contains($0.cardId) })
        case .all:
            return filterCards(cards)
        }
    }

    private func selectedEncyclopediaCard(in cards: [GwentCard]) -> GwentCard? {
        if let selected = gwentCardMeta(selectedDeckCardId),
           cards.contains(where: { $0.cardId == selected.cardId }) {
            return selected
        }
        return cards.first
    }

    private func filterCards(_ cards: [GwentCard]) -> [GwentCard] {
        cards
            .filter { card in
                matchesDeckRowFilter(card) && deckStrengthFilter.contains(card.strength)
            }
            .sorted { lhs, rhs in
                let leftDeckRank = deckDraftCardIds.contains(lhs.cardId) || deckDraftLeaderId == lhs.cardId ? 0 : 1
                let rightDeckRank = deckDraftCardIds.contains(rhs.cardId) || deckDraftLeaderId == rhs.cardId ? 0 : 1
                if leftDeckRank != rightDeckRank {
                    return leftDeckRank < rightDeckRank
                }
                if lhs.row != rhs.row {
                    return rowSortRank(lhs.row) < rowSortRank(rhs.row)
                }
                if lhs.strength != rhs.strength {
                    return lhs.strength > rhs.strength
                }
                return gwentCardTitle(lhs.cardId) < gwentCardTitle(rhs.cardId)
            }
    }

    private func matchesDeckRowFilter(_ card: GwentCard) -> Bool {
        switch deckRowFilter {
        case .all:
            return true
        case .melee, .ranged, .siege:
            return card.row.lowercased() == deckRowFilter.rawValue
        case .special:
            return ["special", "weather"].contains(card.row.lowercased()) || card.type.lowercased() == "special"
        }
    }

    private func syncDeckDraftIfNeeded(force: Bool = false) {
        guard let deck = currentPlayerGwentDeck else { return }
        let fingerprint = deckFingerprint(deck)
        guard force || fingerprint != deckDraftSourceFingerprint else { return }
        deckDraftSourceFingerprint = fingerprint
        deckDraftCardIds = deck.cardIds
        deckDraftLeaderId = deck.leaderCardId
        selectedDeckCardId = deckDraftCardIds.first ?? deck.leaderCardId
    }

    private func applyDeckScreenshotArgumentsIfNeeded() {
        #if DEBUG
        guard !appliedDeckScreenshotArguments else { return }
        let arguments = ProcessInfo.processInfo.arguments
        var applied = false
        if let modeIndex = arguments.firstIndex(of: "--deck-mode") {
            let valueIndex = arguments.index(after: modeIndex)
            if arguments.indices.contains(valueIndex),
               let mode = DeckSetupMode(rawValue: arguments[valueIndex]) {
                deckMode = mode
                applied = true
            }
        }
        if let cardIndex = arguments.firstIndex(of: "--deck-card") {
            let valueIndex = arguments.index(after: cardIndex)
            if arguments.indices.contains(valueIndex) {
                selectedDeckCardId = arguments[valueIndex]
                applied = true
            }
        }
        if applied {
            appliedDeckScreenshotArguments = true
        }
        #endif
    }

    private func deckFingerprint(_ deck: GwentDeck) -> String {
        "\(deck.deckId)|\(deck.leaderCardId)|\(deck.cardIds.joined(separator: ","))"
    }

    private func applyDeckLeader(_ leaderId: String) {
        deckDraftLeaderId = leaderId
        if let source = importedPlayerGwentDecks.first(where: { $0.leaderCardId == leaderId }) {
            deckDraftCardIds = source.cardIds
            selectedDeckCardId = deckDraftCardIds.first ?? leaderId
        } else {
            selectedDeckCardId = leaderId
        }
    }

    private func toggleDeckCard(_ card: GwentCard) {
        selectedDeckCardId = card.cardId
        if card.type.lowercased() == "leader" || card.row.lowercased() == "leader" {
            applyDeckLeader(card.cardId)
            return
        }
        if deckDraftCardIds.contains(card.cardId) {
            requestDeckCardRemoval(card)
        } else {
            let metrics = gwentDeckMetrics(cardIds: deckDraftCardIds)
            let type = card.type.lowercased()
            if type == "special", metrics.specials >= gwentDeckSpecialCardLimit {
                model.infoMessage = "В боевой колоде уже 10 особых карт."
                return
            }
            deckDraftCardIds.append(card.cardId)
        }
    }

    private func requestDeckCardRemoval(_ card: GwentCard) {
        selectedDeckCardId = card.cardId
        pendingDeckRemovalCardId = card.cardId
    }

    private var deckRemovalConfirmationBinding: Binding<Bool> {
        Binding(
            get: { !pendingDeckRemovalCardId.isEmpty },
            set: { isPresented in
                if !isPresented {
                    pendingDeckRemovalCardId = ""
                }
            }
        )
    }

    private var deckRemovalConfirmationMessage: String {
        let title = pendingDeckRemovalCardId.isEmpty
            ? "Эта карта"
            : "«\(gwentCardTitle(pendingDeckRemovalCardId))»"
        return "\(title) останется в доступных картах, но будет убрана из боевой колоды."
    }

    private func confirmDeckCardRemoval() {
        let cardId = pendingDeckRemovalCardId
        pendingDeckRemovalCardId = ""
        guard let index = deckDraftCardIds.firstIndex(of: cardId) else { return }
        deckDraftCardIds.remove(at: index)
        selectedDeckCardId = deckDraftCardIds.first ?? deckDraftLeaderId
    }

    private func saveDeckDraft(_ deck: GwentDeck) async {
        guard !isSavingDeckDraft else { return }
        isSavingDeckDraft = true
        let deckToSave = GwentDeck(
            deckId: deck.deckId,
            playerId: deck.playerId,
            leaderCardId: deckDraftLeaderId.isEmpty ? deck.leaderCardId : deckDraftLeaderId,
            cardIds: deckDraftCardIds
        )
        if let savedDeck = await model.saveGwentDeck(deckToSave) {
            deckDraftCardIds = savedDeck.cardIds
            deckDraftLeaderId = savedDeck.leaderCardId
            deckDraftSourceFingerprint = deckFingerprint(savedDeck)
        }
        isSavingDeckDraft = false
    }

    private func gwentDeckMetrics(cardIds: [String]) -> HomeGwentDeckMetrics {
        var rows = ["melee": 0, "ranged": 0, "siege": 0]
        var units = 0
        var specials = 0
        var heroes = 0
        var strength = 0

        for cardId in cardIds {
            guard let card = gwentCardMeta(cardId) else { continue }
            let type = card.type.lowercased()
            if type == "unit" {
                units += 1
                strength += card.strength
                if rows[card.row] != nil {
                    rows[card.row, default: 0] += 1
                }
            } else if type == "special" {
                specials += 1
            }
            if card.effect.lowercased() == "hero" {
                heroes += 1
            }
        }

        return HomeGwentDeckMetrics(
            total: cardIds.count,
            units: units,
            specials: specials,
            heroes: heroes,
            strength: strength,
            rows: rows
        )
    }

    private func gwentDeckWarnings(_ metrics: HomeGwentDeckMetrics) -> [String] {
        var warnings: [String] = []
        if metrics.units < gwentDeckMinUnitCards {
            warnings.append("Нужно выбрать минимум 22 карты отрядов.")
        }
        if metrics.specials > gwentDeckSpecialCardLimit {
            warnings.append("Особых карт должно быть не больше 10.")
        }
        if metrics.activeRows < 2 {
            warnings.append("Колода почти не покрывает боевые ряды.")
        }
        return warnings
    }

    private func gwentDeckTitle(_ deck: GwentDeck) -> String {
        let playerName = gwentPlayerName(deck.playerId)
        let faction = gwentFactionLabel(gwentDeckFaction(deck))
        if !playerName.isEmpty {
            return "\(playerName) - \(faction)"
        }
        return faction
    }

    private func gwentDeckFaction(_ deck: GwentDeck) -> String {
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

    private func gwentFactionLabel(_ faction: String) -> String {
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

    private func gwentFactionAbilityLabel(_ faction: String) -> String {
        switch faction.lowercased() {
        case "northern":
            return "+1 карта после выигранного раунда"
        case "nilfgaard":
            return "ничья считается победой фракции"
        case "scoiatael", "scoia'tael":
            return "контроль первого хода"
        case "monsters":
            return "одна карта отряда остается после раунда"
        case "skellige":
            return "возврат карт из сброса в третьем раунде"
        default:
            return "без фракционного бонуса"
        }
    }

    private func gwentLeaderAbilityText(_ leader: GwentCard) -> String {
        if !leader.effectText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            return leader.effectText
        }
        let rule = gwentEffectRulesText(leader.effect)
        if !rule.isEmpty {
            return rule
        }
        return gwentEffectSummary(leader)
    }

    private func deckCardDetail(_ cardId: String) -> String {
        guard let card = gwentCardMeta(cardId) else {
            return readableIdentifier(cardId)
        }
        let effect = card.effectText.isEmpty ? gwentEffectSummary(card) : card.effectText
        return "\(gwentRowLabel(card.row)) · \(gwentTypeLabel(card.type)) · \(effect)"
    }

    private func gwentTypeLabel(_ type: String) -> String {
        switch type.lowercased() {
        case "unit":
            return "отряд"
        case "special":
            return "особая"
        case "leader":
            return "лидер"
        default:
            return readableIdentifier(type)
        }
    }

    private func gwentEffectLabel(_ effect: String) -> String {
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
            return "мороз"
        case "weather_ranged", "impenetrable_fog":
            return "туман"
        case "weather_siege", "torrential_rain":
            return "ливень"
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
            return "замешать сброс"
        default:
            return readableIdentifier(effect)
        }
    }

    private func rowSortRank(_ row: String) -> Int {
        switch row.lowercased() {
        case "leader":
            return 0
        case "melee":
            return 1
        case "ranged":
            return 2
        case "siege":
            return 3
        case "weather":
            return 4
        case "special":
            return 5
        default:
            return 9
        }
    }

    private func gwentArtworkIcon(_ card: GwentCard) -> String {
        switch card.effect.lowercased() {
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
        case "scorch", "scorch_siege":
            return "flame.fill"
        default:
            break
        }
        switch card.row.lowercased() {
        case "leader":
            return "crown.fill"
        case "melee":
            return "shield.lefthalf.filled"
        case "ranged":
            return "scope"
        case "siege":
            return "building.columns.fill"
        case "weather":
            return "cloud.bolt.rain.fill"
        case "special":
            return "sparkles"
        default:
            return "suit.club.fill"
        }
    }

    private func gwentRarityColor(_ rarity: String) -> Color {
        switch rarity.lowercased() {
        case "common":
            return .white.opacity(0.72)
        case "uncommon":
            return .green
        case "rare":
            return .cyan
        case "legendary":
            return .yellow
        default:
            return .secondary
        }
    }

    private var gwentBoardCard: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Состояние стола")
                .font(.headline)

            if let root = gwentStateRoot {
                let challenge = gwentChallengeObject(root)
                let match = gwentMatchObject(root)
                let round = gwentRoundObject(root)
                let roundState = gwentRoundState(root)

                VStack(alignment: .leading, spacing: 4) {
                    if let challenge {
                        Text("Вызов: \(shortGameCode(challenge.string("challenge_id")))")
                        Text("Статус: \(gwentStatusLabel(challenge.string("status", default: "unknown")))")
                        let zone = challenge.string("assigned_zone")
                        if !zone.isEmpty {
                            Text("Зона встречи: \(zoneLabel(zone))")
                        }
                    } else {
                        Text("Активного вызова нет")
                    }
                }
                .font(.caption)
                .foregroundStyle(.secondary)

                if let match {
                    VStack(alignment: .leading, spacing: 4) {
                        Text("Матч: \(shortGameCode(match.string("match_id")))")
                            .font(.subheadline.bold())
                        Text("Статус: \(gwentStatusLabel(match.string("status", default: "unknown")))")
                            .font(.caption)
                            .foregroundStyle(.secondary)

                        if let deckState = match.object("deck_state") {
                            ForEach(Array(gwentPlayerIds(deckState).enumerated()), id: \.offset) { _, playerId in
                                gwentPlayerDeckState(playerId: playerId, state: deckState.object(playerId) ?? [:])
                            }
                        }
                    }
                }

                if let roundState {
                    VStack(alignment: .leading, spacing: 8) {
                        let roundNumber = round?.int("round_number") ?? root.int("round_number")
                        Text("Раунд \(roundNumber == 0 ? 1 : roundNumber)")
                            .font(.subheadline.bold())
                        Text("Статус раунда: \(gwentStatusLabel(roundState.string("status", default: "unknown")))")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                        let ready = roundState.arrayStrings("ready_players")
                        let missing = roundState.arrayStrings("missing_players")
                        if !ready.isEmpty || !missing.isEmpty {
                            Text("Готовы: \(gwentPlayerList(ready)) · Ожидаем: \(gwentPlayerList(missing))")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }
                        if let board = roundState.object("board") {
                            ForEach(Array(gwentPlayerIds(board).enumerated()), id: \.offset) { _, playerId in
                                gwentBoardPlayer(playerId: playerId, board: board.object(playerId) ?? [:])
                            }
                        }
                    }
                }
            } else {
                Text("Начни вызов или обнови столы, чтобы увидеть состояние партии.")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
            }
        }
        .cardStyle()
    }

    private var gwentActionCard: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Text("Текущая партия")
                    .font(.headline)
                Spacer()
                Button {
                    Task { await model.refreshPvpTables() }
                } label: {
                    Image(systemName: "arrow.clockwise")
                }
                .buttonStyle(.bordered)
                .accessibilityLabel("Обновить Гвинт")
            }

            if let root = gwentStateRoot {
                if let match = gwentMatchObject(root) {
                    let roundNumber = activeGwentRoundNumber(root)

                    VStack(alignment: .leading, spacing: 8) {
                        Text("Раунд \(roundNumber) · \(gwentStatusLabel(match.string("status", default: "active")))")
                            .font(.subheadline)
                            .foregroundStyle(.secondary)

                        if activeGwentCanPlay(root) {
                            Text("Ваш ход. Откройте стол, чтобы выбрать карту, ряд, цель или пас.")
                                .font(.subheadline)
                                .foregroundStyle(.primary)
                        } else if activeGwentPlayerSubmitted(root) {
                            Text("Ход отправлен. Ждем второго игрока или обновления стола.")
                                .font(.subheadline)
                                .foregroundStyle(.secondary)
                        } else {
                            Text("Сейчас нельзя ходить: \(activeGwentBlockReason(root))")
                                .font(.subheadline)
                                .foregroundStyle(.secondary)
                        }

                        Button {
                            showGwentTable = true
                        } label: {
                            Label("Открыть стол", systemImage: "iphone.landscape")
                                .frame(maxWidth: .infinity)
                        }
                        .buttonStyle(.borderedProminent)
                    }
                } else if let challenge = gwentChallengeObject(root) {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Вызов \(gwentStatusLabel(challenge.string("status", default: "unknown")))")
                            .font(.subheadline)
                            .foregroundStyle(.secondary)
                        let readyPlayers = gwentChallengeReadyPlayers(challenge)
                        let missingPlayers = gwentChallengeMissingPlayers(challenge)
                        if !readyPlayers.isEmpty || !missingPlayers.isEmpty {
                            Text("Готовы: \(gwentPlayerList(readyPlayers)) · Ждем: \(gwentPlayerList(missingPlayers))")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }
                        HStack {
                            Button {
                                showGwentTable = true
                            } label: {
                                Label("Подготовка", systemImage: "rectangle.stack.badge.play")
                                    .frame(maxWidth: .infinity)
                            }
                            .buttonStyle(.borderedProminent)
                            .disabled(!activeGwentCanStart(root))

                            Button {
                                Task {
                                    await model.refusePvpChallenge(
                                        id: challenge.string("challenge_id"),
                                        reason: gwentRefusalReason
                                    )
                                }
                            } label: {
                                Label("Отказ", systemImage: "xmark.circle")
                                    .frame(maxWidth: .infinity)
                            }
                            .buttonStyle(.bordered)
                            .disabled(!activeGwentCanStart(root))
                        }
                    }
                } else {
                    Text("Активного вызова нет. Брось вызов выше или обнови состояние.")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                }
            } else {
                Text("Обнови столы в Wi-Fi зоне, чтобы увидеть свой вызов или матч.")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
            }
        }
        .cardStyle()
    }

    private var gwentStateRoot: [String: JSONValue]? {
        if let root = model.pvpPlayerState?.objectValue {
            return root
        }
        return model.lastPvpActionResult?.objectValue
    }

    private func gwentChallengeObject(_ root: [String: JSONValue]) -> [String: JSONValue]? {
        if let activeChallenge = root.object("active_challenge") {
            return activeChallenge
        }
        if let challenge = root.object("challenge") {
            return challenge
        }
        return root["challenge_id"] == nil ? nil : root
    }

    private func gwentChallengeReadyPlayers(_ challenge: [String: JSONValue]) -> [String] {
        challenge.object("prep")?.arrayStrings("ready_players") ?? []
    }

    private func gwentChallengeMissingPlayers(_ challenge: [String: JSONValue]) -> [String] {
        if let missing = challenge.object("prep")?.arrayStrings("missing_players"), !missing.isEmpty {
            return missing
        }
        let ready = Set(gwentChallengeReadyPlayers(challenge))
        return [challenge.string("challenger_id"), challenge.string("target_id")]
            .filter { !$0.isEmpty && !ready.contains($0) }
    }

    private func gwentMatchObject(_ root: [String: JSONValue]) -> [String: JSONValue]? {
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

    private func gwentRoundObject(_ root: [String: JSONValue]) -> [String: JSONValue]? {
        root.object("current_round") ?? root.object("round")
    }

    private func gwentRoundState(_ root: [String: JSONValue]) -> [String: JSONValue]? {
        if let round = gwentRoundObject(root) {
            return round.object("round_state") ?? round
        }
        return root.object("round_state")
    }

    private func activeGwentHand(_ root: [String: JSONValue]) -> [String] {
        let endpointHand = root.arrayStrings("player_hand")
        if !endpointHand.isEmpty {
            return endpointHand
        }
        guard let playerId = model.player?.playerId,
              let deckState = gwentMatchObject(root)?.object("deck_state")
        else { return [] }
        return deckState.object(playerId)?.arrayStrings("hand") ?? []
    }

    private func activeGwentRoundNumber(_ root: [String: JSONValue]) -> Int {
        if let legal = root.object("legal_actions"), legal.int("round_number") > 0 {
            return legal.int("round_number")
        }
        if let round = gwentRoundObject(root), round.int("round_number") > 0 {
            return round.int("round_number")
        }
        return 1
    }

    private func activeGwentCanStart(_ root: [String: JSONValue]) -> Bool {
        if let legal = root.object("legal_actions") {
            return jsonBool(legal, key: "can_start")
        }
        guard let challenge = gwentChallengeObject(root) else { return false }
        return ["assigned", "queued", "deferred"].contains(challenge.string("status"))
    }

    private func activeGwentCanPlay(_ root: [String: JSONValue]) -> Bool {
        if let legal = root.object("legal_actions") {
            return jsonBool(legal, key: "can_play_card")
        }
        guard let playerId = model.player?.playerId,
              let match = gwentMatchObject(root),
              match.string("status", default: "active") != "finished"
        else { return false }
        let ready = gwentRoundState(root)?.arrayStrings("ready_players") ?? []
        return !ready.contains(playerId)
    }

    private func activeGwentPlayerSubmitted(_ root: [String: JSONValue]) -> Bool {
        if let round = gwentRoundObject(root), jsonBool(round, key: "player_submitted") {
            return true
        }
        guard let playerId = model.player?.playerId else { return false }
        return gwentRoundState(root)?.arrayStrings("ready_players").contains(playerId) ?? false
    }

    private func activeGwentBlockReason(_ root: [String: JSONValue]) -> String {
        if let match = gwentMatchObject(root), match.string("status") == "awaiting_finish" {
            return "раунды завершены"
        }
        if let round = gwentRoundState(root), round.string("status") == "needs_master_review" {
            return "нужна проверка мастера"
        }
        return "стол ожидает обновления"
    }

    private func jsonBool(_ object: [String: JSONValue], key: String) -> Bool {
        guard let value = object[key] else { return false }
        if case .bool(let boolValue) = value {
            return boolValue
        }
        return value.stringValue == "true"
    }

    private var pvpTablesCard: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Игровые столы")
                .font(.headline)
            if let throttle = model.pvpTables?.throttle {
                Text(pvpThrottleSummary(throttle))
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            if let tables = model.pvpTables?.tables {
                Text("Доступно записей: \(tables.count)")
                ForEach(Array(tables.prefix(5).enumerated()), id: \.offset) { _, table in
                    VStack(alignment: .leading, spacing: 3) {
                        Text(pvpTableTitle(table))
                            .font(.subheadline.bold())
                        Text(pvpTableDetail(table))
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                    .padding(.vertical, 3)
                }
            } else {
                Text("Обнови состояние, когда iPhone в Wi-Fi зоне.")
                    .foregroundStyle(.secondary)
            }
            if let queued = model.pvpTables?.queuedChallenges, !queued.isEmpty {
                Divider()
                Text("Ожидают старта")
                    .font(.subheadline.bold())
                ForEach(Array(queued.prefix(5).enumerated()), id: \.offset) { _, challenge in
                    VStack(alignment: .leading, spacing: 3) {
                        Text(pvpChallengeTitle(challenge))
                            .font(.subheadline.bold())
                        Text(pvpChallengeDetail(challenge))
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                    .padding(.vertical, 3)
                }
            } else {
                Text("Ожидающих вызовов нет")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
        }
        .cardStyle()
    }

    private var gwentChallengeCard: some View {
        let opponents = gwentOpponentOptions
        let stakes = gwentStakeOptions
        let challengeTokens = gwentChallengeTokens

        return VStack(alignment: .leading, spacing: 10) {
            HStack {
                Text("Бросить вызов")
                    .font(.headline)
                Spacer()
                Label("\(challengeTokens)", systemImage: "seal.fill")
                    .font(.caption.bold())
                    .foregroundStyle(challengeTokens > 0 ? .yellow : .secondary)
            }

            if challengeTokens <= 0 {
                Text("Нет жетонов вызова. Мастер должен открыть акт, прежде чем можно создать PvP.")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

            Text("Ставкой может быть золото, карта, предмет, артефакт или зелье из инвентаря.")
                .font(.caption)
                .foregroundStyle(.secondary)

            if opponents.isEmpty {
                Text("На сервере нет доступных ведьмаков или чародеек для вызова.")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
            } else {
                Picker("Соперник", selection: $gwentTargetId) {
                    ForEach(opponents) { player in
                        Text(player.displayName).tag(player.playerId)
                    }
                }
                .pickerStyle(.menu)

                if let selectedOpponent = opponents.first(where: { $0.playerId == gwentTargetId }) {
                    Text("\(roleLabel(selectedOpponent.roleType)) · \(selectedOpponent.reputationLabel)")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }

            Divider()

            if stakes.isEmpty {
                Text("Нет золота, карт, предметов, артефактов или зелий, которые можно поставить.")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
            } else {
                Picker("Ставка", selection: gwentStakeSelection) {
                    ForEach(stakes) { option in
                        Text(option.title).tag(option.id)
                    }
                }
                .pickerStyle(.menu)

                if let selectedStake = selectedGwentStakeOption {
                    HStack {
                        Image(systemName: assetIcon(selectedStake.assetType))
                        VStack(alignment: .leading, spacing: 2) {
                            Text(selectedStake.title)
                                .font(.subheadline.bold())
                            Text(selectedStake.detail)
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }
                    }
                    .padding(8)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(.regularMaterial)
                    .clipShape(RoundedRectangle(cornerRadius: 8))
                }

                if gwentStakeType == "gold" {
                    Stepper(
                        "Золото: \(gwentGoldStakeAmount)g",
                        value: $gwentGoldStakeAmount,
                        in: 1...gwentGoldStakeLimit
                    )
                    .font(.subheadline)
                }
            }

            Button {
                Task {
                    await model.createPvpChallenge(
                        targetId: gwentTargetId,
                        stakeAssetType: gwentStakeType,
                        stakeAssetId: gwentStakeId,
                        stakeQuantity: selectedGwentStakeOption?.quantity ?? 1
                    )
                    if model.errorMessage == nil {
                        showGwentTable = true
                    }
                }
            } label: {
                Label("Бросить вызов", systemImage: "flag.checkered")
                    .frame(maxWidth: .infinity)
            }
            .buttonStyle(.borderedProminent)
            .disabled(!canCreateGwentChallenge)
        }
        .cardStyle()
        .onAppear {
            normalizeGwentChallengeDefaults()
        }
        .onChange(of: model.snapshot?.snapshotVersion ?? "") { _ in
            normalizeGwentChallengeDefaults()
        }
        .onChange(of: model.pvpPlayerState) { _ in
            normalizeGwentChallengeDefaults()
        }
    }

    private var gwentOpponentOptions: [GwentOpponentOption] {
        guard let player = model.player else { return [] }
        let serverOptions = (model.pvpPlayerState?.objectValue?.array("opponents") ?? [])
            .compactMap(\.objectValue)
            .compactMap { GwentOpponentOption(object: $0) }
            .filter { $0.playerId != player.playerId }
        if !serverOptions.isEmpty {
            return serverOptions.sorted { $0.displayName < $1.displayName }
        }
        return (model.snapshot?.players ?? [])
            .filter { candidate in
                candidate.playerId != player.playerId
                    && ["witcher", "sorceress"].contains(candidate.roleType.lowercased())
            }
            .map { GwentOpponentOption(player: $0) }
            .sorted { $0.displayName < $1.displayName }
    }

    private var gwentStakeOptions: [GwentStakeOption] {
        let assetOptions = (ownedAssets.compactMap(gwentStakeOption) + ownedPotions.compactMap(gwentPotionStakeOption))
            .sorted { lhs, rhs in
                if lhs.assetType == rhs.assetType {
                    return lhs.title < rhs.title
                }
                return lhs.assetType < rhs.assetType
            }
        guard let player = model.player, player.gold > 0 else {
            return assetOptions
        }
        let amount = min(max(1, gwentGoldStakeAmount), max(1, player.gold))
        return [
            GwentStakeOption(
                assetType: "gold",
                assetId: "gold",
                quantity: amount,
                title: "\(amount)g",
                detail: "золото · доступно \(player.gold)g"
            )
        ] + assetOptions
    }

    private var selectedGwentStakeOption: GwentStakeOption? {
        gwentStakeOptions.first {
            $0.assetType == gwentStakeType && $0.assetId == gwentStakeId
        }
    }

    private var canCreateGwentChallenge: Bool {
        gwentChallengeTokens > 0
            && gwentOpponentOptions.contains { $0.playerId == gwentTargetId }
            && selectedGwentStakeOption != nil
    }

    private var gwentChallengeTokens: Int {
        guard let root = model.pvpPlayerState?.objectValue else { return 0 }
        return root.int("challenge_tokens")
    }

    private var gwentStakeSelection: Binding<String> {
        Binding(
            get: { "\(gwentStakeType)|\(gwentStakeId)" },
            set: { selection in
                let parts = selection.split(separator: "|", maxSplits: 1).map(String.init)
                guard parts.count == 2 else { return }
                gwentStakeType = parts[0]
                gwentStakeId = parts[1]
            }
        )
    }

    private func normalizeGwentChallengeDefaults() {
        let opponents = gwentOpponentOptions
        if !opponents.contains(where: { $0.playerId == gwentTargetId }) {
            gwentTargetId = opponents.first?.playerId ?? ""
        }

        let stakes = gwentStakeOptions
        if !stakes.contains(where: { $0.assetType == gwentStakeType && $0.assetId == gwentStakeId }) {
            if let firstStake = stakes.first {
                gwentStakeType = firstStake.assetType
                gwentStakeId = firstStake.assetId
            } else {
                gwentStakeId = ""
            }
        }
        gwentGoldStakeAmount = min(max(1, gwentGoldStakeAmount), gwentGoldStakeLimit)
    }

    private func gwentStakeOption(_ row: SnapshotRow) -> GwentStakeOption? {
        guard let player = model.player,
              row.string("owner_player_id") == player.playerId
        else { return nil }

        let assetType = row.string("asset_type").lowercased()
        let assetId = row.string("asset_id")
        let status = row.string("status", default: "active").lowercased()
        let quantity = row.int("quantity", default: 1)
        guard !assetId.isEmpty,
              quantity > 0,
              ["item", "card", "artifact"].contains(assetType),
              ["active", "available"].contains(status)
        else { return nil }

        let title = assetDisplayName(assetId)
        let detail = "\(assetTypeLabel(assetType)) · x\(quantity)"
        return GwentStakeOption(
            assetType: assetType,
            assetId: assetId,
            quantity: 1,
            title: title,
            detail: detail
        )
    }

    private func gwentPotionStakeOption(_ row: SnapshotRow) -> GwentStakeOption? {
        guard let player = model.player,
              row.string("player_id") == player.playerId
        else { return nil }

        let potionId = row.string("potion_id")
        let quantity = row.int("quantity", default: 1)
        guard !potionId.isEmpty, quantity > 0 else { return nil }

        return GwentStakeOption(
            assetType: "potion",
            assetId: potionId,
            quantity: 1,
            title: assetDisplayName(potionId),
            detail: "зелье из инвентаря · x\(quantity)"
        )
    }

    private var gwentGoldStakeLimit: Int {
        max(1, model.player?.gold ?? 1)
    }

    private func pvpThrottleSummary(_ value: JSONValue) -> String {
        guard let object = value.objectValue else {
            return "Лимит столов: \(value.displayText)"
        }
        let mode = object.string("mode", default: "active")
        let maxTables = object.int("max_tables", default: 0)
        return "Режим: \(gwentStatusLabel(mode)) · столов доступно: \(maxTables)"
    }

    private func pvpTableTitle(_ value: JSONValue) -> String {
        guard let object = value.objectValue else {
            return "Стол Гвинта"
        }
        let zone = object.string("zone_name")
        if !zone.isEmpty {
            return zoneLabel(zone)
        }
        return "Стол \(shortGameCode(object.string("table_id")))"
    }

    private func pvpTableDetail(_ value: JSONValue) -> String {
        guard let object = value.objectValue else {
            return value.displayText
        }
        var parts = [gwentStatusLabel(object.string("status", default: "unknown"))]
        let challengeId = object.string("current_challenge_id")
        if !challengeId.isEmpty {
            parts.append("вызов \(shortGameCode(challengeId))")
        }
        let matchId = object.string("current_match_id")
        if !matchId.isEmpty {
            parts.append("матч \(shortGameCode(matchId))")
        }
        return parts.joined(separator: " · ")
    }

    private func pvpChallengeTitle(_ value: JSONValue) -> String {
        guard let object = value.objectValue else {
            return "Вызов ожидает"
        }
        return "\(gwentPlayerName(object.string("challenger_id"))) против \(gwentPlayerName(object.string("target_id")))"
    }

    private func pvpChallengeDetail(_ value: JSONValue) -> String {
        guard let object = value.objectValue else {
            return value.displayText
        }
        var parts = [
            gwentStatusLabel(object.string("status", default: "queued")),
            "вызов \(shortGameCode(object.string("challenge_id")))"
        ]
        let zone = object.string("assigned_zone")
        if !zone.isEmpty {
            parts.append(zoneLabel(zone))
        }
        if let stake = object.object("stake_json") {
            let assetType = stake.string("asset_type")
            let assetId = stake.string("asset_id")
            if assetType == "gold" {
                parts.append("ставка: \(stake.int("quantity", default: stake.int("amount", default: 1)))g")
            } else if !assetId.isEmpty {
                parts.append("ставка: \(assetTypeLabel(assetType)) \(readableIdentifier(assetId, droppingPrefixes: ["item_", "card_", "artifact_"]))")
            }
        }
        return parts.joined(separator: " · ")
    }

    private func assetTypeLabel(_ assetType: String) -> String {
        switch assetType.lowercased() {
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
        case "quest_object":
            return "квестовый предмет"
        case "strategic", "strategic_support":
            return "стратегия"
        case "final_evidence":
            return "финальная улика"
        case "pvp_stake":
            return "ставка"
        case "gold":
            return "золото"
        default:
            return readableIdentifier(assetType)
        }
    }

    private func gwentPlayerDeckState(playerId: String, state: [String: JSONValue]) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text(gwentPlayerName(playerId))
                    .font(.caption.bold())
                Spacer()
                Text(state.string("leader_used", default: "false") == "true" ? "Лидер использован" : "Лидер готов")
                    .font(.caption2.bold())
                    .foregroundStyle(.secondary)
            }

            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 8) {
                    let hand = state.arrayStrings("hand")
                    if hand.isEmpty {
                        emptyCardPlaceholder("рука пуста")
                    } else {
                        ForEach(Array(hand.prefix(8).enumerated()), id: \.offset) { _, cardId in
                            gwentCompactCard(cardId: cardId)
                        }
                    }
                }
            }

            let graveyard = state.arrayStrings("graveyard")
            if !graveyard.isEmpty {
                Text("Сброс: \(compactCards(graveyard))")
                    .font(.caption2)
                    .foregroundStyle(.secondary)
            }
        }
        .padding(8)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(.regularMaterial)
        .clipShape(RoundedRectangle(cornerRadius: 8))
    }

    private func gwentBoardPlayer(playerId: String, board: [String: JSONValue]) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text(gwentPlayerName(playerId))
                    .font(.caption.bold())
                Spacer()
                Text("Сила \(gwentRowTotal(board.array("melee") + board.array("ranged") + board.array("siege")))")
                    .font(.caption2.bold())
                    .foregroundStyle(.secondary)
            }
            gwentBoardRow(rowId: "melee", title: gwentRowLabel("melee"), cards: board.array("melee"))
            gwentBoardRow(rowId: "ranged", title: gwentRowLabel("ranged"), cards: board.array("ranged"))
            gwentBoardRow(rowId: "siege", title: gwentRowLabel("siege"), cards: board.array("siege"))
        }
        .padding(10)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(.regularMaterial)
        .clipShape(RoundedRectangle(cornerRadius: 8))
    }

    private func gwentBoardRow(rowId: String, title: String, cards: [JSONValue]) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Text(title)
                    .font(.caption2.bold())
                Spacer()
                Text("Сумма \(gwentRowTotal(cards))")
                    .font(.caption2.bold())
                    .foregroundStyle(.secondary)
            }

            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 8) {
                    if cards.isEmpty {
                        emptyBoardSlot(rowId)
                    } else {
                        ForEach(Array(cards.prefix(8).enumerated()), id: \.offset) { _, value in
                            gwentBoardCardTile(value)
                        }
                    }
                }
            }
        }
        .padding(8)
        .background(gwentRowColor(rowId).opacity(0.11))
        .overlay(
            RoundedRectangle(cornerRadius: 8)
                .stroke(gwentRowColor(rowId).opacity(0.25), lineWidth: 1)
        )
        .clipShape(RoundedRectangle(cornerRadius: 8))
    }

    private func gwentBoardCardTile(_ value: JSONValue) -> some View {
        let cardId = gwentCardId(value)
        let meta = gwentCardMeta(cardId)
        let strength = gwentCardStrength(value)
        let row = meta?.row ?? value.objectValue?.string("row") ?? "card"
        let rarity = meta?.rarity ?? value.objectValue?.string("rarity") ?? ""

        return VStack(alignment: .leading, spacing: 5) {
            HStack {
                Text(strength.map(String.init) ?? "-")
                    .font(.headline.bold())
                Spacer()
                Image(systemName: gwentRowIcon(row))
                    .font(.caption)
                    .foregroundStyle(gwentRowColor(row))
            }
            Text(gwentCardTitle(cardId))
                .font(.caption2.bold())
                .lineLimit(2)
                .minimumScaleFactor(0.68)
            Text(rarity.isEmpty ? gwentRowLabel(row) : "\(gwentRowLabel(row)) · \(gwentRarityLabel(rarity))")
                .font(.caption2)
                .foregroundStyle(.secondary)
        }
        .padding(8)
        .frame(width: 96, height: 112, alignment: .topLeading)
        .background(.thinMaterial)
        .overlay(
            RoundedRectangle(cornerRadius: 8)
                .stroke(gwentRowColor(row).opacity(0.45), lineWidth: 1)
        )
        .clipShape(RoundedRectangle(cornerRadius: 8))
    }

    private func gwentCompactCard(cardId: String) -> some View {
        let meta = gwentCardMeta(cardId)
        let row = meta?.row ?? "card"
        return VStack(alignment: .leading, spacing: 4) {
            Text(meta.map { String($0.strength) } ?? "-")
                .font(.caption.bold())
                .foregroundStyle(gwentRowColor(row))
            Text(gwentCardTitle(cardId))
                .font(.caption2.bold())
                .lineLimit(2)
                .minimumScaleFactor(0.7)
        }
        .padding(7)
        .frame(width: 82, height: 72, alignment: .topLeading)
        .background(gwentRowColor(row).opacity(0.1))
        .overlay(
            RoundedRectangle(cornerRadius: 8)
                .stroke(gwentRowColor(row).opacity(0.35), lineWidth: 1)
        )
        .clipShape(RoundedRectangle(cornerRadius: 8))
    }

    private func emptyBoardSlot(_ rowId: String) -> some View {
        Text("пусто")
            .font(.caption2)
            .foregroundStyle(.secondary)
            .frame(width: 96, height: 54)
            .overlay(
                RoundedRectangle(cornerRadius: 8)
                    .stroke(gwentRowColor(rowId).opacity(0.25), style: StrokeStyle(lineWidth: 1, dash: [4, 4]))
            )
    }

    private func emptyCardPlaceholder(_ text: String) -> some View {
        Text(text)
            .font(.caption2)
            .foregroundStyle(.secondary)
            .frame(width: 82, height: 72)
            .overlay(
                RoundedRectangle(cornerRadius: 8)
                    .stroke(.secondary.opacity(0.25), style: StrokeStyle(lineWidth: 1, dash: [4, 4]))
            )
    }

    private func gwentCardId(_ value: JSONValue) -> String {
        if let object = value.objectValue {
            return object.string("card_id", default: "card")
        }
        return value.stringValue ?? "card"
    }

    private func gwentCardStrength(_ value: JSONValue) -> Int? {
        if let object = value.objectValue, let strength = object["strength"]?.intValue {
            let cardId = gwentCardId(value)
            if strength == 0,
               let meta = gwentCardMeta(cardId),
               meta.type.lowercased() == "unit",
               meta.strength > 0 {
                return meta.strength
            }
            return strength
        }
        return gwentCardMeta(gwentCardId(value))?.strength
    }

    private func gwentCardMeta(_ cardId: String) -> GwentCard? {
        let snapshotCard = model.snapshot?.gwentCards.first { $0.cardId == cardId }
        if let snapshotCard, !snapshotCard.displayName.isEmpty {
            return snapshotCard
        }
        return GwentStaticCatalog.card(cardId) ?? snapshotCard
    }

    private func gwentRowTotal(_ cards: [JSONValue]) -> Int {
        cards.reduce(0) { partial, value in
            partial + (gwentCardStrength(value) ?? 0)
        }
    }

    private func gwentCardTitle(_ cardId: String) -> String {
        if let meta = gwentCardMeta(cardId), !meta.displayName.isEmpty {
            return meta.displayName
        }
        let knownTitles = [
            "gwent_leader_wolf": "Наставник Школы Волка",
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

    private func gwentEffectSummary(_ card: GwentCard) -> String {
        let labels = gwentCardEffects(card).map(gwentEffectLabel)
        return labels.isEmpty ? "без эффекта" : labels.joined(separator: " · ")
    }

    private func gwentCardEffects(_ card: GwentCard) -> [String] {
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

    private func gwentCardBadgeText(_ card: GwentCard) -> String {
        let type = card.type.lowercased()
        let row = card.row.lowercased()
        if type == "leader" || row == "leader" {
            return "Л"
        }
        if row == "weather" {
            return "П"
        }
        if type == "special" || row == "special" {
            return "О"
        }
        return "\(card.strength)"
    }

    private func gwentCardBadgeColor(_ card: GwentCard) -> Color {
        let type = card.type.lowercased()
        let row = card.row.lowercased()
        if type == "leader" || row == "leader" || gwentCardEffects(card).contains("hero") {
            return .yellow
        }
        if row == "weather" {
            return .cyan
        }
        if type == "special" || row == "special" {
            return .orange
        }
        return .white
    }

    private func gwentEffectIcon(_ effect: String) -> String {
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

    private func gwentEffectColor(_ effect: String) -> Color {
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

    private func gwentCardEffectRuleText(_ effect: String, card: GwentCard) -> String {
        let rule = gwentEffectRulesText(effect)
        if !rule.isEmpty {
            return rule
        }
        if effect.hasPrefix("leader_"), !card.effectText.isEmpty {
            return "Один раз за партию: \(card.effectText)"
        }
        return card.effectText.isEmpty ? "Особое правило этой карты применяется движком гвинта." : card.effectText
    }

    private func gwentEffectRulesText(_ effect: String) -> String {
        switch effect.lowercased() {
        case "none":
            return "У карты нет отдельной способности: важны сила, ряд и фракция."
        case "hero":
            return "Не подвержен погоде, командирскому рогу, казни и большинству способностей."
        case "spy":
            return "Играется на сторону соперника; владелец шпиона добирает две карты."
        case "medic":
            return "Выбирает обычную карту из вашего сброса и сразу разыгрывает ее."
        case "muster":
            return "Вытаскивает из руки и колоды все карты той же группы."
        case "morale":
            return "Дает +1 всем другим обычным картам в этом же ряду."
        case "bond", "tight_bond":
            return "Одинаковые карты этой группы усиливают друг друга: две дают x2, три дают x3."
        case "agile":
            return "Может быть сыграна в ближний или дальний ряд."
        case "weather_melee", "biting_frost":
            return "Сила обычных карт ближнего ряда становится 1. Герои не меняются."
        case "weather_ranged", "impenetrable_fog":
            return "Сила обычных карт дальнего ряда становится 1. Герои не меняются."
        case "weather_siege", "torrential_rain":
            return "Сила обычных карт осадного ряда становится 1. Герои не меняются."
        case "clear_weather":
            return "Снимает все погодные эффекты со стола."
        case "commanders_horn":
            return "Удваивает силу обычных карт выбранного ряда. Герои не меняются."
        case "decoy":
            return "Заменяет вашу обычную карту на столе и возвращает ее в руку. Героя вернуть нельзя."
        case "scorch":
            return "Уничтожает самые сильные обычные карты на столе, если их сила 10 или выше."
        case "scorch_melee":
            return "Уничтожает сильнейшие обычные карты ближнего ряда соперника, если сумма ряда 10 или выше."
        case "scorch_ranged":
            return "Уничтожает сильнейшие обычные карты дальнего ряда соперника, если сумма ряда 10 или выше."
        case "scorch_siege":
            return "Уничтожает сильнейшие обычные карты осадного ряда соперника, если сумма ряда 10 или выше."
        case "leader_foltest_fog":
            return "Один раз за партию: достает из колоды Непроницаемый туман и сразу применяет его."
        case "leader_foltest_clear_weather":
            return "Один раз за партию: снимает все погодные эффекты со стола."
        case "leader_foltest_siege_horn":
            return "Один раз за партию: удваивает силу вашего осадного ряда как командирский рог."
        case "leader_foltest_siege_scorch":
            return "Один раз за партию: казнит сильнейшие обычные карты осадного ряда соперника при сумме ряда 10+."
        case "leader_emhyr_spy_hand":
            return "Один раз за партию: смотрит три случайные карты в руке соперника."
        case "leader_emhyr_rain":
            return "Один раз за партию: достает из колоды Ливень и сразу применяет его."
        case "leader_emhyr_graveyard_theft":
            return "Один раз за партию: берет одну обычную карту из сброса соперника в вашу руку."
        case "leader_emhyr_cancel_leader":
            return "Один раз за партию: запрещает сопернику использовать способность лидера."
        case "leader_francesca_draw":
            return "Пассивно: дает одну дополнительную карту в начале партии."
        case "leader_francesca_frost":
            return "Один раз за партию: достает из колоды Мороз и сразу применяет его."
        case "leader_francesca_melee_scorch":
            return "Один раз за партию: казнит сильнейшие обычные карты ближнего ряда соперника при сумме ряда 10+."
        case "leader_francesca_ranged_horn":
            return "Один раз за партию: удваивает силу вашего дальнего ряда как командирский рог."
        case "leader_eredin_graveyard_return":
            return "Один раз за партию: возвращает одну обычную карту из вашего сброса в руку."
        case "leader_eredin_melee_horn":
            return "Один раз за партию: удваивает силу вашего ближнего ряда как командирский рог."
        case "leader_eredin_discard_draw":
            return "Один раз за партию: сбрасывает две карты из руки и добирает одну карту из колоды."
        case "leader_eredin_weather":
            return "Один раз за партию: достает из колоды первую погодную карту и сразу применяет ее."
        case "leader_crach_graveyard_shuffle":
            return "Один раз за партию: замешивает карты из сброса обратно в колоду."
        default:
            return ""
        }
    }

    private var gwentTypeMechanics: [GwentMechanicInfo] {
        [
            GwentMechanicInfo(
                id: "type_unit",
                title: "Отряд",
                detail: "Карта с силой. Играется в свой ряд и участвует в счете раунда.",
                icon: "shield.lefthalf.filled",
                color: .white.opacity(0.56)
            ),
            GwentMechanicInfo(
                id: "type_special",
                title: "Особая карта",
                detail: "Не считается отрядом: меняет стол, ряд или другую карту.",
                icon: "sparkles",
                color: .orange
            ),
            GwentMechanicInfo(
                id: "type_leader",
                title: "Лидер",
                detail: "Отдельная способность колоды. Обычно применяется один раз за партию.",
                icon: "crown.fill",
                color: .yellow
            ),
            GwentMechanicInfo(
                id: "row_melee",
                title: "Ближний ряд",
                detail: "Для мечников, пехоты и части гибких карт.",
                icon: gwentRowIcon("melee"),
                color: gwentRowColor("melee")
            ),
            GwentMechanicInfo(
                id: "row_ranged",
                title: "Дальний ряд",
                detail: "Для лучников, магов и части гибких карт.",
                icon: gwentRowIcon("ranged"),
                color: gwentRowColor("ranged")
            ),
            GwentMechanicInfo(
                id: "row_siege",
                title: "Осадный ряд",
                detail: "Для баллист, катапульт и осадных машин.",
                icon: gwentRowIcon("siege"),
                color: gwentRowColor("siege")
            )
        ]
    }

    private var gwentAbilityMechanics: [GwentMechanicInfo] {
        [
            "hero",
            "spy",
            "medic",
            "muster",
            "tight_bond",
            "morale",
            "agile",
            "commanders_horn",
            "decoy",
            "scorch",
            "weather_melee",
            "weather_ranged",
            "weather_siege",
            "clear_weather"
        ].map { effect in
            GwentMechanicInfo(
                id: effect,
                title: gwentEffectLabel(effect),
                detail: gwentEffectRulesText(effect),
                icon: gwentEffectIcon(effect),
                color: gwentEffectColor(effect)
            )
        }
    }

    private func gwentRowLabel(_ row: String) -> String {
        switch row.lowercased() {
        case "melee":
            return "Ближний ряд"
        case "ranged":
            return "Дальний ряд"
        case "siege":
            return "Осадный ряд"
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

    private func gwentRarityLabel(_ rarity: String) -> String {
        switch rarity.lowercased() {
        case "common":
            return "Обычная"
        case "uncommon":
            return "Необычная"
        case "rare":
            return "Редкая"
        case "legendary":
            return "Легендарная"
        default:
            return readableIdentifier(rarity)
        }
    }

    private func gwentStatusLabel(_ status: String) -> String {
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

    private func gwentPlayerList(_ playerIds: [String]) -> String {
        if playerIds.isEmpty {
            return "никого"
        }
        return playerIds.map(gwentPlayerName).joined(separator: ", ")
    }

    private func gwentPlayerName(_ playerId: String) -> String {
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

    private func shortGameCode(_ value: String) -> String {
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

    private func zoneLabel(_ zone: String) -> String {
        switch zone.lowercased() {
        case "main_house_table":
            return "Главный дом, стол"
        case "lord_hall", "main_house":
            return "Главный дом"
        case "yard":
            return "Двор"
        default:
            return readableIdentifier(zone)
        }
    }

    private func readableIdentifier(_ value: String, droppingPrefixes prefixes: [String] = []) -> String {
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

    private func gwentRowColor(_ row: String) -> Color {
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

    private func gwentRowIcon(_ row: String) -> String {
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

    private func gwentPlayerIds(_ object: [String: JSONValue]) -> [String] {
        object.keys
            .filter { $0.hasPrefix("p_") }
            .sorted()
    }

    private func compactCards(_ cards: [String]) -> String {
        if cards.isEmpty {
            return "пусто"
        }
        let visible = cards.prefix(6).map(gwentCardTitle).joined(separator: ", ")
        return cards.count > 6 ? "\(visible), +\(cards.count - 6)" : visible
    }

    private var queue: some View {
        NavigationStack {
            List {
                Section("Состояние") {
                    Label(syncStateLabel(model.syncState), systemImage: syncStateIcon(model.syncState))
                        .font(.headline)
                    Text(model.serverConnectionLabel)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    Text(model.pendingEvents.isEmpty ? "На этом iPhone нет неотправленных событий." : "На этом iPhone ждут отправки: \(model.pendingEvents.count)")
                        .font(.caption)
                        .foregroundStyle(.secondary)

                    if let info = model.infoMessage {
                        Text(info)
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                    if let error = model.errorMessage {
                        Text(error)
                            .font(.caption)
                            .foregroundStyle(.red)
                    }

                    Button {
                        Task { await model.checkServerHealth() }
                    } label: {
                        Label("Проверить связь", systemImage: "network")
                    }
                }

                Section("На телефоне") {
                    if model.pendingEvents.isEmpty {
                        Text("Все игровые события отправлены.")
                            .foregroundStyle(.secondary)
                    } else {
                        ForEach(model.pendingEvents) { event in
                            VStack(alignment: .leading, spacing: 4) {
                                Text(eventTitle(event))
                                    .font(.headline)
                                Text(eventDetail(event))
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                            }
                        }
                    }
                }

                Section {
                    Button {
                        Task { await model.syncPendingEvents() }
                    } label: {
                        Label("Отправить события", systemImage: "arrow.triangle.2.circlepath")
                    }
                    .disabled(model.pendingEvents.isEmpty)
                }
            }
            .navigationTitle("Связь")
        }
    }

    private func eventTitle(_ event: QueuedEvent) -> String {
        switch event.eventType {
        case "pve_completed":
            return "Результат сцены"
        case "order_submission":
            return "Сдача заказа"
        case "qr_attempt":
            return "Проверка QR"
        case "act_unlocked_offline":
            return "Открытие акта"
        default:
            return readableIdentifier(event.eventType)
        }
    }

    private func eventDetail(_ event: QueuedEvent) -> String {
        switch event.eventType {
        case "pve_completed":
            let qr = qrDisplayName(event.payload.string("manual_code", default: event.payload.string("qr_id")))
            let result = event.payload.string("result", default: event.payload.string("outcome"))
            return "\(qr) · \(pveResultLabel(result)) · \(eventSyncDetail(event))"
        case "order_submission":
            let orderId = event.payload.string("order_id")
            return "\(orderDisplayName(orderId)) · подтверждение сохранено · \(eventSyncDetail(event))"
        case "qr_attempt":
            let code = event.payload.string("manual_code", default: event.payload.string("normalized_code"))
            let reason = event.payload.string("review_reason")
            let localReason = reason.isEmpty ? "" : " · \(reviewReasonLabel(reason))"
            return "\(code)\(localReason) · \(eventSyncDetail(event))"
        case "act_unlocked_offline":
            return "\(actDisplayName(event.payload.string("act_id"))) · открыто на этом телефоне · \(eventSyncDetail(event))"
        default:
            return "Событие \(event.clientSequence) · \(eventSyncDetail(event))"
        }
    }

    private func eventSyncDetail(_ event: QueuedEvent) -> String {
        let label: String
        switch event.syncStatus.lowercased() {
        case "pending":
            label = "ждет связи"
        case "sync_error":
            label = "ошибка отправки"
        case "pending_master_approval":
            label = "на подтверждении награды"
        case "needs_master_review", "needs_review", "review", "queued_for_review":
            label = "у мастера на проверке"
        case "rejected":
            label = "отклонено"
        case "accepted":
            label = "принято"
        case "duplicate":
            label = "уже было принято"
        default:
            label = readableIdentifier(event.syncStatus)
        }
        guard let reason = event.syncReason, !reason.isEmpty else {
            return label
        }
        return "\(label): \(reviewReasonLabel(reason))"
    }

    private func pveResultLabel(_ result: String) -> String {
        switch result.lowercased() {
        case "success":
            return "успех"
        case "partial_success":
            return "частичный успех"
        case "failure":
            return "провал"
        default:
            return readableIdentifier(result)
        }
    }

    private func reviewReasonLabel(_ reason: String) -> String {
        switch reason.lowercased() {
        case "unknown_qr":
            return "неизвестный QR, нужна проверка мастера"
        case "future_act_locked":
            return "будущий акт, нужна проверка мастера"
        case "missing_local_scenario":
            return "нет сцены в дневнике, нужна проверка мастера"
        default:
            return "\(readableIdentifier(reason)), нужна проверка мастера"
        }
    }

    private func qrDisplayName(_ code: String) -> String {
        if let qr = model.snapshot?.qrObjects.first(where: {
            $0.qrId.caseInsensitiveCompare(code) == .orderedSame
                || $0.manualCode.caseInsensitiveCompare(code) == .orderedSame
        }) {
            if let order = model.snapshot?.orders.first(where: { $0.objectId == qr.qrId }) {
                return orderTitle(order)
            }
            return readableIdentifier(qr.manualCode.isEmpty ? qr.qrId : qr.manualCode, droppingPrefixes: ["qr_"])
        }
        return readableIdentifier(code, droppingPrefixes: ["qr_"])
    }

    private func orderDisplayName(_ orderId: String) -> String {
        if let order = model.snapshot?.orders.first(where: { $0.orderId == orderId }) {
            return orderTitle(order)
        }
        return shortGameCode(orderId)
    }

    private var ownedAssets: [SnapshotRow] {
        guard let player = model.player else { return [] }
        return model.snapshot?.assetOwnership.filter {
            $0.string("owner_player_id") == player.playerId && $0.int("quantity") > 0
        } ?? []
    }

    private var ownedPotions: [SnapshotRow] {
        guard let player = model.player else { return [] }
        return model.snapshot?.potionInventory.filter {
            $0.string("player_id") == player.playerId && $0.int("quantity") > 0
        } ?? []
    }

    private var ownedMaterials: [SnapshotRow] {
        guard let player = model.player else { return [] }
        return model.snapshot?.materialInventory
            .filter { $0.string("player_id") == player.playerId && $0.int("quantity") > 0 }
            .sorted { assetDisplayName($0.string("material_id")) < assetDisplayName($1.string("material_id")) }
            ?? []
    }

    private var canUsePotionMarket: Bool {
        model.player?.roleType.lowercased() == "sorceress"
    }

    private var potionMarketRows: [SnapshotRow] {
        guard canUsePotionMarket else { return [] }
        return (model.snapshot?.potionMarket ?? [])
            .filter {
                $0.string("seller_role").lowercased() == "sorceress"
                    && $0.int("stock") > 0
            }
            .sorted {
                if $0.int("wholesale_cost") != $1.int("wholesale_cost") {
                    return $0.int("wholesale_cost") < $1.int("wholesale_cost")
                }
                return assetDisplayName($0.string("potion_id")) < assetDisplayName($1.string("potion_id"))
            }
    }

    private var materialMarketRows: [SnapshotRow] {
        (model.snapshot?.materialMarket ?? model.snapshot?.materialMarkets ?? [])
            .sorted { lhs, rhs in
                if materialMarketPrice(lhs) != materialMarketPrice(rhs) {
                    return materialMarketPrice(lhs) > materialMarketPrice(rhs)
                }
                return assetDisplayName(lhs.string("material_id")) < assetDisplayName(rhs.string("material_id"))
            }
    }

    private var cardMarketRows: [SnapshotRow] {
        let ownedIds = playerAvailableGwentCardIds
        return (model.snapshot?.cardMarket ?? [])
            .filter {
                $0.string("status").lowercased() != "owned"
                    && !ownedIds.contains($0.string("card_id"))
            }
            .sorted {
                if $0.int("unit_cost") != $1.int("unit_cost") {
                    return $0.int("unit_cost") < $1.int("unit_cost")
                }
                return gwentCardTitle($0.string("card_id")) < gwentCardTitle($1.string("card_id"))
            }
    }

    private var playerAvailableGwentCardIds: Set<String> {
        guard let player = model.player else { return [] }
        var ids = Set((model.snapshot?.gwentDecks ?? [])
            .filter { $0.playerId == player.playerId }
            .flatMap { [$0.leaderCardId] + $0.cardIds })
        ids.formUnion(runtimeGwentDecksForCurrentPlayer.flatMap { [$0.leaderCardId] + $0.cardIds })
        ids.formUnion(ownedRuntimeGwentCardIds)
        return ids
    }

    private var ownedRuntimeGwentCardIds: [String] {
        guard let player = model.player else { return [] }
        return model.snapshot?.assetOwnership.compactMap { row in
            row.string("owner_player_id") == player.playerId
                && row.string("asset_type").lowercased() == "card"
                && row.string("status", default: "active").lowercased() == "active"
                && row.int("quantity", default: 1) > 0
                ? row.string("asset_id")
                : nil
        } ?? []
    }

    private var runtimeGwentDecksForCurrentPlayer: [GwentDeck] {
        guard let playerId = model.player?.playerId else { return [] }
        return model.runtimeGwentDecks.filter { $0.playerId == playerId }
    }

    private var selectedMaterialMarket: SnapshotRow? {
        marketRow(materialId: selectedMarketMaterialId)
    }

    private var selectedMarketMaterialQuantity: Int {
        ownedMaterials.first { $0.string("material_id") == selectedMarketMaterialId }?.int("quantity") ?? 0
    }

    private var canSellSelectedMaterial: Bool {
        selectedMaterialMarket != nil && selectedMarketMaterialQuantity > 0 && materialSellQuantity > 0
    }

    private func marketRow(materialId: String) -> SnapshotRow? {
        materialMarketRows.first { $0.string("material_id") == materialId }
    }

    private func materialMarketPrice(_ row: SnapshotRow) -> Int {
        let current = row.int("current_price")
        return current > 0 ? current : row.int("base_price")
    }

    private func materialInventoryDetail(_ row: SnapshotRow, market: SnapshotRow?) -> String {
        let description = row.string("description")
        let price = market.map(materialMarketPrice) ?? 0
        if price > 0 {
            return description.isEmpty ? "Рынок берет по \(price)g." : "\(description) · рынок \(price)g."
        }
        return description
    }

    private func normalizeMaterialMarketDefaults() {
        let rows = materialMarketRows
        if !rows.contains(where: { $0.string("material_id") == selectedMarketMaterialId }) {
            selectedMarketMaterialId = rows.first?.string("material_id") ?? ""
        }
        let available = selectedMarketMaterialQuantity
        materialSellQuantity = min(max(1, materialSellQuantity), max(1, available))
    }

    private func rawRowsCard(
        title: String,
        rows: [SnapshotRow],
        emptyText: String,
        titleKeys: [String],
        detailKeys: [String]
    ) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(title)
                .font(.headline)
            if rows.isEmpty {
                Text(emptyText)
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
            } else {
                ForEach(Array(rows.prefix(8).enumerated()), id: \.offset) { _, row in
                    VStack(alignment: .leading, spacing: 3) {
                        Text(rowTitle(row, keys: titleKeys))
                            .font(.subheadline.bold())
                        let details = rowDetails(row, keys: detailKeys)
                        if !details.isEmpty {
                            Text(details)
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }
                    }
                    .padding(.vertical, 3)
                }
            }
        }
        .cardStyle()
    }

    private func rowTitle(_ row: SnapshotRow, keys: [String]) -> String {
        for key in keys {
            let value = row.string(key)
            if !value.isEmpty {
                return value
            }
        }
        return row.sorted { $0.key < $1.key }.first.map { "\($0.key): \($0.value.displayText)" } ?? "row"
    }

    private func rowDetails(_ row: SnapshotRow, keys: [String]) -> String {
        keys.compactMap { key in
            guard let value = row[key]?.stringValue, !value.isEmpty else { return nil }
            return "\(key): \(value)"
        }
        .joined(separator: " / ")
    }

    private func actDisplayName(_ actId: String) -> String {
        switch actId.lowercased() {
        case "registration":
            return "Регистрация"
        case "act1":
            return "Акт I"
        case "act2":
            return "Акт II"
        case "act3":
            return "Акт III"
        case "final_lock":
            return "Финальный замок"
        case "final", "final_act", "act_final":
            return "Финал"
        case "debrief":
            return "Debrief"
        default:
            return readableIdentifier(actId)
        }
    }

    private func syncStateLabel(_ state: SyncState) -> String {
        switch state {
        case .offline:
            return "на телефоне"
        case .pending:
            return "ждет связи"
        case .syncing:
            return "отправляем"
        case .synced:
            return "синхронизировано"
        case .syncError:
            return "ошибка связи"
        case .needsReview:
            return "у мастера"
        }
    }

    private func syncStateIcon(_ state: SyncState) -> String {
        switch state {
        case .offline:
            return "iphone"
        case .pending:
            return "clock.badge.exclamationmark"
        case .syncing:
            return "arrow.triangle.2.circlepath"
        case .synced:
            return "checkmark.circle.fill"
        case .syncError:
            return "exclamationmark.triangle.fill"
        case .needsReview:
            return "person.badge.shield.checkmark"
        }
    }

    private func roleLabel(_ role: String) -> String {
        switch role {
        case "witcher":
            return "Ведьмак"
        case "sorceress":
            return "Чародейка"
        case "lord":
            return "Лорд"
        default:
            return readableIdentifier(role)
        }
    }

    private func pveSceneTypeLabel(_ sceneType: String) -> String {
        switch sceneType.lowercased() {
        case "monster_hunt":
            return "охота на чудовище"
        case "investigation":
            return "расследование"
        case "moral_choice":
            return "моральный выбор"
        case "puzzle", "check":
            return "испытание"
        case "order_object":
            return "объект заказа"
        default:
            return readableIdentifier(sceneType)
        }
    }
}

private enum InventoryMode: String, CaseIterable, Identifiable {
    case bag
    case market
    case trade

    var id: String { rawValue }

    var title: String {
        switch self {
        case .bag:
            return "Сумка"
        case .market:
            return "Рынок"
        case .trade:
            return "Обмен"
        }
    }
}

private struct GwentStakeOption: Identifiable, Equatable {
    let assetType: String
    let assetId: String
    let quantity: Int
    let title: String
    let detail: String

    var id: String {
        "\(assetType)|\(assetId)"
    }
}

private struct GwentOpponentOption: Identifiable, Equatable {
    let playerId: String
    let roleType: String
    let displayName: String
    let reputationLabel: String

    var id: String { playerId }

    init(playerId: String, roleType: String, displayName: String, reputationLabel: String) {
        self.playerId = playerId
        self.roleType = roleType
        self.displayName = displayName
        self.reputationLabel = reputationLabel
    }

    init(player: PlayerProfile) {
        self.init(
            playerId: player.playerId,
            roleType: player.roleType,
            displayName: player.displayName,
            reputationLabel: player.reputationLabel
        )
    }

    init?(object: [String: JSONValue]) {
        let playerId = object.string("player_id").trimmingCharacters(in: .whitespacesAndNewlines)
        guard !playerId.isEmpty else { return nil }

        let roleType = object.string("role_type").trimmingCharacters(in: .whitespacesAndNewlines)
        let displayName = object.string("display_name").trimmingCharacters(in: .whitespacesAndNewlines)
        let explicitReputation = object.string("reputation_label").trimmingCharacters(in: .whitespacesAndNewlines)
        let stateReputation = object.object("reputation_state")?.string("canonical_label")
            ?? object.object("reputation_state")?.string("state_label")
            ?? object.object("reputation_state")?.string("player_descriptor")
            ?? ""
        let reputationLabel = explicitReputation.isEmpty
            ? (stateReputation.isEmpty ? "Нейтральный" : stateReputation)
            : explicitReputation

        self.init(
            playerId: playerId,
            roleType: roleType.isEmpty ? "player" : roleType,
            displayName: displayName.isEmpty ? playerId : displayName,
            reputationLabel: reputationLabel
        )
    }
}

private struct TransferAssetOption: Identifiable, Equatable {
    let assetType: String
    let assetId: String
    let quantity: Int
    let title: String
    let detail: String

    var id: String {
        "\(assetType)|\(assetId)"
    }
}

private enum HomeTab: String {
    case journal
    case pvp
    case deck
    case inventory
    case orders
}

private enum DeckSetupMode: String, CaseIterable, Identifiable {
    case builder
    case encyclopedia
    case mechanics

    var id: String { rawValue }

    var title: String {
        switch self {
        case .builder:
            return "Колода"
        case .encyclopedia:
            return "Энциклопедия"
        case .mechanics:
            return "Механики"
        }
    }
}

private enum DeckEncyclopediaScope: String, CaseIterable, Identifiable {
    case owned
    case all

    var id: String { rawValue }

    var title: String {
        switch self {
        case .owned:
            return "Свои карты"
        case .all:
            return "Все карты"
        }
    }

    var emptyMessage: String {
        switch self {
        case .owned:
            return "В доступных картах пока нет карт этого ряда."
        case .all:
            return "Карты этого ряда пока не найдены."
        }
    }
}

private struct GwentMechanicInfo: Identifiable {
    let id: String
    let title: String
    let detail: String
    let icon: String
    let color: Color
}

private enum DeckRowFilter: String, CaseIterable, Identifiable {
    case all
    case melee
    case ranged
    case siege
    case special

    var id: String { rawValue }

    var title: String {
        switch self {
        case .all:
            return "Все"
        case .melee:
            return "Ближ."
        case .ranged:
            return "Дальн."
        case .siege:
            return "Осада"
        case .special:
            return "Особ."
        }
    }
}

private enum DeckStrengthFilter: String, CaseIterable, Identifiable {
    case all
    case low
    case medium
    case high

    var id: String { rawValue }

    var title: String {
        switch self {
        case .all:
            return "Любая"
        case .low:
            return "0-4"
        case .medium:
            return "5-9"
        case .high:
            return "10+"
        }
    }

    func contains(_ strength: Int) -> Bool {
        switch self {
        case .all:
            return true
        case .low:
            return strength <= 4
        case .medium:
            return (5...9).contains(strength)
        case .high:
            return strength >= 10
        }
    }
}

private struct HomeGwentDeckMetrics {
    let total: Int
    let units: Int
    let specials: Int
    let heroes: Int
    let strength: Int
    let rows: [String: Int]

    var activeRows: Int {
        rows.values.filter { $0 > 0 }.count
    }
}

private struct XPProgress {
    let fraction: Double
    let percentLabel: String
    let detailLabel: String
    let accessibilityLabel: String
}

private extension View {
    func cardStyle() -> some View {
        padding()
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(.thinMaterial)
            .clipShape(RoundedRectangle(cornerRadius: 8))
    }
}
