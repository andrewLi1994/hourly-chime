import Combine
import Foundation

@MainActor
final class ConfigStore: ObservableObject {
    @Published var config = AppConfig.fallback
    @Published var status: StatusEnvelope?
    @Published var isBusy = false
    @Published var banner: String?
    @Published var previewText: String?
    @Published var errorMessage: String?
    @Published var diagnostics = "尚未运行诊断"

    let client: CLIClient

    init(client: CLIClient = CLIClient()) {
        self.client = client
    }

    func load() {
        isBusy = true
        let client = client
        Task {
            do {
                async let configEnvelope: ConfigEnvelope = Task.detached { try client.decode(ConfigEnvelope.self, arguments: ["config", "get"]) }.value
                async let statusEnvelope: StatusEnvelope = Task.detached { try client.decode(StatusEnvelope.self, arguments: ["status", "--json"]) }.value
                config = try await configEnvelope.config
                status = try await statusEnvelope
                errorMessage = nil
            } catch {
                errorMessage = "无法连接后台工具：\(error.localizedDescription)"
            }
            isBusy = false
        }
    }

    func save(_ candidate: AppConfig, rollback: AppConfig? = nil, message: String = "设置已保存") {
        let previous = rollback ?? config
        config = candidate
        isBusy = true
        let client = client
        Task {
            do {
                let data = try JSONEncoder().encode(candidate)
                _ = try await Task.detached { try client.run(["config", "apply"], stdin: data) }.value
                banner = message
                errorMessage = nil
            } catch {
                config = previous
                errorMessage = "保存失败，已恢复原设置：\(error.localizedDescription)"
            }
            isBusy = false
        }
    }

    func setEnabled(_ enabled: Bool) {
        isBusy = true
        let client = client
        Task {
            do {
                _ = try await Task.detached { try client.run([enabled ? "enable" : "disable", "--json"]) }.value
                banner = enabled ? "整点播报已启用" : "整点播报已暂停"
                refreshStatus()
            } catch {
                errorMessage = error.localizedDescription
            }
            isBusy = false
        }
    }

    func runTest(_ kind: String) {
        isBusy = true
        let client = client
        Task {
            do {
                _ = try await Task.detached { try client.run(["test", kind, "--json"]) }.value
                banner = "测试播放完成"
            } catch {
                errorMessage = error.localizedDescription
            }
            isBusy = false
        }
    }

    func refreshCache() {
        isBusy = true
        let client = client
        Task {
            do {
                _ = try await Task.detached { try client.run(["refresh", "--json"]) }.value
                banner = "语音缓存已刷新"
                refreshStatus()
            } catch {
                errorMessage = error.localizedDescription
            }
            isBusy = false
        }
    }

    func refreshStatus() {
        let client = client
        Task {
            status = try? await Task.detached { try client.decode(StatusEnvelope.self, arguments: ["status", "--json"]) }.value
        }
    }

    func runDoctor() {
        isBusy = true
        let client = client
        Task {
            do {
                let data = try await Task.detached { try client.run(["doctor", "--json"]) }.value
                let object = try JSONSerialization.jsonObject(with: data)
                let pretty = try JSONSerialization.data(withJSONObject: object, options: [.prettyPrinted, .sortedKeys])
                diagnostics = String(data: pretty, encoding: .utf8) ?? "诊断完成"
            } catch {
                // doctor intentionally exits non-zero when a check fails. Its JSON is
                // surfaced by CLIError, so keep that evidence visible in this panel.
                diagnostics = error.localizedDescription
            }
            isBusy = false
        }
    }

    func testProvider(_ provider: ProviderConfig, template: ReminderTemplate, apiKey: String) async -> Bool {
        isBusy = true
        defer { isBusy = false }
        previewText = nil
        let payload: [String: Any] = [
            "provider": [
                "kind": provider.kind,
                "preset": provider.preset,
                "base_url": provider.baseURL,
                "model": provider.model,
                "credential_id": provider.credentialID,
                "timeout_seconds": provider.timeoutSeconds,
                "codex_path": provider.codexPath,
            ],
            "template": ["prompt": template.prompt, "language": template.language],
            "api_key": apiKey,
        ]
        do {
            let input = try JSONSerialization.data(withJSONObject: payload)
            let client = client
            let result: ProviderTestEnvelope = try await Task.detached {
                try client.decode(ProviderTestEnvelope.self, arguments: ["provider", "test", "--stdin-json"], stdin: input)
            }.value
            guard result.ok else { throw CLIError(message: result.message ?? "Provider 测试失败") }
            previewText = result.sampleText ?? "测试成功"
            banner = "Provider 测试成功"
            errorMessage = nil
            return true
        } catch {
            errorMessage = "Provider 测试失败：\(error.localizedDescription)"
            return false
        }
    }

    func saveProvider(_ provider: ProviderConfig, apiKey: String) async {
        isBusy = true
        defer { isBusy = false }
        var candidate = config
        var provider = provider
        let oldCredential = config.provider.credentialID
        var newCredential = ""
        do {
            if provider.kind == "openai_compatible" {
                guard !apiKey.isEmpty else { throw CLIError(message: "API Key 不能为空") }
                newCredential = UUID().uuidString
                try KeychainStore.save(apiKey, credentialID: newCredential)
                provider.credentialID = newCredential
            } else {
                provider.credentialID = ""
            }
            candidate.provider = provider
            let input = try JSONEncoder().encode(candidate)
            let client = client
            _ = try await Task.detached { try client.run(["config", "apply"], stdin: input) }.value
            config = candidate
            if oldCredential != newCredential { KeychainStore.delete(credentialID: oldCredential) }
            banner = "Provider 已保存"
            errorMessage = nil
        } catch {
            if !newCredential.isEmpty { KeychainStore.delete(credentialID: newCredential) }
            errorMessage = "Provider 保存失败：\(error.localizedDescription)"
        }
    }
}
