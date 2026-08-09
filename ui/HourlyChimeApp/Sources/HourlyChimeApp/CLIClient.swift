import Foundation

struct CLIError: LocalizedError, Sendable {
    let message: String
    var errorDescription: String? { message }
}

struct CLIClient: Sendable {
    var executable: URL

    init(executable: URL? = nil) {
        if let executable {
            self.executable = executable
        } else if let override = ProcessInfo.processInfo.environment["HOURLY_CHIME_CHIMECTL"] {
            self.executable = URL(fileURLWithPath: override)
        } else {
            self.executable = FileManager.default.homeDirectoryForCurrentUser
                .appendingPathComponent("Library/Application Support/HourlyChime/venv/bin/chimectl")
        }
    }

    func run(_ arguments: [String], stdin: Data? = nil) throws -> Data {
        let process = Process()
        process.executableURL = executable
        process.arguments = arguments
        let output = Pipe()
        let errors = Pipe()
        process.standardOutput = output
        process.standardError = errors
        if let stdin {
            let input = Pipe()
            process.standardInput = input
            try process.run()
            input.fileHandleForWriting.write(stdin)
            try input.fileHandleForWriting.close()
        } else {
            try process.run()
        }
        process.waitUntilExit()
        let data = output.fileHandleForReading.readDataToEndOfFile()
        let errorData = errors.fileHandleForReading.readDataToEndOfFile()
        guard process.terminationStatus == 0 else {
            let fallback = String(data: data.isEmpty ? errorData : data, encoding: .utf8) ?? "chimectl 执行失败"
            throw CLIError(message: fallback.trimmingCharacters(in: .whitespacesAndNewlines))
        }
        return data
    }

    func decode<T: Decodable>(_ type: T.Type, arguments: [String], stdin: Data? = nil) throws -> T {
        try JSONDecoder().decode(type, from: run(arguments, stdin: stdin))
    }
}
