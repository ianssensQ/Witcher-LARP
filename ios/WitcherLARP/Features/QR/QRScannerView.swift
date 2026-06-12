import AVFoundation
import SwiftUI
import UIKit
import Vision

struct QRScannerView: UIViewControllerRepresentable {
    var onCode: (String) -> Void

    func makeUIViewController(context: Context) -> ScannerViewController {
        let controller = ScannerViewController()
        controller.onCode = onCode
        return controller
    }

    func updateUIViewController(_ uiViewController: ScannerViewController, context: Context) {}
}

final class ScannerViewController: UIViewController, AVCaptureMetadataOutputObjectsDelegate, AVCaptureVideoDataOutputSampleBufferDelegate {
    var onCode: ((String) -> Void)?

    private let session = AVCaptureSession()
    private var previewLayer: AVCaptureVideoPreviewLayer?
    private let statusLabel = UILabel()
    private let videoOutputQueue = DispatchQueue(label: "witcher.qr.video-output")
    private var isConfigured = false
    private var didEmitCode = false
    private var isRecognizingText = false
    private var lastTextScanAt = Date.distantPast

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = .black
        configureStatusLabel()
        requestCameraAccessIfNeeded()
    }

    override func viewDidLayoutSubviews() {
        super.viewDidLayoutSubviews()
        previewLayer?.frame = view.bounds
    }

    override func viewWillAppear(_ animated: Bool) {
        super.viewWillAppear(animated)
        didEmitCode = false
        startSessionIfPossible()
    }

    override func viewWillDisappear(_ animated: Bool) {
        super.viewWillDisappear(animated)
        if session.isRunning {
            stopSession()
        }
    }

    private func configureStatusLabel() {
        statusLabel.translatesAutoresizingMaskIntoConstraints = false
        statusLabel.text = "Наведи камеру на QR-код"
        statusLabel.textColor = .white
        statusLabel.font = .preferredFont(forTextStyle: .footnote)
        statusLabel.textAlignment = .center
        statusLabel.numberOfLines = 0
        statusLabel.backgroundColor = UIColor.black.withAlphaComponent(0.45)
        statusLabel.layer.cornerRadius = 8
        statusLabel.layer.masksToBounds = true
        view.addSubview(statusLabel)
        NSLayoutConstraint.activate([
            statusLabel.leadingAnchor.constraint(equalTo: view.leadingAnchor, constant: 16),
            statusLabel.trailingAnchor.constraint(equalTo: view.trailingAnchor, constant: -16),
            statusLabel.bottomAnchor.constraint(equalTo: view.bottomAnchor, constant: -16)
        ])
    }

    private func requestCameraAccessIfNeeded() {
        switch AVCaptureDevice.authorizationStatus(for: .video) {
        case .authorized:
            configureSession()
            startSessionIfPossible()
        case .notDetermined:
            AVCaptureDevice.requestAccess(for: .video) { [weak self] granted in
                DispatchQueue.main.async {
                    guard let self else { return }
                    if granted {
                        self.configureSession()
                        self.startSessionIfPossible()
                    } else {
                        self.showScannerError("Нет доступа к камере")
                    }
                }
            }
        default:
            showScannerError("Нет доступа к камере")
        }
    }

    private func startSessionIfPossible() {
        guard isConfigured, !session.isRunning else { return }
        DispatchQueue.global(qos: .userInitiated).async { self.session.startRunning() }
    }

    private func configureSession() {
        guard !isConfigured else { return }
        guard
            let device = AVCaptureDevice.default(.builtInWideAngleCamera, for: .video, position: .back)
                ?? AVCaptureDevice.default(for: .video),
            let input = try? AVCaptureDeviceInput(device: device),
            session.canAddInput(input)
        else {
            showScannerError("Камера недоступна")
            return
        }

        session.beginConfiguration()
        if session.canSetSessionPreset(.high) {
            session.sessionPreset = .high
        }

        session.addInput(input)
        configureCameraFocus(device)

        let output = AVCaptureMetadataOutput()
        guard session.canAddOutput(output) else {
            session.commitConfiguration()
            showScannerError("QR-сканер недоступен")
            return
        }
        session.addOutput(output)
        output.setMetadataObjectsDelegate(self, queue: DispatchQueue.main)
        if output.availableMetadataObjectTypes.contains(.qr) {
            output.metadataObjectTypes = [.qr]
        } else {
            session.commitConfiguration()
            showScannerError("Камера не поддерживает QR")
            return
        }

        let videoOutput = AVCaptureVideoDataOutput()
        videoOutput.alwaysDiscardsLateVideoFrames = true
        videoOutput.setSampleBufferDelegate(self, queue: videoOutputQueue)
        if session.canAddOutput(videoOutput) {
            session.addOutput(videoOutput)
        }
        session.commitConfiguration()

        let previewLayer = AVCaptureVideoPreviewLayer(session: session)
        previewLayer.videoGravity = .resizeAspectFill
        view.layer.insertSublayer(previewLayer, at: 0)
        self.previewLayer = previewLayer
        isConfigured = true
    }

    private func configureCameraFocus(_ device: AVCaptureDevice) {
        guard let _ = try? device.lockForConfiguration() else { return }
        if device.isFocusModeSupported(.continuousAutoFocus) {
            device.focusMode = .continuousAutoFocus
        }
        if device.isExposureModeSupported(.continuousAutoExposure) {
            device.exposureMode = .continuousAutoExposure
        }
        device.unlockForConfiguration()
    }

    private func showScannerError(_ message: String) {
        statusLabel.text = message
        statusLabel.textColor = .systemOrange
    }

    private func stopSession() {
        DispatchQueue.global(qos: .userInitiated).async {
            if self.session.isRunning {
                self.session.stopRunning()
            }
        }
    }

    private func emitCode(_ value: String, status: String) {
        DispatchQueue.main.async {
            guard !self.didEmitCode else { return }
            self.didEmitCode = true
            self.statusLabel.text = status
            self.statusLabel.textColor = .systemGreen
            self.stopSession()
            self.onCode?(value)
        }
    }

    func metadataOutput(
        _ output: AVCaptureMetadataOutput,
        didOutput metadataObjects: [AVMetadataObject],
        from connection: AVCaptureConnection
    ) {
        guard !didEmitCode else { return }
        guard
            let readable = metadataObjects.compactMap({ $0 as? AVMetadataMachineReadableCodeObject }).first,
            let value = readable.stringValue
        else { return }

        emitCode(value, status: "QR-код считан")
    }

    func captureOutput(
        _ output: AVCaptureOutput,
        didOutput sampleBuffer: CMSampleBuffer,
        from connection: AVCaptureConnection
    ) {
        guard !didEmitCode else { return }
        let now = Date()
        guard !isRecognizingText, now.timeIntervalSince(lastTextScanAt) > 0.8 else { return }
        guard let pixelBuffer = CMSampleBufferGetImageBuffer(sampleBuffer) else { return }
        isRecognizingText = true
        lastTextScanAt = now
        defer { isRecognizingText = false }

        for orientation in textRecognitionOrientations {
            if let code = recognizePrintedQRCode(in: pixelBuffer, orientation: orientation) {
                emitCode(code, status: "Код под QR считан")
                return
            }
        }
    }

    private var textRecognitionOrientations: [CGImagePropertyOrientation] {
        [.right, .up, .left]
    }

    private func recognizePrintedQRCode(
        in pixelBuffer: CVPixelBuffer,
        orientation: CGImagePropertyOrientation
    ) -> String? {
        let request = VNRecognizeTextRequest()
        request.recognitionLevel = .fast
        request.usesLanguageCorrection = false
        request.recognitionLanguages = ["en-US"]
        request.customWords = ["QR-A1", "QR-A2", "QR-A3"]

        let handler = VNImageRequestHandler(
            cvPixelBuffer: pixelBuffer,
            orientation: orientation,
            options: [:]
        )
        guard (try? handler.perform([request])) != nil else { return nil }
        let text = (request.results ?? [])
            .compactMap { $0.topCandidates(1).first?.string }
            .joined(separator: " ")
        return printedQRCode(in: text)
    }

    private func printedQRCode(in text: String) -> String? {
        let normalized = text
            .uppercased()
            .replacingOccurrences(of: " ", with: "")
            .replacingOccurrences(of: "–", with: "-")
            .replacingOccurrences(of: "—", with: "-")
            .replacingOccurrences(of: "_", with: "-")
        let pattern = #"QR-A[0-9]-[A-Z0-9]+(?:-[A-Z0-9]+)+"#
        guard let range = normalized.range(of: pattern, options: .regularExpression) else {
            return nil
        }
        return String(normalized[range])
    }
}
