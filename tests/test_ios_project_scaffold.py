import csv
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_ios_native_scaffold_exists():
    expected = [
        "ios/README.md",
        "ios/project.yml",
        "ios/Resources/Info.plist",
        "ios/WitcherLARP/App/WitcherLARPApp.swift",
        "ios/WitcherLARP/App/AppModel.swift",
        "ios/WitcherLARP/Core/API/LarpAPIClient.swift",
        "ios/WitcherLARP/Core/Sync/EventQueueStore.swift",
        "ios/WitcherLARP/Features/PvE/PVEMissionSheet.swift",
        "ios/WitcherLARP/Features/QR/QRScannerView.swift",
    ]

    for relative_path in expected:
        assert (ROOT / relative_path).exists(), relative_path


def test_ios_scaffold_uses_native_qr_and_local_network_permissions():
    scanner = (ROOT / "ios/WitcherLARP/Features/QR/QRScannerView.swift").read_text(encoding="utf-8")
    plist = (ROOT / "ios/Resources/Info.plist").read_text(encoding="utf-8")
    accent = ROOT / "ios/Resources/Assets.xcassets/AccentColor.colorset/Contents.json"

    assert "AVFoundation" in scanner
    assert "AVCaptureMetadataOutput" in scanner
    assert "Vision" in scanner
    assert "AVCaptureVideoDataOutput" in scanner
    assert "VNRecognizeTextRequest" in scanner
    assert "printedQRCode" in scanner
    assert "NSCameraUsageDescription" in plist
    assert "NSLocalNetworkUsageDescription" in plist
    assert accent.exists()


def test_ios_plan_marks_godot_as_legacy_not_deleted():
    plan = (ROOT / "docs/ios-native-plan.md").read_text(encoding="utf-8")

    assert "iOS-приложение" in plan
    assert "SwiftUI" in plan
    assert "Godot" in plan
    assert "legacy/reference" in plan
    assert "Android выходит из scope" in plan


def test_ios_gwent_bot_training_button_starts_match_before_opening_table():
    home = (ROOT / "ios/WitcherLARP/Features/Home/HomeView.swift").read_text(encoding="utf-8")
    marker = 'Text("Тренировка против компьютера")'

    bot_card = home[home.index(marker): home.index(marker) + 1_200]

    assert "await model.startGwentBotMatch()" in bot_card
    assert "showGwentTable = true" in bot_card
    assert 'Label(isStartingBotMatch ? "Стартую..." : "Начать"' in bot_card
    assert 'Label("Подготовить"' not in bot_card


def test_ios_gwent_table_requests_landscape_orientation():
    table = (ROOT / "ios/WitcherLARP/Features/Gwent/GwentTableView.swift").read_text(encoding="utf-8")
    plist = (ROOT / "ios/Resources/Info.plist").read_text(encoding="utf-8")

    assert "UIInterfaceOrientationLandscapeLeft" in plist
    assert "UIInterfaceOrientationLandscapeRight" in plist
    assert "GwentOrientationRequester" in table
    assert "requestGeometryUpdate(.iOS(interfaceOrientations: orientations))" in table
    assert ".background(GwentOrientationRequester(orientations: .landscape))" in table


