import Foundation
import Security

enum KeychainStore {
    static let legacyService = "com.andrewli.hourlychime.ai"

    private struct HelperEnvelope: Decodable {
        let ok: Bool
        let credentialAvailable: Bool?
        let errorCode: String?
        let message: String?

        enum CodingKeys: String, CodingKey {
            case ok, message
            case credentialAvailable = "credential_available"
            case errorCode = "error_code"
        }
    }

    private static var helperURL: URL {
        if let override = ProcessInfo.processInfo.environment["HOURLY_CHIME_KEYCHAIN_HELPER"], !override.isEmpty {
            return URL(fileURLWithPath: override)
        }
        return FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent("Library/Application Support/HourlyChime/bin/hourly-chime-keychain")
    }

    private static func runHelper(_ command: String, credentialID: String? = nil, input: Data? = nil) throws -> HelperEnvelope {
        guard FileManager.default.isExecutableFile(atPath: helperURL.path) else {
            throw CLIError(message: "找不到原生 Keychain Helper，请重新安装 Hourly Chime")
        }
        let process = Process()
        process.executableURL = helperURL
        process.arguments = [command] + (credentialID.map { [$0] } ?? [])
        let output = Pipe()
        let errors = Pipe()
        process.standardOutput = output
        process.standardError = errors
        if let input {
            let stdin = Pipe()
            process.standardInput = stdin
            try process.run()
            stdin.fileHandleForWriting.write(input)
            try stdin.fileHandleForWriting.close()
        } else {
            try process.run()
        }
        process.waitUntilExit()
        let data = output.fileHandleForReading.readDataToEndOfFile()
        let envelope: HelperEnvelope
        do {
            envelope = try JSONDecoder().decode(HelperEnvelope.self, from: data)
        } catch {
            throw CLIError(message: "Keychain Helper 返回格式无效")
        }
        guard envelope.ok else {
            throw CLIError(message: envelope.message ?? "Keychain Helper 执行失败")
        }
        return envelope
    }

    static func save(_ secret: String, credentialID: String) throws {
        _ = try runHelper("save", credentialID: credentialID, input: Data(secret.utf8))
    }

    static func delete(credentialID: String) {
        guard !credentialID.isEmpty else { return }
        _ = try? runHelper("delete", credentialID: credentialID)
        deleteLegacy(credentialID: credentialID)
    }

    static func migrateLegacyIfNeeded(credentialID: String) throws -> Bool {
        guard !credentialID.isEmpty else { return false }
        if try runHelper("status").credentialAvailable == true { return false }
        guard let secret = try readLegacy(credentialID: credentialID) else {
            throw CLIError(message: "Keychain Helper 中没有当前 API Key，请在 Provider 页面重新输入并保存")
        }
        try save(secret, credentialID: credentialID)
        guard try runHelper("status").credentialAvailable == true else {
            throw CLIError(message: "API Key 迁移后校验失败")
        }
        deleteLegacy(credentialID: credentialID)
        return true
    }

    private static func readLegacy(credentialID: String) throws -> String? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: legacyService,
            kSecAttrAccount as String: credentialID,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne,
        ]
        var result: CFTypeRef?
        let status = SecItemCopyMatching(query as CFDictionary, &result)
        if status == errSecItemNotFound { return nil }
        guard status == errSecSuccess, let data = result as? Data, let secret = String(data: data, encoding: .utf8) else {
            throw CLIError(message: "无法读取旧版 Keychain 项（\(status)）")
        }
        return secret
    }

    private static func deleteLegacy(credentialID: String) {
        SecItemDelete([
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: legacyService,
            kSecAttrAccount as String: credentialID,
        ] as CFDictionary)
    }
}
