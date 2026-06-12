import SwiftUI

struct HomeView: View {
    @EnvironmentObject private var model: AppModel
    @State private var selectedTab: HomeTab = .journal
    @State private var appliedInitialTab = false
    @State private var showQR = false
    @State private var showGwentTable = false
    @State private var inventoryMode: InventoryMode = .gear
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
    @State private var isStartingBotMatch = false
    @State private var showServerSettings = false
    @State private var serverURLText = ""
    @State private var deckMode: DeckSetupMode = .builder
    @State private var deckRowFilter: DeckRowFilter = .all
    @State private var deckDraftCardIds: [String] = []
    @State private var deckDraftLeaderId = ""
    @State private var deckDraftSourceFingerprint = ""
    @State private var selectedDeckCardId = ""
    @State private var isSavingDeckDraft = false

    var body: some View {
        TabView(selection: $selectedTab) {
            journal
                .tabItem { Label("Журнал", systemImage: "book.closed") }
                .tag(HomeTab.journal)
            pvp
                .tabItem { Label("PvP", systemImage: "suit.club") }
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
            QRScannerSheet()
        }
        .fullScreenCover(isPresented: $showGwentTable) {
            GwentTableView()
                .environmentObject(model)
        }
        .sheet(isPresented: $showServerSettings) {
            serverSettingsSheet
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
            showQR = true
        } label: {
            Label("Сканировать QR", systemImage: "qrcode.viewfinder")
                .frame(maxWidth: .infinity)
        }
        .buttonStyle(.borderedProminent)
    }

    private func characterCard(_ player: PlayerProfile) -> some View {
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
                metric("XP", "\(player.xp)")
                metric("Золото", "\(player.gold)g")
            }