def test_ios_gwent_table_uses_adaptive_landscape_metrics():
    table = (ROOT / "ios/WitcherLARP/Features/Gwent/GwentTableView.swift").read_text(encoding="utf-8")

    assert "@Environment(\\.verticalSizeClass)" in table
    assert "var compactLandscapeTable: Bool" in table
    assert "verticalSizeClass == .compact || model.screenshotMode" in table
    assert "private struct GwentTableLayout" in table
    assert "enum Density" in table
    assert "case tightPhone" in table
    assert "case phone" in table
    assert "let safeAreaInsets: EdgeInsets" in table
    assert "safeAreaInsets.leading + safeAreaInsets.trailing" in table
    assert "let notchFallback" in table
    assert "let landscapeTopClearance" in table
    assert "max(max(safeAreaInsets.top, baseVertical), landscapeTopClearance)" in table
    assert "layout.contentInsets" in table
    assert "gwentTableBackground\n                    .ignoresSafeArea()" in table
    assert ".persistentSystemOverlays(.hidden)" in table
    assert "var boardRowHeight: CGFloat" in table
    assert "let visibleRows: CGFloat = selectionMode ? 3 : 6" in table
    assert "floor((boardAreaHeight - weatherStripHeight - (boardRowSpacing * visibleRows)) / visibleRows)" in table
    assert "var handExpandedHeight: CGFloat" in table
    assert "contentHeight * 0.26" in table
    assert "layout.playerRailWidth" in table
    assert "layout.handCardHeight" in table
    assert "collapsedHandPlaque(match: match, layout: layout)" in table
    assert "private func passButton(match: [String: JSONValue], layout: GwentTableLayout) -> some View" in table
    assert table.count("passButton(match: match, layout: layout)") >= 2
    assert "ScrollView(.horizontal, showsIndicators: false)" in table
    assert "LazyHStack(spacing:" in table
    assert "ForEach(Array(cards.enumerated()), id: \\.offset)" in table
    assert "showsIndicators: cards.count > 3" not in table
    assert "cards.prefix(10)" not in table
    assert "var boardCardTitleBandHeight: CGFloat" in table
    assert "gwentBoardCardDisplayStrength(value, row: row, playerId: playerId, rowCards: rowCards)" in table
    assert '"gwent_unit_11": "Осадная башня"' in table
    assert 'return "Отряд"' in table
    assert "Боевая карта" not in table
    assert ".lineLimit(2)" in table
    assert "tableSafeLeadingPadding" not in table


def test_ios_gwent_static_catalog_prevents_english_card_fallbacks():
    snapshot = (ROOT / "ios/WitcherLARP/Core/Models/SnapshotModels.swift").read_text(encoding="utf-8")
    table = (ROOT / "ios/WitcherLARP/Features/Gwent/GwentTableView.swift").read_text(encoding="utf-8")
    home = (ROOT / "ios/WitcherLARP/Features/Home/HomeView.swift").read_text(encoding="utf-8")

    assert "enum GwentStaticCatalog" in snapshot
    assert "static var allCards: [GwentCard]" in snapshot
    seed_card_ids = {
        row["card_id"]
        for row in csv.DictReader((ROOT / "data/seed/gwent_cards.csv").open(encoding="utf-8"))
    }
    static_card_ids = set(re.findall(r'"([^"]+)": StaticCard', snapshot))
    assert seed_card_ids <= static_card_ids
    assert len(static_card_ids) == len(seed_card_ids)
    assert '"gwent_leader_eredin_bringer": StaticCard' in snapshot
    assert '"Эредин: Несущий смерть"' in snapshot
    assert '"gwent_leader_eredin_destroyer": StaticCard' in snapshot
    assert '"Эредин: Разрушитель миров"' in snapshot
    assert '"nr_sile_de_tansarville": StaticCard' in snapshot
    assert '"Шеала де Тансервилль"' in snapshot
    assert '"rare_gwent_03": StaticCard' in snapshot
    assert '"Цирилла Фиона Элен Рианнон"' in snapshot
    assert '"nr_kaedweni_siege_expert_3": StaticCard' in snapshot
    assert 'strength: 1, effect: "morale"' in snapshot
    assert '"Каэдвенский осадный мастер"' in snapshot
    assert (ROOT / "ios/Resources/Assets.xcassets/gwent_card_art_gwent_unit_04.imageset/Contents.json").exists()
    assert (ROOT / "ios/Resources/Assets.xcassets/gwent_card_art_gwent_unit_04.imageset/gwent_card_art_gwent_unit_04.png").exists()

    assert "GwentStaticCatalog.card(cardId) ?? snapshotCard" in table
    assert "GwentStaticCatalog.card(cardId) ?? snapshotCard" in home
    assert "normalizedPayloadStrength(strength, key: key, cardId: cardId)" in table
    assert 'return "Лидер \\(readableIdentifier(cardId' not in table
    assert 'return "Лидер \\(readableIdentifier(cardId' not in home


