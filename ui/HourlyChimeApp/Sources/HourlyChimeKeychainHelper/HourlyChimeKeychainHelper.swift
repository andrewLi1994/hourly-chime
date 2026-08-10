import Foundation
import Security

private let service = "com.andrewli.hourlychime.ai.helper.v1"

private struct ProviderConfig: Decodable {
    let kind: String
    let preset: String
    let baseURL: String
    let model: String
    let credentialID: String
    let timeoutSeconds: Int

    enum CodingKeys: String, CodingKey {
        case kind, preset, model
        case baseURL = "base_url"
        case credentialID = "credential_id"
        case timeoutSeconds = "timeout_seconds"
    }
}

private struct ConfigFile: Decodable { let provider: ProviderConfig }
private struct GenerateInput: Decodable { let prompt: String }

private struct ChatRequest: Encodable {
    struct Message: Encodable { let role: String; let content: String }
    let model: String
    let messages: [Message]
    let maxTokens: Int
    let temperature: Double
    let stream: Bool
    let reasoningEffort: String?

    enum CodingKeys: String, CodingKey {
        case model, messages, temperature, stream
        case maxTokens = "max_tokens"
        case reasoningEffort = "reasoning_effort"
    }
}

private struct ChatResponse: Decodable {
    struct Choice: Decodable {
        struct Message: Decodable { let content: String }
        let finishReason: String?
        let message: Message
        enum CodingKeys: String, CodingKey {
            case message
            case finishReason = "finish_reason"
        }
    }
    let choices: [Choice]
}

private struct HelperResponse: Encodable {
    let ok: Bool
    var credentialAvailable: Bool? = nil
    var content: String? = nil
    var finishReason: String? = nil
    var latencyMS: Int? = nil
    var provider: String? = nil
    var model: String? = nil
    var errorCode: String? = nil
    var message: String? = nil

    enum CodingKeys: String, CodingKey {
        case ok, content, provider, model, message
        case credentialAvailable = "credential_available"
        case finishReason = "finish_reason"
        case latencyMS = "latency_ms"
        case errorCode = "error_code"
    }
}

private enum HelperFailure: Error {
    case classified(String, String)
}

private func emit(_ response: HelperResponse) {
    let encoder = JSONEncoder()
    guard let data = try? encoder.encode(response) else { return }
    FileHandle.standardOutput.write(data)
    FileHandle.standardOutput.write(Data([0x0A]))
}

private func baseQuery(_ credentialID: String) -> [String: Any] {
    [
        kSecClass as String: kSecClassGenericPassword,
        kSecAttrService as String: service,
        kSecAttrAccount as String: credentialID,
    ]
}