            Text(player.reputationLabel)
                .font(.footnote)
                .foregroundStyle(.secondary)
        }
        .cardStyle()
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

    private func lastResultCard(_ result: PvESceneDraft) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Последняя сцена")
                .font(.headline)
            Text("\(result.qr.manualCode) · \(pveSceneTypeLabel(result.scenario.sceneType))")
                .font(.subheadline)
            Text("d20 \(result.roll) + \(result.statLabel) \(result.statValue) = \(result.total), сложность \(result.scenario.dc)")
                .font(.footnote)
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
                    TextField("http://192.168.0.102:8003", text: $serverURLText)
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
                    case .gear:
                        gearSection
                    case .bag:
                        bagSection
                    case .trade:
                        tradeSection
                    }
                }
                .padding()
            }
            .navigationTitle("Инвентарь")
        }
    }

    private var gearSection: some View {
        VStack(alignment: .leading, spacing: 16) {
            ownedAssetsCard
            catalogItemsCard
            personalCardsCard
            Text("Использование и передача доступны только для активных, не заблокированных вещей.")
                .font(.footnote)
                .foregroundStyle(.secondary)
        }
    }

    private var bagSection: some View {
        VStack(alignment: .leading, spacing: 16) {
            potionInventoryCard
            potionCatalogCard
            artifactsCard
            lockedRewardsCard
        }
    }

    private var ownedAssetsCard: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Активные вещи")
                .font(.headline)
            if ownedAssets.isEmpty {
                Text("У персонажа пока нет активных вещей.")
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
            "item_silver_dust": "Серебряная пыль",
            "item_monster_trophy": "Трофей чудовища",
            "item_order_seal": "Печать заказа",
            "artifact_silver_chain": "Серебряная цепь",
            "potion_common_swallow": "Ласточка",
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
            "pc_"
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
        if lower.contains("minor_heal_scene_hp") {
            return "Помогает восстановиться в сцене."
        }
        return ""
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

    private var tradeSection: some View {
        VStack(alignment: .leading, spacing: 16) {
            VStack(alignment: .leading, spacing: 10) {
                Text("Передать вещь")
                    .font(.headline)
                Text("Выбери получателя и предмет. Заблокированные награды и уже потраченные вещи здесь не показываются.")
                    .font(.caption)
                    .foregroundStyle(.secondary)

                if tradeRecipients.isEmpty {
                    Label("В дневнике пока нет доступных получателей. Обнови данные игры в Wi-Fi зоне.", systemImage: "person.crop.circle.badge.exclamationmark")
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

            if model.snapshot?.tradeTransfers.isEmpty ?? true {
                Text("Обмен работает только при связи с сервером. Если ты офлайн, договорись устно и вернись к передаче после подключения.")
                    .font(.footnote)
                    .foregroundStyle(.secondary)
            }

            if let result = model.lastTradeResult {
                VStack(alignment: .leading, spacing: 8) {
                    Text("Последняя передача")
                        .font(.headline)
                    Text(result.displayText)
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                }
                .cardStyle()
            }
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
                Text(assetDisplayName(row.string("asset_id")))
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
        let otherPlayerId = incoming ? row.string("from_player_id") : row.string("to_player_id")
        let direction = incoming ? "от \(playerName(otherPlayerId))" : "для \(playerName(otherPlayerId))"
        let quantity = max(1, row.int("quantity", default: 1))
        let price = row.int("price_gold")
        var parts = [
            direction,
            "\(assetTypeLabel(row.string("asset_type"))) · x\(quantity)"
        ]
        if price > 0 {
            parts.append("\(price)g")
        }
        let mode = row.string("mode")
        if !mode.isEmpty {
            parts.append(tradeModeLabel(mode))
        }
        return parts.joined(separator: " · ")
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

                            Text("\(orderVisibilityLabel(order.visibility)) · \(orderObjectTypeLabel(order.objectType)) · награда зарезервирована")
                                .font(.footnote)
                                .foregroundStyle(.secondary)

                            Text(orderProgressHint(order))
                                .font(.caption)
                                .foregroundStyle(.secondary)

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
        if !order.objectLabel.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            return order.objectLabel
        }
        return readableIdentifier(order.objectId, droppingPrefixes: ["qr_", "order_"])
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

    private func orderProgressHint(_ order: OrderSummary) -> String {
        if hasQueuedOrderSubmission(order) {
            return "Сдача уже сохранена на телефоне. Вернись в Wi-Fi и отправь события."
        }
        if localOrderProof(order) != nil {
            return "Подтверждение найдено на телефоне. Можно сдать заказ."
        }
        if order.isSubmittable {
            return "Пройди QR/PvE на объекте заказа, затем вернись сюда и нажми «Сдать»."
        }
        if order.isAcceptable {
            return "Награда в escrow. Возьми заказ, если готов идти к объекту."
        }
        return "Следи за статусом после обновления дневника."
    }

    private func localOrderProof(_ order: OrderSummary) -> QueuedEvent? {
        model.pendingEvents.last { event in
            event.eventType == "pve_completed"
                && event.payload.string("qr_id") == order.objectId
                && event.payload.string("player_id", default: model.player?.playerId ?? "") == model.player?.playerId
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
                    gwentTableLauncher
                    gwentBotTrainingCard
                    gwentStatusNotice
                    gwentActionCard
                    gwentChallengeCard
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
            .onAppear {
                syncDeckDraftIfNeeded(force: true)
            }
            .onChange(of: model.snapshot?.snapshotVersion ?? "") { _ in
                syncDeckDraftIfNeeded(force: true)
            }
            .onChange(of: model.runtimeGwentDecks.map(\.deckId).joined(separator: "|")) { _ in
                syncDeckDraftIfNeeded(force: true)
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
                    Text("\(metrics.total)")
                        .font(.title2.monospacedDigit().bold())
                        .foregroundStyle(warnings.isEmpty ? .green : .orange)
                    Text("карт")
                        .font(.caption2.bold())
                        .foregroundStyle(.white.opacity(0.62))
                }
                .padding(.horizontal, 10)
                .padding(.vertical, 7)
                .background(.black.opacity(0.34))
                .clipShape(RoundedRectangle(cornerRadius: 6))
            }

            HStack(spacing: 7) {
                deckMetricSeal(title: "Отряды", value: "\(metrics.units)", ok: metrics.units >= 22)
                deckMetricSeal(title: "Особые", value: "\(metrics.specials)/10", ok: metrics.specials <= 10)
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

    private func deckBuilderPanel(compact: Bool) -> some View {
        VStack(alignment: .leading, spacing: compact ? 12 : 14) {
            if let snapshot = model.snapshot, let deck = draftGwentDeck {
                let leader = gwentCardMeta(deck.leaderCardId) ?? snapshot.gwentCards.first { $0.cardId == deck.leaderCardId }

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
                        Text(gwentFactionLabel(gwentDeckFaction(deck)))
                            .font(.caption.bold())
                            .foregroundStyle(.yellow.opacity(0.88))
                        Text(gwentFactionAbilityLabel(gwentDeckFaction(deck)))
                            .font(.caption)
                            .foregroundStyle(.white.opacity(0.68))
                            .fixedSize(horizontal: false, vertical: true)

                        leaderPicker
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                }

                deckSelectedStrip(compact: compact)
                rowFilterControl
                cardCollectionGrid(cards: filteredDeckCards, compact: compact, allowsEditing: true)

                Button {
                    Task {
                        await saveDeckDraft(deck)
                    }
                } label: {
                    Label(isSavingDeckDraft ? "Сохраняю..." : "Сохранить колоду", systemImage: "square.and.arrow.down")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent)
                .tint(gwentDeckWarnings(gwentDeckMetrics(cardIds: deckDraftCardIds)).isEmpty ? .green : .orange)
                .disabled(isSavingDeckDraft || !gwentDeckWarnings(gwentDeckMetrics(cardIds: deckDraftCardIds)).isEmpty)
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
        VStack(alignment: .leading, spacing: compact ? 12 : 14) {
            rowFilterControl
            cardCollectionGrid(cards: filteredDeckCardsIncludingLeaders, compact: compact, allowsEditing: false)

            if let selected = selectedDeckCard {
                deckCardInspector(selected, compact: compact)
            }
        }
        .padding(compact ? 12 : 14)
        .background(deckPanelBackground)
        .overlay(deckPanelStroke)
        .clipShape(RoundedRectangle(cornerRadius: 8))
    }

    private var gwentTableLauncher: some View {
        Button {
            showGwentTable = true
        } label: {
            HStack(spacing: 12) {
                Image(systemName: "iphone.landscape")
                    .font(.title2.bold())
                    .frame(width: 42, height: 42)
                    .background(.yellow.opacity(0.18))
                    .clipShape(RoundedRectangle(cornerRadius: 8))
                VStack(alignment: .leading, spacing: 3) {
                    Text("Открыть игровой стол")
                        .font(.headline)
                    Text("Крупная рука, три ряда, счет и пас в fullscreen.")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                Spacer()
                Image(systemName: "chevron.right")
                    .font(.caption.bold())
                    .foregroundStyle(.secondary)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .buttonStyle(.plain)
        .cardStyle()
    }

    private var gwentBotTrainingCard: some View {
        HStack(spacing: 12) {
            Image(systemName: "cpu")
                .font(.title2.bold())
                .frame(width: 42, height: 42)
                .background(.orange.opacity(0.16))
                .clipShape(RoundedRectangle(cornerRadius: 8))
            VStack(alignment: .leading, spacing: 3) {
                Text("Тренировка против компьютера")
                    .font(.headline)
                Text("Серверный соперник играет по тем же правилам, без ставки.")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            Spacer()
            Button {
                Task {
                    guard !isStartingBotMatch else { return }
                    isStartingBotMatch = true
                    await model.startGwentBotMatch()
                    isStartingBotMatch = false
                    if model.errorMessage == nil {
                        showGwentTable = true
                    }
                }
            } label: {
                Label(isStartingBotMatch ? "Стартую..." : "Начать", systemImage: "rectangle.stack.badge.play")
            }
            .buttonStyle(.borderedProminent)
            .tint(.orange)
            .disabled(isStartingBotMatch)
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

    private var leaderPicker: some View {
        let leaders = availableLeaderCards

        return Menu {
            ForEach(leaders) { leader in
                Button {
                    deckDraftLeaderId = leader.cardId
                    selectedDeckCardId = leader.cardId
                } label: {
                    Label(gwentCardTitle(leader.cardId), systemImage: gwentRowIcon(leader.row))
                }
            }
        } label: {
            Label("Сменить лидера", systemImage: "crown")
                .font(.caption.bold())
                .frame(maxWidth: .infinity)
        }
        .buttonStyle(.bordered)
        .tint(.yellow)
        .disabled(leaders.isEmpty)
    }

    private func deckSelectedStrip(compact: Bool) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text("Карты в колоде")
                    .font(.headline)
                    .foregroundStyle(.white)
                Spacer()
                Text("\(deckDraftCardIds.count)")
                    .font(.caption.monospacedDigit().bold())
                    .foregroundStyle(.white.opacity(0.72))
            }

            let selectedCards = deckDraftCards
            if selectedCards.isEmpty {
                Text("Нажимай на карты ниже, чтобы собрать колоду перед боем.")
                    .font(.caption)
                    .foregroundStyle(.white.opacity(0.58))
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.vertical, 14)
            } else {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: compact ? 8 : 10) {
                        ForEach(selectedCards) { card in
                            Button {
                                toggleDeckCard(card)
                            } label: {
                                gwentCardView(
                                    card,
                                    selected: selectedDeckCardId == card.cardId,
                                    inDeck: true,
                                    compact: true,
                                    large: false
                                )
                                .frame(width: compact ? 78 : 86, height: compact ? 112 : 124)
                            }
                            .buttonStyle(.plain)
                        }
                    }
                    .padding(.vertical, 2)
                }
            }
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

    private func cardCollectionGrid(cards: [GwentCard], compact: Bool, allowsEditing: Bool) -> some View {
        let columns = [
            GridItem(.adaptive(minimum: compact ? 96 : 108, maximum: compact ? 112 : 128), spacing: compact ? 9 : 11)
        ]

        return LazyVGrid(columns: columns, spacing: compact ? 10 : 12) {
            ForEach(cards) { card in
                let inDeck = deckDraftCardIds.contains(card.cardId) || deckDraftLeaderId == card.cardId
                Button {
                    if allowsEditing {
                        toggleDeckCard(card)
                    } else {
                        selectedDeckCardId = card.cardId
                    }
                } label: {
                    gwentCardView(
                        card,
                        selected: selectedDeckCardId == card.cardId,
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
                    Image(systemName: gwentArtworkIcon(card))
                        .font(.system(size: large ? 38 : (compact ? 30 : 34), weight: .semibold))
                        .foregroundStyle(rowColor.opacity(0.88))
                        .shadow(color: .black.opacity(0.8), radius: 3, y: 2)
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
                }
                .frame(height: large ? (compact ? 82 : 92) : (compact ? 72 : 80))

                Text(gwentCardTitle(card.cardId))
                    .font(large ? .caption.bold() : .caption2.bold())
                    .foregroundStyle(.white)
                    .multilineTextAlignment(.center)
                    .lineLimit(2)
                    .minimumScaleFactor(0.62)
                    .frame(maxWidth: .infinity, minHeight: compact ? 26 : 30)

                Text(gwentEffectLabel(card.effect))
                    .font(.system(size: compact ? 8 : 9, weight: .bold))
                    .foregroundStyle(.black.opacity(0.78))
                    .lineLimit(1)
                    .minimumScaleFactor(0.58)
                    .padding(.horizontal, 5)
                    .frame(maxWidth: .infinity, minHeight: 17)
                    .background(rowColor.opacity(0.72))
                    .clipShape(RoundedRectangle(cornerRadius: 4))
            }
            .padding(large ? 7 : 6)

            Text(card.type.lowercased() == "leader" ? "L" : "\(card.strength)")
                .font(.system(size: large ? 18 : 16, weight: .black, design: .rounded))
                .foregroundStyle(.black)
                .frame(width: large ? 34 : 30, height: large ? 34 : 30)
                .background(
                    Circle()
                        .fill(card.type.lowercased() == "leader" ? .yellow : .white)
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
                HStack(spacing: 6) {
                    deckPropertyChip(gwentFactionLabel(card.faction), color: .yellow)
                    deckPropertyChip(gwentRarityLabel(card.rarity), color: gwentRarityColor(card.rarity))
                }
                if !card.abilityTags.isEmpty {
                    Text(card.abilityTags.map { readableIdentifier($0) }.joined(separator: " · "))
                        .font(.caption2.bold())
                        .foregroundStyle(.white.opacity(0.58))
                        .lineLimit(2)
                }
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

    private var availableLeaderCards: [GwentCard] {
        (model.snapshot?.gwentCards ?? [])
            .filter { $0.type.lowercased() == "leader" || $0.row.lowercased() == "leader" }
            .sorted { gwentFactionLabel($0.faction) < gwentFactionLabel($1.faction) }
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
        filterCards((model.snapshot?.gwentCards ?? []).filter { $0.type.lowercased() != "leader" && $0.row.lowercased() != "leader" })
    }

    private var filteredDeckCardsIncludingLeaders: [GwentCard] {
        filterCards(model.snapshot?.gwentCards ?? [])
    }

    private func filterCards(_ cards: [GwentCard]) -> [GwentCard] {
        cards
            .filter { card in
                switch deckRowFilter {
                case .all:
                    return true
                case .melee, .ranged, .siege:
                    return card.row.lowercased() == deckRowFilter.rawValue
                case .special:
                    return ["special", "weather"].contains(card.row.lowercased()) || card.type.lowercased() == "special"
                }
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

    private func syncDeckDraftIfNeeded(force: Bool = false) {
        guard let deck = currentPlayerGwentDeck else { return }
        let fingerprint = deckFingerprint(deck)
        guard force || fingerprint != deckDraftSourceFingerprint else { return }
        deckDraftSourceFingerprint = fingerprint
        deckDraftCardIds = deck.cardIds
        deckDraftLeaderId = deck.leaderCardId
        selectedDeckCardId = deck.cardIds.first ?? deck.leaderCardId
    }

    private func deckFingerprint(_ deck: GwentDeck) -> String {
        "\(deck.deckId)|\(deck.leaderCardId)|\(deck.cardIds.joined(separator: ","))"
    }

    private func toggleDeckCard(_ card: GwentCard) {
        selectedDeckCardId = card.cardId
        if card.type.lowercased() == "leader" || card.row.lowercased() == "leader" {
            deckDraftLeaderId = card.cardId
            return
        }
        if let index = deckDraftCardIds.firstIndex(of: card.cardId) {
            deckDraftCardIds.remove(at: index)
        } else {
            deckDraftCardIds.append(card.cardId)
        }
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

    private func gwentDeckTitle(_ deck: GwentDeck) -> String {
        readableIdentifier(deck.deckId, droppingPrefixes: ["runtime_deck_", "deck_", "gwent_deck_"])
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

    private func deckCardDetail(_ cardId: String) -> String {
        guard let card = gwentCardMeta(cardId) else {
            return readableIdentifier(cardId)
        }
        let effect = card.effect == "none" ? "без эффекта" : gwentEffectLabel(card.effect)
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
            return "медик"
        case "muster":
            return "сбор"
        case "morale":
            return "боевой дух"
        case "bond", "tight_bond":
            return "прочная связь"
        case "agile":
            return "гибкий ряд"
        case "weather_melee", "biting_frost":
            return "мороз"
        case "weather_ranged", "impenetrable_fog":
            return "туман"
        case "weather_siege", "torrential_rain":
            return "ливень"
        case "clear_weather":
            return "ясно"
        case "commanders_horn":
            return "рог"
        case "decoy":
            return "приманка"
        case "scorch":
            return "казнь"
        case "scorch_siege":
            return "казнь осады"
        case "custom_larp_order_banner":
            return "знамя заказа"
        case "custom_larp_spyglass":
            return "подзорная труба"
        case "custom_larp_oathbreak":
            return "разрыв клятвы"
        case "custom_larp_last_stand":
            return "последний рубеж"
        case "leader_order_rally":
            return "приказ лидера"
        case "leader_foltest_clear_weather":
            return "ясная погода"
        case "leader_emhyr_graveyard_theft":
            return "карта из сброса"
        case "leader_francesca_ranged_horn":
            return "рог дальнего ряда"
        case "leader_eredin_melee_horn":
            return "рог ближнего ряда"
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
        case "spy", "custom_larp_spyglass":
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
                Text("Лобби партии")
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
                    Text("Активного вызова нет. Создай вызов ниже или обнови столы.")
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
            Text("Открытые партии")
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
                Text("Нажми «Столы», когда iPhone в Wi-Fi зоне.")
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
                Text("Вызов")
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

            if opponents.isEmpty {
                Text("В snapshot нет доступных ведьмаков или чародеек для вызова.")
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
                Text("Нет активных вещей, карт или артефактов, которые можно поставить.")
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
                Label("Вызвать на Гвинт", systemImage: "flag.checkered")
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
    }

    private var gwentOpponentOptions: [PlayerProfile] {
        guard let player = model.player else { return [] }
        return (model.snapshot?.players ?? [])
            .filter { candidate in
                candidate.playerId != player.playerId
                    && ["witcher", "sorceress"].contains(candidate.roleType.lowercased())
            }
            .sorted { $0.displayName < $1.displayName }
    }

    private var gwentStakeOptions: [GwentStakeOption] {
        let assetOptions = ownedAssets
            .compactMap(gwentStakeOption)
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
            return strength
        }
        return gwentCardMeta(gwentCardId(value))?.strength
    }

    private func gwentCardMeta(_ cardId: String) -> GwentCard? {
        model.snapshot?.gwentCards.first { $0.cardId == cardId }
    }

    private func gwentRowTotal(_ cards: [JSONValue]) -> Int {
        cards.reduce(0) { partial, value in
            partial + (gwentCardStrength(value) ?? 0)
        }
    }

    private func gwentCardTitle(_ cardId: String) -> String {
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
            return "Погода: \(readableIdentifier(cardId, droppingPrefixes: ["gwent_weather_"]))"
        }
        if let meta = gwentCardMeta(cardId), meta.type.lowercased() == "leader" {
            return "Лидер \(readableIdentifier(cardId, droppingPrefixes: ["gwent_leader_", "gwent_"]))"
        }
        return readableIdentifier(cardId, droppingPrefixes: ["gwent_"])
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
            return "\(qr) · \(pveResultLabel(result)) · ожидает отправки"
        case "order_submission":
            let orderId = event.payload.string("order_id")
            return "\(orderDisplayName(orderId)) · подтверждение сохранено · ожидает отправки"
        case "qr_attempt":
            let code = event.payload.string("manual_code", default: event.payload.string("normalized_code"))
            let reason = event.payload.string("review_reason")
            return reason.isEmpty ? "\(code) · ожидает отправки" : "\(code) · \(reviewReasonLabel(reason))"
        case "act_unlocked_offline":
            return "\(actDisplayName(event.payload.string("act_id"))) · открыто на этом телефоне · ожидает отправки"
        default:
            return "Событие \(event.clientSequence) ожидает отправки"
        }
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
    case gear
    case bag
    case trade

    var id: String { rawValue }

    var title: String {
        switch self {
        case .gear:
            return "Снаряжение"
        case .bag:
            return "Сумка"
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

    var id: String { rawValue }

    var title: String {
        switch self {
        case .builder:
            return "Колода"
        case .encyclopedia:
            return "Энциклопедия"
        }
    }
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

private extension View {
    func cardStyle() -> some View {
        padding()
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(.thinMaterial)
            .clipShape(RoundedRectangle(cornerRadius: 8))
    }
}