def test_ios_screenshot_mode_does_not_auto_probe_server_on_login():
    login = (ROOT / "ios/WitcherLARP/Features/Login/LoginView.swift").read_text(encoding="utf-8")
    root = (ROOT / "ios/WitcherLARP/App/RootView.swift").read_text(encoding="utf-8")
    home = (ROOT / "ios/WitcherLARP/Features/Home/HomeView.swift").read_text(encoding="utf-8")
    app_model = (ROOT / "ios/WitcherLARP/App/AppModel.swift").read_text(encoding="utf-8")

    assert "var screenshotMode: Bool" in app_model
    assert "let demoSnapshotMode: Bool" in app_model
    assert "demoSnapshotMode || screenshotInitialTab != nil" in app_model
    assert "!screenshotMode && serverHealthChecked && !serverSupportsGwent" in app_model
    assert "guard !model.screenshotMode else { return }" in root
    assert "if !model.screenshotMode" in home
    assert "if !model.screenshotMode" in login
    assert "await model.checkServerHealth()" in login
    assert "guard !model.screenshotMode else { return }" in (
        ROOT / "ios/WitcherLARP/Features/Gwent/GwentTableView.swift"
    ).read_text(encoding="utf-8")


def test_ios_server_settings_normalize_local_http_address():
    app_model = (ROOT / "ios/WitcherLARP/App/AppModel.swift").read_text(encoding="utf-8")
    login = (ROOT / "ios/WitcherLARP/Features/Login/LoginView.swift").read_text(encoding="utf-8")
    home = (ROOT / "ios/WitcherLARP/Features/Home/HomeView.swift").read_text(encoding="utf-8")

    assert "func updateServerURL(from text: String)" in app_model
    assert 'raw = "http://\\(raw)"' in app_model
    assert 'raw.lowercased().hasSuffix("/health")' in app_model
    assert "model.updateServerURL(from: serverURLText)" in login
    assert "model.updateServerURL(from: serverURLText)" in home


def test_ios_gwent_finished_match_hides_raw_ids_and_can_restart_bot_training():
    table = (ROOT / "ios/WitcherLARP/Features/Gwent/GwentTableView.swift").read_text(encoding="utf-8")

    subtitle = table[table.index("var tableSubtitle"): table.index("func activeGwentPlayerSubmitted")]
    weather = table[table.index("private func weatherStrip"): table.index("private func handStrip")]
    resolution = table[table.index("private func matchResolutionPanel"): table.index("private func resolutionMetric")]

    assert "shortGameCode" not in subtitle
    assert "match_id" not in weather
    assert "Ваши раунды" in resolution
    assert "Раунды соперника" in resolution
    assert "await model.startGwentBotMatch()" in resolution
    assert "Новая тренировка" in resolution
    assert "var shouldAutoPollGwentTable" in table
    assert "return !isMatchResolutionVisible(match)" in table


def test_ios_release_includes_gwent_table_source():
    home = (ROOT / "ios/WitcherLARP/Features/Home/HomeView.swift").read_text(encoding="utf-8")
    app_model = (ROOT / "ios/WitcherLARP/App/AppModel.swift").read_text(encoding="utf-8")
    project = (ROOT / "ios/WitcherLARP.xcodeproj/project.pbxproj").read_text(encoding="utf-8")
    project_yml = (ROOT / "ios/project.yml").read_text(encoding="utf-8")

    cover = home[
        home.index(".sheet(isPresented: $showQR)"):
        home.index(".sheet(isPresented: $showServerSettings)")
    ]
    assert "#if DEBUG" not in cover
    assert "GwentTableView()" in cover
    assert "var gwentUXEnabled: Bool" in app_model
    gwent_flag = app_model[app_model.index("var gwentUXEnabled: Bool"): app_model.index("var serverIsReachable")]
    assert "true" in gwent_flag
    assert "false" not in gwent_flag

    target_debug = project[
        project.index("100000000000000000000A03 /* Debug */"):
        project.index("100000000000000000000A04 /* Release */")
    ]
    target_release = project[
        project.index("100000000000000000000A04 /* Release */"):
        project.index("/* End XCBuildConfiguration section */")
    ]
    assert "EXCLUDED_SOURCE_FILE_NAMES = GwentTableView.swift;" not in target_debug
    assert "EXCLUDED_SOURCE_FILE_NAMES = GwentTableView.swift;" not in target_release
    assert "EXCLUDED_SOURCE_FILE_NAMES: GwentTableView.swift" not in project_yml


