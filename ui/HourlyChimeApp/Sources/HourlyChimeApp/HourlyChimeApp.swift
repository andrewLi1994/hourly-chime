import AppKit
import SwiftUI

@main
struct HourlyChimeApp: App {
    @StateObject private var store = ConfigStore()

    var body: some Scene {
        MenuBarExtra {
            MenuBarContent(store: store)
        } label: {
            Image(systemName: store.status?.enabled == true ? "bell.and.waves.left.and.right.fill" : "bell.slash.fill")
                .accessibilityLabel(store.status?.enabled == true ? "Hourly Chime 正在运行" : "Hourly Chime 已暂停")
        }

        Window("Hourly Chime", id: "settings") {
            ContentView(store: store)
        }
        .defaultSize(width: 780, height: 740)
        .windowResizability(.contentMinSize)
    }
}

private struct MenuBarContent: View {
    @ObservedObject var store: ConfigStore
    @Environment(\.openWindow) private var openWindow

    var body: some View {
        Group {
            if let status = store.status {
                Label(status.enabled ? "播报运行中" : "播报已暂停", systemImage: status.enabled ? "checkmark.circle.fill" : "pause.circle")
                Text("Provider：\(status.provider)")
                Text("下次播报：\(status.nextPlayAt)")
            } else {
                Text("正在读取状态…")
            }
        }
        .disabled(true)
        Divider()
        Button(store.status?.enabled == true ? "暂停播报" : "启用播报") { store.setEnabled(store.status?.enabled != true) }
        Menu("立即测试") {
            Button("完整播报") { store.runTest("full") }
            Button("整点提示音") { store.runTest("chime") }
            Button("缓存语音") { store.runTest("voice") }
            Button("日语音乐") { store.runTest("music") }
        }
        Button("刷新语音缓存") { store.refreshCache() }
        Divider()
        Button("设置…") {
            openWindow(id: "settings")
            NSApp.activate(ignoringOtherApps: true)
        }
        Button("打开日志文件夹") {
            let url = FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/Application Support/HourlyChime/logs")
            NSWorkspace.shared.open(url)
        }
        Divider()
        Button("退出 Hourly Chime") { NSApp.terminate(nil) }
        .onAppear { store.refreshStatus() }
    }
}