private func saveSecret(_ secret: String, credentialID: String) throws {
    guard !credentialID.isEmpty, !secret.isEmpty, secret.utf8.count <= 16_384 else {
        throw HelperFailure.classified("invalid_input", "API Key 或 credential_id 无效")
    }
    let query = baseQuery(credentialID)
    SecItemDelete(query as CFDictionary)
    var item = query
    item[kSecValueData as String] = Data(secret.utf8)
    item[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly
    let status = SecItemAdd(item as CFDictionary, nil)
    guard status == errSecSuccess else {
        throw HelperFailure.classified("keychain", "无法写入 Keychain（\(status)）")
    }
}

private func readSecret(_ credentialID: String) throws -> String {
    var query = baseQuery(credentialID)
    query[kSecReturnData as String] = true
    query[kSecMatchLimit as String] = kSecMatchLimitOne
    var result: CFTypeRef?
    let status = SecItemCopyMatching(query as CFDictionary, &result)
    guard status == errSecSuccess, let data = result as? Data, let secret = String(data: data, encoding: .utf8), !secret.isEmpty else {
        throw HelperFailure.classified("keychain", "Keychain 中未找到当前 Provider 的 API Key")
    }
    return secret
}

private func deleteSecret(_ credentialID: String) throws {
    let status = SecItemDelete(baseQuery(credentialID) as CFDictionary)
    guard status == errSecSuccess || status == errSecItemNotFound else {
        throw HelperFailure.classified("keychain", "无法删除 Keychain 项（\(status)）")
    }
}

private func appHome() -> URL {
    if let override = ProcessInfo.processInfo.environment["HOURLY_CHIME_HOME"], !override.isEmpty {
        return URL(fileURLWithPath: override, isDirectory: true)
    }
    return FileManager.default.homeDirectoryForCurrentUser
        .appendingPathComponent("Library/Application Support/HourlyChime", isDirectory: true)
}

private func loadProvider() throws -> ProviderConfig {
    let data: Data
    do {
        data = try Data(contentsOf: appHome().appendingPathComponent("config.json"))
    } catch {
        throw HelperFailure.classified("not_configured", "无法读取 Hourly Chime 配置")
    }
    let provider: ProviderConfig
    do {
        provider = try JSONDecoder().decode(ConfigFile.self, from: data).provider
    } catch {
        throw HelperFailure.classified("not_configured", "Provider 配置格式无效")
    }
    guard provider.kind == "openai_compatible", !provider.credentialID.isEmpty else {
        throw HelperFailure.classified("not_configured", "当前 Provider 不使用 Keychain Helper")
    }
    return provider
}

private func endpoint(for baseURL: String) throws -> URL {
    let trimmed = baseURL.trimmingCharacters(in: CharacterSet(charactersIn: "/"))
    guard var components = URLComponents(string: trimmed), let host = components.host?.lowercased() else {
        throw HelperFailure.classified("not_configured", "Provider URL 无效")
    }
    let localHosts = ["localhost", "127.0.0.1", "::1"]
    guard components.scheme?.lowercased() == "https" || (components.scheme?.lowercased() == "http" && localHosts.contains(host)) else {
        throw HelperFailure.classified("not_configured", "Provider URL 必须使用 HTTPS；本机地址除外")
    }
    if !trimmed.hasSuffix("/chat/completions") {
        components.path = components.path.trimmingCharacters(in: CharacterSet(charactersIn: "/")) + "/chat/completions"
        if !components.path.hasPrefix("/") { components.path = "/" + components.path }
    }
    guard let url = components.url else {
        throw HelperFailure.classified("not_configured", "Provider URL 无效")
    }
    return url
}

private func callProvider(input: GenerateInput) async throws -> HelperResponse {
    guard !input.prompt.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty, input.prompt.count <= 2_000 else {
        throw HelperFailure.classified("invalid_input", "提示词无效")
    }
    let provider = try loadProvider()
    let secret = try readSecret(provider.credentialID)
    let reasoning: String? = provider.preset == "gemini"
        ? (provider.model.lowercased().contains("gemini-2.5-flash") ? "none" : "low")
        : nil
    let body = ChatRequest(
        model: provider.model,
        messages: [.init(role: "user", content: input.prompt)],
        maxTokens: 192,
        temperature: 0.8,
        stream: false,
        reasoningEffort: reasoning
    )
    var request = URLRequest(url: try endpoint(for: provider.baseURL))
    request.httpMethod = "POST"
    request.timeoutInterval = TimeInterval(provider.timeoutSeconds)
    request.setValue("Bearer \(secret)", forHTTPHeaderField: "Authorization")
    request.setValue("application/json", forHTTPHeaderField: "Content-Type")
    request.setValue("application/json", forHTTPHeaderField: "Accept")
    request.httpBody = try JSONEncoder().encode(body)

    let started = Date()
    let data: Data
    let response: URLResponse
    do {
        (data, response) = try await URLSession.shared.data(for: request)
    } catch let error as URLError where error.code == .timedOut {
        throw HelperFailure.classified("timeout", "Provider 调用超时")
    } catch {
        throw HelperFailure.classified("network", "Provider 网络错误")
    }
    guard let http = response as? HTTPURLResponse else {
        throw HelperFailure.classified("network", "Provider 未返回 HTTP 响应")
    }
    if http.statusCode == 401 || http.statusCode == 403 {
        throw HelperFailure.classified("auth", "Provider 认证失败")
    }
    if http.statusCode == 429 {
        throw HelperFailure.classified("rate_limit", "Provider 已达到速率限制")
    }
    guard (200..<300).contains(http.statusCode) else {
        throw HelperFailure.classified("network", "Provider 返回 HTTP \(http.statusCode)")
    }
    let decoded: ChatResponse
    do {
        decoded = try JSONDecoder().decode(ChatResponse.self, from: data)
    } catch {
        throw HelperFailure.classified("invalid_response", "Provider 响应格式不兼容")
    }
    guard let choice = decoded.choices.first else {
        throw HelperFailure.classified("invalid_response", "Provider 响应缺少文本")
    }
    return HelperResponse(
        ok: true,
        content: choice.message.content,
        finishReason: choice.finishReason,
        latencyMS: Int(Date().timeIntervalSince(started) * 1_000),
        provider: provider.preset,
        model: provider.model
    )
}

@main
private struct HourlyChimeKeychainHelper {
    static func main() async {
        do {
            let arguments = CommandLine.arguments
            guard arguments.count >= 2 else {
                throw HelperFailure.classified("invalid_input", "缺少 Helper 命令")
            }
            switch arguments[1] {
            case "save":
                guard arguments.count == 3 else { throw HelperFailure.classified("invalid_input", "缺少 credential_id") }
                let input = FileHandle.standardInput.readDataToEndOfFile()
                guard let secret = String(data: input, encoding: .utf8)?.trimmingCharacters(in: .whitespacesAndNewlines) else {
                    throw HelperFailure.classified("invalid_input", "API Key 编码无效")
                }
                try saveSecret(secret, credentialID: arguments[2])
                emit(HelperResponse(ok: true))
            case "delete":
                guard arguments.count == 3 else { throw HelperFailure.classified("invalid_input", "缺少 credential_id") }
                try deleteSecret(arguments[2])
                emit(HelperResponse(ok: true))
            case "status":
                let provider = try loadProvider()
                let available = (try? readSecret(provider.credentialID)) != nil
                emit(HelperResponse(ok: true, credentialAvailable: available))
            case "generate":
                let input = try JSONDecoder().decode(GenerateInput.self, from: FileHandle.standardInput.readDataToEndOfFile())
                emit(try await callProvider(input: input))
            default:
                throw HelperFailure.classified("invalid_input", "未知 Helper 命令")
            }
        } catch HelperFailure.classified(let code, let message) {
            emit(HelperResponse(ok: false, errorCode: code, message: message))
        } catch {
            emit(HelperResponse(ok: false, errorCode: "helper_error", message: "Keychain Helper 执行失败"))
        }
    }
}
