import AppKit
import SwiftUI

struct ContentView: View {
    @ObservedObject var store: ConfigStore

    var body: some View {
        VStack(spacing: 0) {
            if let error = store.errorMessage {
                Banner(text: error, color: .red, dismiss: { store.errorMessage = nil })
            } else if let message = store.banner {
                Banner(text: message, color: .accentColor, dismiss: { store.banner = nil })
            }
            if let preview = store.previewText {
                PreviewBanner(text: preview, dismiss: { store.previewText = nil })
            }

            TabView {
                GeneralSettingsView(store: store)
                    .tabItem { Label("常规", systemImage: "clock") }
                TemplatesView(store: store)
                    .tabItem { Label("提醒模板", systemImage: "text.bubble") }
                ProviderSettingsView(store: store)
                    .tabItem { Label("AI Provider", systemImage: "sparkles") }
                DiagnosticsView(store: store)
                    .tabItem { Label("诊断", systemImage: "stethoscope") }
            }
            .padding(20)
        }
        .frame(minWidth: 720, minHeight: 680)
        .task { store.load() }
    }
}

private struct Banner: View {
    let text: String
    let color: Color
    let dismiss: () -> Void
    var body: some View {
        HStack {
            Text(text)
                .fixedSize(horizontal: false, vertical: true)
            Spacer()
            Button(action: dismiss) { Image(systemName: "xmark") }.buttonStyle(.plain)
        }
        .font(.callout)
        .padding(.horizontal, 16)
        .padding(.vertical, 10)
        .background(color.opacity(0.12))
    }
}

private struct PreviewBanner: View {
    let text: String
    let dismiss: () -> Void

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            Image(systemName: "quote.bubble.fill")
                .foregroundStyle(.tint)
                .padding(.top, 2)
            VStack(alignment: .leading, spacing: 3) {
                Text("完整预览")
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(.secondary)
                Text(text)
                    .font(.body)
                    .textSelection(.enabled)
                    .fixedSize(horizontal: false, vertical: true)
                    .frame(maxWidth: .infinity, alignment: .leading)
            }
            Button(action: dismiss) { Image(systemName: "xmark") }
                .buttonStyle(.plain)
                .accessibilityLabel("关闭预览")
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 12)
        .background(Color.accentColor.opacity(0.10))
    }
}

struct GeneralSettingsView: View {
    @ObservedObject var store: ConfigStore

    private var dndBinding: Binding<DNDConfig> {
        Binding(
            get: { store.config.schedule.dnd },
            set: { store.config.schedule.dnd = $0 }
        )
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                HStack {
                    VStack(alignment: .leading, spacing: 4) {
                        Text("静音时段").font(.title2.weight(.semibold))
                        Text("每天使用同一套连续时段；拖动后吸附到 15 分钟刻度。")
                            .foregroundStyle(.secondary)
                    }
                    Spacer()
                    Toggle("启用", isOn: Binding(
                        get: { store.config.schedule.dnd.enabled },
                        set: { enabled in
                            let previous = store.config
                            var candidate = store.config
                            candidate.schedule.dnd.enabled = enabled
                            store.save(candidate, rollback: previous)
                        }
                    ))
                    .toggleStyle(.switch)
                }

                QuietHoursDial(dnd: dndBinding) { oldDND, newDND in
                    var previous = store.config
                    previous.schedule.dnd = oldDND
                    var candidate = store.config
                    candidate.schedule.dnd = newDND
                    store.save(candidate, rollback: previous, message: "静音时段已保存")
                }

                Divider()
                Grid(alignment: .leading, horizontalSpacing: 24, verticalSpacing: 16) {
                    GridRow {
                        Text("音乐时间")
                        Picker("音乐时间", selection: Binding(
                            get: { store.config.schedule.musicHour },
                            set: { hour in
                                let previous = store.config
                                var candidate = store.config
                                candidate.schedule.musicHour = hour
                                store.save(candidate, rollback: previous)
                            }
                        )) {
                            ForEach(0..<24, id: \.self) { hour in Text(String(format: "%02d:00", hour)).tag(hour) }
                        }
                        .labelsHidden().frame(width: 130)
                    }
                    GridRow {
                        Text("播放音量")
                        HStack {
                            Image(systemName: "speaker.fill")
                            Slider(value: Binding(
                                get: { store.config.audio.volume },
                                set: { store.config.audio.volume = $0 }
                            ), in: 0...1, onEditingChanged: { editing in
                                if !editing { store.save(store.config, message: "音量已保存") }
                            })
                            Image(systemName: "speaker.wave.3.fill")
                            Text("\(Int(store.config.audio.volume * 100))%")
                                .monospacedDigit().frame(width: 42, alignment: .trailing)
                        }
                    }
                }
            }
            .padding(8)
        }
    }
}

