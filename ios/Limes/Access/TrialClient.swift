import CryptoKit
import Foundation
import Security

/// Asks the trial ledger (server/) when this device's free trial ends. The
/// device is known by a hash of a random ID kept in the keychain, which stays
/// when the app is deleted, so a reinstall gets the same trial back.
struct TrialClient {
    let url: URL

    struct Failure: Error {}

    /// When the trial ends; the first call starts it.
    func register() async throws -> Date {
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.timeoutInterval = 15
        request.setValue("application/json", forHTTPHeaderField: "content-type")
        request.httpBody = try JSONSerialization.data(withJSONObject: ["id": try Self.deviceHash(), "platform": "ios"])
        let (data, response) = try await URLSession.shared.data(for: request)
        guard (response as? HTTPURLResponse)?.statusCode == 200,
              let body = try JSONSerialization.jsonObject(with: data) as? [String: Any],
              let text = body["trial_ends"] as? String,
              let ends = Self.parse(text)
        else { throw Failure() }
        return ends
    }

    private static func parse(_ text: String) -> Date? {
        let format = ISO8601DateFormatter()
        format.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        if let date = format.date(from: text) { return date }
        format.formatOptions = [.withInternetDateTime]
        return format.date(from: text)
    }

    /// Only the hash leaves the device, prefixed so it matches no other app's.
    private static func deviceHash() throws -> String {
        let digest = SHA256.hash(data: Data("limes:\(try deviceID())".utf8))
        return digest.map { String(format: "%02x", $0) }.joined()
    }

    private static let item: [String: Any] = [
        kSecClass as String: kSecClassGenericPassword,
        kSecAttrService as String: "com.osprey74.limes",
        kSecAttrAccount as String: "device-id",
    ]

    /// The ID in the keychain, made on first use. Readable after the first
    /// unlock, and carried to a new device by a backup, where the same trial
    /// then continues.
    private static func deviceID() throws -> String {
        var query = item
        query[kSecReturnData as String] = true
        query[kSecMatchLimit as String] = kSecMatchLimitOne
        var found: CFTypeRef?
        let status = SecItemCopyMatching(query as CFDictionary, &found)
        if status == errSecSuccess, let data = found as? Data, let id = String(data: data, encoding: .utf8) {
            return id
        }
        // Anything but "not there" (e.g. locked before the first unlock):
        // do not make a second ID.
        guard status == errSecItemNotFound else { throw Failure() }
        let id = UUID().uuidString
        var add = item
        add[kSecValueData as String] = Data(id.utf8)
        add[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlock
        guard SecItemAdd(add as CFDictionary, nil) == errSecSuccess else { throw Failure() }
        return id
    }
}
