import Foundation

/// Bounded sandbox-local discovery for guest pose files.
/// No symlink traversal. Caller controls trusted roots. Never accesses external paths.
public enum RPFileDiscoveryV10 {
    public struct Finding {
        public let url: URL
        public let sequence: UInt32?
        public let valid: Bool
        public let error: String?
    }
    public struct Limits {
        public var depth = 4
        public var directories = 512
        public var entries = 20_000
        public init() {}
    }

    public static func appRoots() -> [URL] {
        let fm = FileManager.default
        let dirs: [FileManager.SearchPathDirectory] = [
            .documentDirectory, .cachesDirectory, .applicationSupportDirectory
        ]
        return [URL(fileURLWithPath: NSHomeDirectory(), isDirectory: true)] +
            dirs.flatMap { fm.urls(for: $0, in: .userDomainMask) }
    }

    public static func inspect(roots: [URL], limits: Limits = Limits()) -> [Finding] {
        let fm = FileManager.default
        var queue: [(URL, Int)] = roots.filter(\.isFileURL).map { ($0.standardizedFileURL, 0) }
        var visited = Set<String>()
        var findings: [Finding] = []
        var entries = 0, dirs = 0, cursor = 0

        while cursor < queue.count && dirs < limits.directories && entries < limits.entries {
            let (dir, depth) = queue[cursor]
            cursor += 1
            let actual = dir.resolvingSymlinksInPath()
            let props = try? dir.resourceValues(forKeys: [.isDirectoryKey, .isSymbolicLinkKey])
            guard props?.isDirectory == true, props?.isSymbolicLink != true else { continue }
            guard visited.insert(actual.path).inserted else { continue }
            dirs += 1

            let candidate = dir.appendingPathComponent("RPV08_pose.bin", isDirectory: false)
            if (try? candidate.resourceValues(forKeys: [.isSymbolicLinkKey]).isSymbolicLink) != true,
               let attrs = try? fm.attributesOfItem(atPath: candidate.path),
               let size = attrs[.size] as? NSNumber {
                if size.intValue != RPFilePoseCodec.size {
                    findings.append(Finding(url: candidate, sequence: nil,
                                            valid: false, error: "length_\(size.intValue)"))
                } else {
                    do {
                        let first = try Data(contentsOf: candidate)
                        let second = try Data(contentsOf: candidate)
                        guard first == second else { throw RPFilePoseError.torn }
                        let pose = try RPFilePoseCodec.decode(first)
                        findings.append(Finding(url: candidate, sequence: pose.sequence,
                                                valid: true, error: nil))
                    } catch {
                        findings.append(Finding(url: candidate, sequence: nil,
                                                valid: false, error: String(describing: error)))
                    }
                }
            }

            guard depth < limits.depth else { continue }
            guard let children = try? fm.contentsOfDirectory(at: dir,
                includingPropertiesForKeys: [.isDirectoryKey, .isSymbolicLinkKey],
                options: [.skipsHiddenFiles]) else { continue }

            for child in children {
                entries += 1
                if entries > limits.entries || queue.count > limits.directories * 8 { break }
                guard let values = try? child.resourceValues(
                        forKeys: [.isDirectoryKey, .isSymbolicLinkKey]),
                      values.isDirectory == true, values.isSymbolicLink != true
                else { continue }
                queue.append((child, depth + 1))
            }
        }
        return findings.sorted { a, b in
            if a.valid != b.valid { return a.valid }
            let da = (try? a.url.resourceValues(forKeys: [.contentModificationDateKey]).contentModificationDate) ?? .distantPast
            let db = (try? b.url.resourceValues(forKeys: [.contentModificationDateKey]).contentModificationDate) ?? .distantPast
            return da > db
        }
    }
}

/// A valid single frame is NOT proof of a live guest-host bridge.
public enum RPLivePoseProofV10 {
    public enum Result: Equatable {
        case missing, invalid, staticSequence, verified(UInt32, UInt32)
    }
    public static func compare(first: RPFilePose?, second: RPFilePose?) -> Result {
        guard let first = first, let second = second else { return .missing }
        guard first.ped != UInt32.max && second.ped != UInt32.max else { return .invalid }
        guard second.sequence > first.sequence else { return .staticSequence }
        return .verified(first.sequence, second.sequence)
    }
    public static func read(at file: URL) -> RPFilePose? {
        guard let a = try? Data(contentsOf: file),
              let b = try? Data(contentsOf: file), a == b else { return nil }
        return try? RPFilePoseCodec.decode(a)
    }
}
