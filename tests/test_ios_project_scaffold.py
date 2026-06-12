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


def test_ios_plan_marks_godot_as_legacy_not_deleted():
    plan = (ROOT / "docs/ios-native-plan.md").read_text(encoding="utf-8")

    assert "iOS-приложение" in plan
    assert "SwiftUI" in plan
    assert "Godot" in plan
    assert "legacy/reference" in plan
    assert "Android выходит из scope" in plan
