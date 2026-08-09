import Foundation

@main
enum DNDModelChecks {
    static func main() {
        let dnd = DNDConfig(enabled: true, startMinute: 1320, endMinute: 480, stepMinutes: 15)
        precondition(dnd.durationMinutes == 600, "22:00–08:00 should span ten hours")
        precondition(DNDConfig.snapped(1327) == 1320, "drag should snap to the nearest 15 minutes")
        precondition(DNDConfig.snapped(1439) == 0, "snapping should wrap midnight")

        let shortest = dnd.moving(.end, to: 1320, snap: true)
        precondition(shortest.durationMinutes == 15, "handles must not collapse")

        let movedStart = dnd.moving(.start, to: 465, snap: true)
        precondition((15...1425).contains(movedStart.durationMinutes), "duration must stay in range")

        var disabled = dnd
        disabled.enabled = false
        precondition(disabled.startMinute == 1320 && disabled.endMinute == 480, "disabling should preserve values")

        print("DND model checks passed")
    }
}
