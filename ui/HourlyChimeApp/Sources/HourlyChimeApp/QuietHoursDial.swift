import SwiftUI

struct QuietHoursDial: View {
    @Binding var dnd: DNDConfig
    let onCommit: (DNDConfig, DNDConfig) -> Void

    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @Environment(\.accessibilityReduceTransparency) private var reduceTransparency
    @Environment(\.accessibilityDifferentiateWithoutColor) private var differentiateWithoutColor
    @State private var dragOriginPointer: Double?
    @State private var dragOriginMinute = 0
    @State private var dragSnapshot: DNDConfig?

    private let accent = LinearGradient(
        colors: [Color(red: 0.20, green: 0.48, blue: 1), Color(red: 0.52, green: 0.30, blue: 0.95), Color(red: 0.12, green: 0.76, blue: 0.86)],
        startPoint: .topLeading,
        endPoint: .bottomTrailing
    )

    var body: some View {
        VStack(spacing: 20) {
            GeometryReader { proxy in
                let side = min(proxy.size.width, proxy.size.height)
                let center = CGPoint(x: proxy.size.width / 2, y: proxy.size.height / 2)
                let radius = side * 0.36
                ZStack {
                    dialTrack
                        .frame(width: radius * 2, height: radius * 2)
                        .position(center)

                    tickLabels(center: center, radius: radius)

                    centerReadout
                        .frame(width: radius * 1.20)
                        .position(center)

                    handle(.start, center: center, radius: radius)
                    handle(.end, center: center, radius: radius)
                }
                .coordinateSpace(name: "quiet-dial")
            }
            .frame(minWidth: 350, minHeight: 350)

            HStack(spacing: 28) {
                timePicker(title: "开始静音", systemImage: "speaker.slash.fill", minute: dnd.startMinute) { value in
                    commitPicker(.start, minute: value)
                }
                timePicker(title: "恢复播报", systemImage: "speaker.wave.2.fill", minute: dnd.endMinute) { value in
                    commitPicker(.end, minute: value)
                }
            }
        }
        .opacity(dnd.enabled ? 1 : 0.46)
        .allowsHitTesting(dnd.enabled)
    }

    private var dialTrack: some View {
        ZStack {
            Circle()
                .stroke(Color.secondary.opacity(reduceTransparency ? 0.28 : 0.14), style: StrokeStyle(lineWidth: 24, lineCap: .round))
            Circle()
                .trim(from: 0, to: CGFloat(dnd.durationMinutes) / 1440)
                .stroke(accent, style: StrokeStyle(lineWidth: 24, lineCap: .round))
                .rotationEffect(.degrees(Double(dnd.startMinute) / 4 - 90))
            if differentiateWithoutColor {
                Circle()
                    .trim(from: 0, to: CGFloat(dnd.durationMinutes) / 1440)
                    .stroke(Color.primary.opacity(0.45), style: StrokeStyle(lineWidth: 2, lineCap: .round, dash: [4, 7]))
                    .rotationEffect(.degrees(Double(dnd.startMinute) / 4 - 90))
            }
        }
    }

    @ViewBuilder
    private func tickLabels(center: CGPoint, radius: CGFloat) -> some View {
        ForEach([(0, "00:00"), (360, "06:00"), (720, "12:00"), (1080, "18:00")], id: \.0) { minute, label in
            Text(label)
                .font(.caption.monospacedDigit())
                .foregroundStyle(.secondary)
                .position(point(for: minute, center: center, radius: radius + 36))
        }
    }

    private var centerReadout: some View {
        VStack(spacing: 7) {
            Text("静音 \(formattedTime(dnd.startMinute))–\(formattedTime(dnd.endMinute))")
                .font(.title3.weight(.semibold))
                .monospacedDigit()
            Text(durationText)
                .font(.subheadline)
                .foregroundStyle(.secondary)
            Text(nextStartText)
                .font(.caption)
                .foregroundStyle(.secondary)
        }
        .multilineTextAlignment(.center)
    }

    private var durationText: String {
        let hours = dnd.durationMinutes / 60
        let minutes = dnd.durationMinutes % 60
        if minutes == 0 { return "共 \(hours) 小时" }
        return "共 \(hours) 小时 \(minutes) 分钟"
    }

    private var nextStartText: String {
        let calendar = Calendar.current
        let now = Date()
        let current = calendar.component(.hour, from: now) * 60 + calendar.component(.minute, from: now)
        return "下次开始：\(dnd.startMinute > current ? "今天" : "明天") \(formattedTime(dnd.startMinute))"
    }