def test_ios_home_bottom_nav_uses_journal_pvp_deck_inventory_orders():
    home = (ROOT / "ios/WitcherLARP/Features/Home/HomeView.swift").read_text(encoding="utf-8")
    tab_view = home[home.index("TabView(selection: $selectedTab)"): home.index(".sheet(isPresented: $showQR)")]
    journal = home[home.index("private var journal: some View"): home.index("private var journalQRButton")]

    assert 'Label("Журнал", systemImage: "book.closed")' in tab_view
    assert 'Label("Дуэли", systemImage: "suit.club")' in tab_view
    assert 'Label("Колода", systemImage: "rectangle.stack")' in tab_view
    assert 'Label("Инвентарь", systemImage: "backpack")' in tab_view
    assert 'Label("Заказы", systemImage: "scroll")' in tab_view
    assert 'Label("QR", systemImage: "qrcode.viewfinder")' not in tab_view
    assert 'Label("Связь", systemImage: "arrow.triangle.2.circlepath")' not in tab_view
    assert '"Сканировать QR"' in home
    assert '"Продолжить миссию"' in home
    assert '"qrcode.viewfinder"' in home
    assert "journalQRButton" in journal
    assert "currentActCard" in journal
    assert "private var actsCard" not in home
    assert 'SecureField("Код мастера"' not in home
    assert 'Label("Открыть акт"' not in home
    assert "private var pvp: some View" in home
    assert "private var deckSetup: some View" in home


def test_ios_deck_encyclopedia_toggles_owned_and_all_cards_without_clipped_strip():
    home = (ROOT / "ios/WitcherLARP/Features/Home/HomeView.swift").read_text(encoding="utf-8")
    encyclopedia = home[
        home.index("private func deckEncyclopediaPanel"):
        home.index("private func deckMechanicsPanel")
    ]
    selected_strip = home[
        home.index("private func deckSelectedStrip"):
        home.index("private var rowFilterControl")
    ]

    assert "@State private var deckEncyclopediaScope" in home
    assert "@State private var deckStrengthFilter" in home
    assert "@State private var pendingDeckRemovalCardId" in home
    assert "private let gwentDeckMinUnitCards = 22" in home
    assert "private enum DeckEncyclopediaScope" in home
    assert "private enum DeckStrengthFilter" in home
    assert 'return "Свои карты"' in home
    assert 'return "Все карты"' in home
    assert 'return "Все"' in home
    assert 'return "Все ряды"' not in home
    assert 'return "Любая"' in home
    assert "private var gwentCatalogCards: [GwentCard]" in home
    assert "for card in GwentStaticCatalog.allCards" in home
    assert "let cards = gwentCatalogCards" in home
    assert "filterCards(gwentCatalogCards)" in home
    assert "Picker(\"Карты энциклопедии\"" in encyclopedia
    assert "Picker(\"Сила\"" in home
    assert 'confirmationDialog(\n                "Убрать карту из колоды?"' in home
    assert "filteredEncyclopediaCards" in encyclopedia
    assert "ownedEncyclopediaCardIds" in home
    assert "минимум 22" in home
    assert "metrics.units > gwentDeckMinUnitCards" not in home
    assert "В боевой колоде уже 22 карты отрядов." not in home
    assert "normalizedDeckCardIds" not in home
    assert ".frame(width: compact ? 78 : 86, height: compact ? 112 : 124)" not in selected_strip


def test_ios_journal_character_card_shows_xp_bar_reputation_and_pvp_tokens():
    home = (ROOT / "ios/WitcherLARP/Features/Home/HomeView.swift").read_text(encoding="utf-8")
    snapshot = (ROOT / "ios/WitcherLARP/Core/Models/SnapshotModels.swift").read_text(encoding="utf-8")
    app_model = (ROOT / "ios/WitcherLARP/App/AppModel.swift").read_text(encoding="utf-8")

    card = home[home.index("private func characterCard"): home.index("private func metric")]

    assert 'metric("XP", "\\(player.xp)")' not in card
    assert 'metric("PvP", "\\(player.challengeTokens)")' in card
    assert "xpProgressBar(player)" in card
    assert "reputationRow(player)" in card
    assert 'Text("Добро/Зло")' in home
    assert "let challengeTokens: Int" in snapshot
    assert 'case challengeTokens = "challenge_tokens"' in snapshot
    assert '"challenge_tokens": "3"' in app_model


