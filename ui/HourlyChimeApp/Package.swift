// swift-tools-version: 6.2
import PackageDescription

let package = Package(
    name: "HourlyChimeApp",
    platforms: [.macOS(.v14)],
    products: [
        .executable(name: "HourlyChimeApp", targets: ["HourlyChimeApp"]),
        .executable(name: "HourlyChimeKeychainHelper", targets: ["HourlyChimeKeychainHelper"])
    ],
    targets: [
        .executableTarget(name: "HourlyChimeApp"),
        .executableTarget(name: "HourlyChimeKeychainHelper")
    ]
)
