import Foundation

struct AppConfig: Codable, Equatable, Sendable {
    var schemaVersion: Int
    var schedule: ScheduleConfig
    var audio: AudioConfig
    var provider: ProviderConfig
    var templates: [ReminderTemplate]
    var limits: LimitsConfig

    enum CodingKeys: String, CodingKey {
        case schemaVersion = "schema_version"
        case schedule, audio, provider, templates, limits
    }

    static let fallback = AppConfig(
        schemaVersion: 1,
        schedule: ScheduleConfig(
            dnd: DNDConfig(enabled: true, startMinute: 1320, endMinute: 480, stepMinutes: 15),
            musicHour: 17,
            lateToleranceMinutes: 3
        ),
        audio: AudioConfig(
            chimeFile: "hourly-chime.wav",
            musicFile: "hourly-music.wav",
            volume: 1,
            fallbackText: "Time to stay hydrated and drink some water.",
            voices: ["zh": "zh-CN-XiaoxiaoNeural", "en": "en-US-AvaNeural", "ja": "ja-JP-NanamiNeural"]
        ),
        provider: .openClaw,
        templates: [ReminderTemplate(id: "hydration-default", name: "喝水提醒", prompt: "Give me a short, simple and friendly reminder to drink water.", language: "en", enabled: true)],
        limits: LimitsConfig(maxDailyAICalls: 20)
    )
}

struct ScheduleConfig: Codable, Equatable, Sendable {
    var dnd: DNDConfig
    var musicHour: Int
    var lateToleranceMinutes: Int

    enum CodingKeys: String, CodingKey {
        case dnd
        case musicHour = "music_hour"
        case lateToleranceMinutes = "late_tolerance_minutes"
    }
}

struct DNDConfig: Codable, Equatable, Sendable {
    var enabled: Bool
    var startMinute: Int
    var endMinute: Int
    var stepMinutes: Int

    enum CodingKeys: String, CodingKey {
        case enabled
        case startMinute = "start_minute"
        case endMinute = "end_minute"
        case stepMinutes = "step_minutes"
    }

    var durationMinutes: Int { Self.forwardDistance(from: startMinute, to: endMinute) }

    static func wrapped(_ minute: Int) -> Int {
        let result = minute % 1440
        return result >= 0 ? result : result + 1440
    }

    static func forwardDistance(from start: Int, to end: Int) -> Int {
        wrapped(end - start)
    }

    static func snapped(_ minute: Int, step: Int = 15) -> Int {
        wrapped(Int((Double(minute) / Double(step)).rounded()) * step)
    }

    func moving(_ handle: DialHandle, to rawMinute: Int, snap: Bool) -> DNDConfig {
        var copy = self
        var candidate = DNDConfig.wrapped(rawMinute)
        if snap { candidate = DNDConfig.snapped(candidate, step: stepMinutes) }
        switch handle {
        case .start:
            let duration = DNDConfig.forwardDistance(from: candidate, to: endMinute)
            if duration < stepMinutes {
                candidate = DNDConfig.wrapped(endMinute - stepMinutes)
            } else if duration > 1440 - stepMinutes {
                candidate = DNDConfig.wrapped(endMinute + stepMinutes)
            }
            copy.startMinute = candidate
        case .end:
            let duration = DNDConfig.forwardDistance(from: startMinute, to: candidate)
            if duration < stepMinutes {
                candidate = DNDConfig.wrapped(startMinute + stepMinutes)
            } else if duration > 1440 - stepMinutes {
                candidate = DNDConfig.wrapped(startMinute - stepMinutes)
            }
            copy.endMinute = candidate
        }
        return copy
    }
}

enum DialHandle: Sendable { case start, end }

struct AudioConfig: Codable, Equatable, Sendable {
    var chimeFile: String
    var musicFile: String
    var volume: Double
    var fallbackText: String
    var voices: [String: String]

    enum CodingKeys: String, CodingKey {
        case chimeFile = "chime_file"
        case musicFile = "music_file"
        case volume
        case fallbackText = "fallback_text"
        case voices
    }
}

struct ProviderConfig: Codable, Equatable, Sendable {
    var kind: String
    var preset: String
    var baseURL: String
    var model: String
    var credentialID: String
    var timeoutSeconds: Int
    var codexPath: String
    var text: String?

    enum CodingKeys: String, CodingKey {
        case kind, preset, model, text
        case baseURL = "base_url"
        case credentialID = "credential_id"
        case timeoutSeconds = "timeout_seconds"
        case codexPath = "codex_path"
    }

    static let openClaw = ProviderConfig(kind: "openclaw", preset: "openclaw", baseURL: "", model: "", credentialID: "", timeoutSeconds: 25, codexPath: "", text: nil)
}

struct ReminderTemplate: Codable, Equatable, Identifiable, Sendable {
    var id: String
    var name: String
    var prompt: String
    var language: String
    var enabled: Bool
}

struct LimitsConfig: Codable, Equatable, Sendable {
    var maxDailyAICalls: Int
    enum CodingKeys: String, CodingKey { case maxDailyAICalls = "max_daily_ai_calls" }
}

struct ConfigEnvelope: Decodable, Sendable { let config: AppConfig }

struct StatusEnvelope: Decodable, Sendable {
    var ok: Bool
    var enabled: Bool
    var provider: String
    var nextPlayAt: String
    var cacheAvailable: Bool

    enum CodingKeys: String, CodingKey {
        case ok, enabled, provider
        case nextPlayAt = "next_play_at"
        case cacheAvailable = "cache_available"
    }
}

struct ProviderTestEnvelope: Decodable, Sendable {
    var ok: Bool
    var provider: String?
    var model: String?
    var latencyMS: Int?
    var sampleText: String?
    var errorCode: String?
    var message: String?

    enum CodingKeys: String, CodingKey {
        case ok, provider, model, message
        case latencyMS = "latency_ms"
        case sampleText = "sample_text"
        case errorCode = "error_code"
    }
}

enum ProviderPreset: String, CaseIterable, Identifiable {
    case openclaw = "OpenClaw"
    case codex = "Codex"
    case gemini = "Gemini"
    case nvidia = "NVIDIA"
    case custom = "Custom"
    var id: String { rawValue }

    static func from(_ config: ProviderConfig) -> ProviderPreset {
        if config.kind == "openclaw" { return .openclaw }
        if config.kind == "codex" { return .codex }
        return ProviderPreset(rawValue: config.preset.capitalized) ?? (config.preset == "nvidia" ? .nvidia : .custom)
    }
}

func formattedTime(_ minute: Int) -> String {
    String(format: "%02d:%02d", DNDConfig.wrapped(minute) / 60, DNDConfig.wrapped(minute) % 60)
}
