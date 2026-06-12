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
        "ios/WitcherLARP/Features/QR/QRScannerView.swift",
    ]

    for relative_path in expected:
        assert (ROOT / relative_path).exists(), relative_path


def test_ios_scaffold_uses_native_qr_and_local_network_permissions():
    scanner = (ROOT / "ios/WitcherLARP/Features/QR/QRScannerView.swift").read_text(encoding="utf-8")
    plist = (ROOT / "ios/Resources/Info.plist").read_text(encoding="utf-8")

    assert "AVFoundation" in scanner
    assert "AVCaptureMetadataOutput" in scanner
    assert "NSCameraUsageDescription" in plist
    assert "NSLocalNetworkUsageDescription" in plist


def test_ios_qr_lookup_renders_pve_card_contract():
    api_client = (ROOT / "ios/WitcherLARP/Core/API/LarpAPIClient.swift").read_text(
        encoding="utf-8"
    )
    api_models = (ROOT / "ios/WitcherLARP/Core/Models/APIModels.swift").read_text(
        encoding="utf-8"
    )
    snapshot_models = (
        ROOT / "ios/WitcherLARP/Core/Models/SnapshotModels.swift"
    ).read_text(encoding="utf-8")
    app_model = (ROOT / "ios/WitcherLARP/App/AppModel.swift").read_text(encoding="utf-8")
    qr_sheet = (ROOT / "ios/WitcherLARP/Features/QR/QRScannerSheet.swift").read_text(
        encoding="utf-8"
    )
    home_view = (ROOT / "ios/WitcherLARP/Features/Home/HomeView.swift").read_text(
        encoding="utf-8"
    )

    assert "func lookupQR(" in api_client
    assert '"/api/qr/lookup"' in api_client
    assert '"X-Player-Code"' in api_client
    assert "struct QRLookupRequest" in api_models
    assert "struct QRLookupResponse" in api_models
    assert "struct PvEScenarioCard" in snapshot_models
    assert "scenarioTitle = \"scenario_title\"" in snapshot_models
    assert "rewardSummary = \"reward_summary\"" in snapshot_models
    assert "scanReveal = \"scan_reveal\"" in snapshot_models
    assert "choiceOptionsJSON = \"choice_options_json\"" in snapshot_models
    assert "encounterStepsJSON = \"encounter_steps_json\"" in snapshot_models
    assert "victoryRule = \"victory_rule\"" in snapshot_models
    assert "func lookupQRCode" in app_model
    assert "savePlayerCode" in app_model
    assert "lookupQRCode(normalized" in qr_sheet
    assert "questCard(quest)" in home_view


def test_ios_plan_marks_godot_as_legacy_not_deleted():
    plan = (ROOT / "docs/ios-native-plan.md").read_text(encoding="utf-8")

    assert "iOS-приложение" in plan
    assert "SwiftUI" in plan
    assert "Godot" in plan
    assert "legacy/reference" in plan
    assert "Android выходит из scope" in plan