def test_ios_no_pvp_http_smoke_targets_ios_server_and_avoids_pvp():
    smoke = (ROOT / "scripts/ios_no_pvp_http_smoke.py").read_text(encoding="utf-8")

    assert 'default="http://192.168.68.118:8002"' in smoke
    assert "/api/auth/player-code" in smoke
    assert "/api/content/snapshot" in smoke
    assert "/api/qr/lookup" in smoke
    assert "/api/events/sync" in smoke
    assert "/api/pvp" not in smoke
    assert "/api/gwent" not in smoke


def test_ios_valid_qr_opens_pve_mission_screen_outside_scanner():
    home = (ROOT / "ios/WitcherLARP/Features/Home/HomeView.swift").read_text(encoding="utf-8")
    scanner = (ROOT / "ios/WitcherLARP/Features/QR/QRScannerSheet.swift").read_text(encoding="utf-8")
    mission = (ROOT / "ios/WitcherLARP/Features/PvE/PVEMissionSheet.swift").read_text(encoding="utf-8")
    app_model = (ROOT / "ios/WitcherLARP/App/AppModel.swift").read_text(encoding="utf-8")

    assert "func beginPVE(code rawCode: String, source: QRInputSource) -> Bool" in app_model
    assert "onMissionStarted" in scanner
    assert "if model.beginPVE(code: normalized, source: inputSource)" in scanner
    assert "missionCard(" not in scanner
    assert "resultCard(" not in scanner
    assert "@State private var showPVEMission" in home
    assert "pendingMissionPresentation" in home
    assert ".fullScreenCover(isPresented: $showPVEMission)" in home
    assert "PVEMissionSheet" in home
    assert "model.choosePVEOption(choice.choiceId)" in mission
    assert "model.rollNextPVECheck()" in mission


def test_ios_no_pvp_sim_visual_smoke_targets_release_home_without_pvp():
    smoke = (ROOT / "scripts/ios_no_pvp_sim_visual_smoke.py").read_text(encoding="utf-8")

    assert 'DEFAULT_SERVER = "http://192.168.68.118:8002"' in smoke
    assert "xcrun\", \"simctl\", \"install\"" in smoke
    assert "get_app_container" in smoke
    assert "server_url.json" in smoke
    assert "player_code.json" in smoke
    assert "snapshot.json" in smoke
    assert "release-home.png" in smoke
    assert "home_body_not_blank" in smoke
    assert "/api/content/snapshot" in smoke
    assert "/api/pvp" not in smoke
    assert "/api/gwent" not in smoke


def test_ios_gwent_tools_target_ios_server_port():
    app_model = (ROOT / "ios/WitcherLARP/App/AppModel.swift").read_text(encoding="utf-8")
    login = (ROOT / "ios/WitcherLARP/Features/Login/LoginView.swift").read_text(encoding="utf-8")
    smoke = (ROOT / "scripts/ios_gwent_http_smoke.py").read_text(encoding="utf-8")

    assert 'defaultServerURLString = "http://192.168.68.118:8002"' in app_model
    assert "Self.startupServerURL(storedURL: storedURL, defaultURL: defaultURL)" in app_model
    assert "LocalStore.shared.saveServerURL(startupURL)" in app_model
    assert "private static func startupServerURL(storedURL: URL?, defaultURL: URL) -> URL" in app_model
    assert "normalizedStored.absoluteString == normalizedDefault.absoluteString" in app_model
    assert "TextField(AppModel.defaultServerURLString" in login
    assert 'default="http://192.168.68.118:8002"' in smoke