struct TemplatesView: View {
    @ObservedObject var store: ConfigStore
    @State private var selection: String?

    var body: some View {
        HSplitView {
            VStack(spacing: 8) {
                List(store.config.templates, selection: $selection) { template in
                    HStack {
                        Image(systemName: template.enabled ? "checkmark.circle.fill" : "circle")
                            .foregroundStyle(template.enabled ? .green : .secondary)
                        Text(template.name)
                    }.tag(template.id)
                }
                HStack {
                    Button(action: addTemplate) { Image(systemName: "plus") }
                    Button(action: removeTemplate) { Image(systemName: "minus") }.disabled(selection == nil || store.config.templates.count == 1)
                    Spacer()
                }
            }
            .frame(minWidth: 190)

            if let index = selectedIndex {
                Form {
                    TextField("名称", text: binding(index, \.name))
                    TextEditor(text: binding(index, \.prompt)).frame(minHeight: 150)
                    Picker("输出语言", selection: binding(index, \.language)) {
                        Text("简体中文").tag("zh")
                        Text("English").tag("en")
                        Text("日本語").tag("ja")
                    }
                    Toggle("启用此模板", isOn: binding(index, \.enabled))
                    HStack {
                        Button("测试并预览") {
                            Task { _ = await store.testProvider(store.config.provider, template: store.config.templates[index], apiKey: "") }
                        }
                        Spacer()
                        Button("保存模板") { store.save(store.config, message: "模板已保存") }.buttonStyle(.borderedProminent)
                    }
                }
                .padding()
                .frame(minWidth: 420)
            } else {
                ContentUnavailableView("选择一个模板", systemImage: "text.bubble")
            }
        }
        .onAppear { selection = selection ?? store.config.templates.first?.id }
    }

    private var selectedIndex: Int? { store.config.templates.firstIndex { $0.id == selection } }

    private func binding<Value>(_ index: Int, _ keyPath: WritableKeyPath<ReminderTemplate, Value>) -> Binding<Value> {
        Binding(get: { store.config.templates[index][keyPath: keyPath] }, set: { store.config.templates[index][keyPath: keyPath] = $0 })
    }

    private func addTemplate() {
        let item = ReminderTemplate(id: UUID().uuidString, name: "新提醒", prompt: "写一句简短友好的提醒。", language: "zh", enabled: true)
        store.config.templates.append(item)
        selection = item.id
    }

    private func removeTemplate() {
        guard let index = selectedIndex else { return }
        store.config.templates.remove(at: index)
        selection = store.config.templates.first?.id
        store.save(store.config, message: "模板已删除")
    }
}

struct ProviderSettingsView: View {
    @ObservedObject var store: ConfigStore
    @State private var preset: ProviderPreset = .openclaw
    @State private var draft = ProviderConfig.openClaw
    @State private var apiKey = ""
    @State private var testedSignature = ""
    @State private var testTemplateID = ""

    private var needsKey: Bool { [.gemini, .nvidia, .custom].contains(preset) }
    private var signature: String { "\(preset.rawValue)|\(draft.baseURL)|\(draft.model)|\(apiKey)" }

