import Foundation

enum QRCodeNormalizer {
    // Real OCR samples from printed cards:
    // QR-A1-ZPR420-F4C9ACT1ZERKALNYPRUD020QR -> QR-A1-ZPR-020-F4C9
    // QR-A2-SCI-019-K9Z2ACT2DVUKHYARNSNAYAMANUFAKTURA019QR -> QR-A2-SCI-019-K9Z2
    static func normalize(_ raw: String) -> String {
        let trimmed = raw.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return "" }

        if let components = URLComponents(string: trimmed) {
            let queryCode = components.queryItems?
                .first { ["code", "qr", "qr_id", "manual_code"].contains($0.name.lowercased()) }?
                .value
            if let queryCode, !queryCode.isEmpty {
                return normalize(queryCode)
            }
        }

        let uppercased = trimmed.uppercased()
            .replacingOccurrences(of: "–", with: "-")
            .replacingOccurrences(of: "—", with: "-")
            .replacingOccurrences(of: "_", with: "-")

        let canonicalPattern = #"QR-(?:A[0-9]|FA)-[A-Z0-9]{3}-[0-9]{3}-[A-Z0-9]{4}"#
        if let range = uppercased.firstRegexRange(canonicalPattern) {
            return String(uppercased[range])
        }
        if let recovered = recoverPrintedQRCode(from: uppercased) {
            return recovered
        }

        let patterns = [
            #"QR-[A-Z0-9]+(?:-[A-Z0-9]+)*"#,
            #"QR_[A-Z0-9_]+"#
        ]
        for pattern in patterns {
            if let range = uppercased.firstRegexRange(pattern) {
                return String(uppercased[range])
            }
        }
        return uppercased
    }

    static func recoverPrintedQRCode(from raw: String) -> String? {
        let compact = raw.filter { character in
            character.isASCII && (character.isLetter || character.isNumber)
        }
        let prefixPattern = #"QR(A[0-9]|FA)([A-Z]{3})"#
        guard let prefixRange = compact.firstRegexRange(prefixPattern) else {
            return nil
        }

        let prefix = String(compact[prefixRange])
        let body = String(prefix.dropFirst(2))
        let actToken = body.hasPrefix("FA") ? "FA" : String(body.prefix(2))
        let lane = String(body.dropFirst(actToken.count).prefix(3))
        let afterLane = String(compact[prefixRange.upperBound...])
        let secretPattern = #"[A-Z][0-9][A-Z][0-9]"#
        guard let secretRange = afterLane.firstRegexRange(secretPattern) else {
            return nil
        }

        let beforeSecret = String(afterLane[..<secretRange.lowerBound])
        let afterSecret = String(afterLane[secretRange.upperBound...])
        let secret = String(afterLane[secretRange])
        let repeatedSequence = repeatedSequenceAfterActLabel(afterSecret)
        let immediateSequence = beforeSecret.digitRuns(length: 3).last
        guard let sequence = repeatedSequence ?? immediateSequence else { return nil }
        return "QR-\(actToken)-\(lane)-\(sequence)-\(secret)"
    }

    private static func repeatedSequenceAfterActLabel(_ compactSuffix: String) -> String? {
        let searchRange: Substring
        if let actRange = compactSuffix.firstRegexRange(#"ACT[0-9]"#) {
            searchRange = compactSuffix[actRange.upperBound...]
        } else {
            searchRange = compactSuffix[compactSuffix.startIndex...]
        }
        return String(searchRange).digitRuns(length: 3).first
    }
}

private extension String {
    func firstRegexRange(_ pattern: String) -> Range<String.Index>? {
        guard let regex = try? NSRegularExpression(pattern: pattern) else { return nil }
        let fullRange = NSRange(startIndex..<endIndex, in: self)
        guard let match = regex.firstMatch(in: self, range: fullRange) else { return nil }
        return Range(match.range, in: self)
    }

    func digitRuns(length: Int) -> [String] {
        let pattern = #"\d{\#(length)}"#
        guard let regex = try? NSRegularExpression(pattern: pattern) else { return [] }
        let fullRange = NSRange(startIndex..<endIndex, in: self)
        return regex.matches(in: self, range: fullRange).compactMap { match in
            guard let range = Range(match.range, in: self) else { return nil }
            return String(self[range])
        }
    }
}
