import Foundation
import Security

enum KeychainStore {
    static let service = "com.andrewli.hourlychime.ai"

    static func save(_ secret: String, credentialID: String) throws {
        let base: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: credentialID,
        ]
        SecItemDelete(base as CFDictionary)
        var item = base
        item[kSecValueData as String] = Data(secret.utf8)
        item[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly
        let status = SecItemAdd(item as CFDictionary, nil)
        guard status == errSecSuccess else { throw CLIError(message: "无法写入钥匙串（\(status)）") }
    }

    static func delete(credentialID: String) {
        guard !credentialID.isEmpty else { return }
        SecItemDelete([
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: credentialID,
        ] as CFDictionary)
    }
}