    var body: some View {
        Form {
            Picker("Provider", selection: $preset) {
                ForEach(ProviderPreset.allCases) { item in Text(item.rawValue).tag(item) }
            }
            .onChange(of: preset) { _, value in configure(value); testedSignature = "" }

            if preset == .codex {
                TextField("Codex 路径（留空自动发现）", text: $draft.codexPath)
                Text("复用当前 ChatGPT 登录；提示词通过 stdin 发送，并在隔离的只读空目录中运行。")
                    .font(.caption).foregroundStyle(.secondary)
            }
            if needsKey {
                TextField("Base URL", text: $draft.baseURL)
                TextField("模型", text: $draft.model)
                SecureField("API Key（保存到 macOS 钥匙串）", text: $apiKey)
            }
            if preset == .openclaw {
                Text("使用本机 OpenClaw main agent。")
                    .font(.callout).foregroundStyle(.secondary)
            }

            Picker("测试模板", selection: $testTemplateID) {
                ForEach(store.config.templates) { template in
                    Text(template.enabled ? template.name : "\(template.name)（未启用）").tag(template.id)
                }
            }

            HStack {
                Button("测试并预览") {
                    Task {
                        let template = selectedTestTemplate
                        if await store.testProvider(draft, template: template, apiKey: apiKey) { testedSignature = signature }
                    }
                }
                .disabled(store.isBusy || (needsKey && apiKey.isEmpty && draft.credentialID.isEmpty))
                Spacer()
                Button("保存并启用") { Task { await store.saveProvider(draft, apiKey: apiKey) } }
                    .buttonStyle(.borderedProminent)
                    .disabled(store.isBusy || testedSignature != signature)
            }
            Text("为避免误配置，只有当前草稿测试成功后才可保存。手动测试不计入每日 AI 调用上限。")
                .font(.caption).foregroundStyle(.secondary)
        }
        .padding(8)
        .onAppear { loadDraft(); ensureTestTemplate() }
        .onChange(of: store.config.templates) { _, _ in ensureTestTemplate() }
    }

    private var selectedTestTemplate: ReminderTemplate {
        store.config.templates.first(where: { $0.id == testTemplateID }) ?? store.config.templates[0]
    }

    private func loadDraft() {
        draft = store.config.provider
        preset = ProviderPreset.from(draft)
        testedSignature = ""
    }

    private func ensureTestTemplate() {
        guard !store.config.templates.contains(where: { $0.id == testTemplateID }) else { return }
        testTemplateID = store.config.templates.first(where: { $0.enabled })?.id ?? store.config.templates[0].id
    }

    private func configure(_ value: ProviderPreset) {
        switch value {
        case .openclaw:
            draft = .openClaw
        case .codex:
            draft = ProviderConfig(kind: "codex", preset: "codex", baseURL: "", model: "", credentialID: "", timeoutSeconds: 45, codexPath: draft.codexPath, text: nil)
        case .gemini:
            draft = ProviderConfig(kind: "openai_compatible", preset: "gemini", baseURL: "https://generativelanguage.googleapis.com/v1beta/openai", model: "gemini-2.5-flash", credentialID: "draft", timeoutSeconds: 25, codexPath: "", text: nil)
        case .nvidia:
            draft = ProviderConfig(kind: "openai_compatible", preset: "nvidia", baseURL: "https://integrate.api.nvidia.com/v1", model: "meta/llama-3.1-8b-instruct", credentialID: "draft", timeoutSeconds: 25, codexPath: "", text: nil)
        case .custom:
            draft = ProviderConfig(kind: "openai_compatible", preset: "custom", baseURL: "https://", model: "", credentialID: "draft", timeoutSeconds: 25, codexPath: "", text: nil)
        }
    }
}

struct DiagnosticsView: View {
    @ObservedObject var store: ConfigStore
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Button("运行诊断") { store.runDoctor() }.buttonStyle(.borderedProminent)
                Button("测试提示音") { store.runTest("chime") }
                Button("测试语音") { store.runTest("voice") }
                Button("测试音乐") { store.runTest("music") }
                Spacer()
                if store.isBusy { ProgressView().controlSize(.small) }
            }
            ScrollView {
                Text(store.diagnostics)
                    .font(.system(.caption, design: .monospaced))
                    .textSelection(.enabled)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding()
            }
            .background(Color.secondary.opacity(0.08), in: RoundedRectangle(cornerRadius: 10))
        }
        .padding(8)
    }
}