    private func handle(_ handle: DialHandle, center: CGPoint, radius: CGFloat) -> some View {
        let minute = handle == .start ? dnd.startMinute : dnd.endMinute
        return Image(systemName: handle == .start ? "speaker.slash.fill" : "speaker.wave.2.fill")
            .font(.system(size: 13, weight: .semibold))
            .foregroundStyle(.white)
            .frame(width: 38, height: 38)
            .background(.blue.gradient, in: Circle())
            .overlay(Circle().stroke(.white.opacity(0.85), lineWidth: 2))
            .shadow(color: .black.opacity(0.18), radius: 5, y: 2)
            .contentShape(Circle())
            .position(point(for: minute, center: center, radius: radius))
            .gesture(dragGesture(handle, center: center))
            .focusable()
            .onKeyPress { press in
                guard press.phase == .down else { return .ignored }
                let amount = press.modifiers.contains(.option) ? 60 : 15
                switch press.key {
                case .leftArrow, .downArrow:
                    adjust(handle, by: -amount)
                    return .handled
                case .rightArrow, .upArrow:
                    adjust(handle, by: amount)
                    return .handled
                default:
                    return .ignored
                }
            }
            .accessibilityLabel(handle == .start ? "开始静音" : "恢复播报")
            .accessibilityValue(formattedTime(minute))
            .accessibilityHint("方向键调整十五分钟，按住 Option 调整一小时")
            .accessibilityAdjustableAction { direction in
                adjust(handle, by: direction == .increment ? 15 : -15)
            }
    }

    private func dragGesture(_ handle: DialHandle, center: CGPoint) -> some Gesture {
        DragGesture(minimumDistance: 0, coordinateSpace: .named("quiet-dial"))
            .onChanged { value in
                let pointerMinute = minute(at: value.location, center: center)
                if dragOriginPointer == nil {
                    dragOriginPointer = pointerMinute
                    dragOriginMinute = handle == .start ? dnd.startMinute : dnd.endMinute
                    dragSnapshot = dnd
                }
                guard let origin = dragOriginPointer else { return }
                var delta = pointerMinute - origin
                if delta > 720 { delta -= 1440 }
                if delta < -720 { delta += 1440 }
                dnd = dnd.moving(handle, to: dragOriginMinute + Int(delta.rounded()), snap: false)
            }
            .onEnded { _ in
                let old = dragSnapshot ?? dnd
                let current = handle == .start ? dnd.startMinute : dnd.endMinute
                let snapped = dnd.moving(handle, to: current, snap: true)
                if reduceMotion {
                    dnd = snapped
                } else {
                    withAnimation(.interpolatingSpring(stiffness: 420, damping: 42)) { dnd = snapped }
                }
                dragOriginPointer = nil
                dragSnapshot = nil
                onCommit(old, snapped)
            }
    }

    private func minute(at point: CGPoint, center: CGPoint) -> Double {
        // Use angular delta from the initial pointer location rather than snapping
        // the pointer to the handle center. This keeps dragging 1:1 with no jump.
        let angle = atan2(point.y - center.y, point.x - center.x) + .pi / 2
        let normalized = angle < 0 ? angle + 2 * .pi : angle
        return normalized / (2 * .pi) * 1440
    }

    private func point(for minute: Int, center: CGPoint, radius: CGFloat) -> CGPoint {
        let angle = Double(minute) / 1440 * 2 * Double.pi - Double.pi / 2
        return CGPoint(x: center.x + cos(angle) * radius, y: center.y + sin(angle) * radius)
    }

    private func timePicker(title: String, systemImage: String, minute: Int, changed: @escaping (Int) -> Void) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Label(title, systemImage: systemImage)
                .font(.caption)
                .foregroundStyle(.secondary)
            DatePicker("", selection: Binding(
                get: { date(for: minute) },
                set: { date in
                    let components = Calendar.current.dateComponents([.hour, .minute], from: date)
                    changed((components.hour ?? 0) * 60 + (components.minute ?? 0))
                }
            ), displayedComponents: .hourAndMinute)
            .labelsHidden()
            .environment(\.locale, Locale(identifier: "zh_CN"))
        }
    }

    private func date(for minute: Int) -> Date {
        Calendar.current.date(bySettingHour: minute / 60, minute: minute % 60, second: 0, of: Date()) ?? Date()
    }

    private func commitPicker(_ handle: DialHandle, minute: Int) {
        let old = dnd
        let new = dnd.moving(handle, to: minute, snap: true)
        dnd = new
        onCommit(old, new)
    }

    private func adjust(_ handle: DialHandle, by amount: Int) {
        let old = dnd
        let current = handle == .start ? dnd.startMinute : dnd.endMinute
        let new = dnd.moving(handle, to: current + amount, snap: true)
        dnd = new
        onCommit(old, new)
    }
}