def test_ios_no_pvp_release_gate_keeps_real_iphone_evidence_explicit():
    gate = (ROOT / "scripts/ios_no_pvp_release_gate.py").read_text(encoding="utf-8")

    assert 'DEFAULT_SERVER = "http://192.168.68.118:8002"' in gate
    assert "scripts/ios_no_pvp_http_smoke.py" in gate
    assert "xcodebuild_debug" in gate
    assert "xcodebuild_release" in gate
    assert "xcodebuild_release_device" in gate
    assert "xcodebuild_signed_release_device" in gate
    assert "--device-id" in gate
    assert "--signed-device-build" in gate
    assert "--install-signed-device-app" in gate
    assert "--include-sim-visual-smoke" in gate
    assert "scripts/ios_no_pvp_sim_visual_smoke.py" in gate
    assert "ios_no_pvp_sim_visual_smoke" in gate
    assert "devicectl_install_signed_device_app" in gate
    assert "machine_real_device_checks" in gate
    assert 'machine_real_device_checks["installed_release_build"] = True' in gate
    assert "machine_proven" in gate
    assert "machine_checks=machine_real_device_checks" in gate
    assert "CODE_SIGNING_ALLOWED=NO" in gate
    assert "signed_device_app" in gate
    assert "_collect_signed_app_summary" in gate
    assert "embedded.mobileprovision" in gate
    assert "profile_contains_destination_device" in gate
    assert "REAL_DEVICE_CHECKS" in gate
    assert "local_network_permission_allowed" in gate
    assert "camera_permission_allowed" in gate
    assert "login_against_8002" in gate
    assert "physical_qr_scanned" in gate
    assert "sync_retry_success" in gate
    assert "ready_for_players" in gate
    assert "/api/pvp" not in gate
    assert "/api/gwent" not in gate


def test_ios_no_pvp_player_server_status_hides_technical_revision():
    app_model = (ROOT / "ios/WitcherLARP/App/AppModel.swift").read_text(encoding="utf-8")
    status = app_model[
        app_model.index("var serverConnectionLabel"):
        app_model.index("init()")
    ]

    assert '"Сервер игры доступен."' in status
    assert "revision" not in status
    assert "Gwent" not in status
    assert "PvP" not in status


def test_ios_no_pvp_local_session_status_does_not_say_offline():
    home = (ROOT / "ios/WitcherLARP/Features/Home/HomeView.swift").read_text(encoding="utf-8")
    label = home[
        home.index("private func syncStateLabel"):
        home.index("private func syncStateIcon")
    ]
    icon = home[
        home.index("private func syncStateIcon"):
        home.index("private func roleLabel")
    ]

    assert 'return "на телефоне"' in label
    assert 'return "офлайн"' not in label
    assert 'return "iphone"' in icon


def test_ios_no_pvp_reputation_prefers_player_facing_canonical_label():
    models = (ROOT / "ios/WitcherLARP/Core/Models/SnapshotModels.swift").read_text(encoding="utf-8")
    reputation = models[
        models.index("reputationLabel = explicitReputation"):
        models.index('?? "Нейтральный"')
    ]

    assert reputation.index('string("canonical_label")') < reputation.index('string("player_descriptor")')
    assert reputation.index('string("canonical_label")') < reputation.index('string("state_label")')


def test_ios_qr_screen_is_camera_manual_only_and_has_keyboard_dismiss():
    qr = (ROOT / "ios/WitcherLARP/Features/QR/QRScannerSheet.swift").read_text(encoding="utf-8")

    assert 'Toggle("Камера", isOn: $useCamera)' in qr
    assert 'TextField("Короткий код объекта", text: $manualCode)' in qr
    assert 'Label("Применить код", systemImage: "checkmark.circle")' in qr
    assert 'Image(systemName: "keyboard.chevron.compact.down")' in qr
    assert ".keyboardType(.asciiCapable)" in qr
    assert "qrSpecificError" in qr
    assert "offlineNotice" in qr
    assert "foregroundStyle(.red)" not in qr
    assert "Проверка сервера" not in qr
    assert "Я физически у объекта" not in qr
    assert "Бросить d20" not in qr


def test_ios_qr_camera_scan_marks_source_before_updating_manual_code():
    qr = (ROOT / "ios/WitcherLARP/Features/QR/QRScannerSheet.swift").read_text(encoding="utf-8")
    scanner_callback = qr[
        qr.index("func handleScannedCode"):
        qr.index("func submitManualCode")
    ]

    assert "normalizeQRCode(rawCode)" in scanner_callback
    assert scanner_callback.index("inputSource = .camera") < scanner_callback.index("manualCode = normalized")
    assert "model.beginPVE(code: normalized, source: .camera)" in scanner_callback
