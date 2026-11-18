import Foundation

/// Diagnostic file-based guest/host transport proof, not a public GTA5Port API.
public enum RPFilePoseError: Error, Equatable {
    case length, magic, version, mode, checksum, invalidPose, torn, stale
}

public struct RPFilePose: Equatable {
    public let sequence: UInt32
    public let ped: UInt32
    public let x: Double
    public let y: Double
    public let z: Double
    public let heading: Double
}

public enum RPFilePoseCodec {
    public static let size = 48

    private static func u32(_ b: [UInt8], _ p: Int) -> UInt32 {
        UInt32(b[p]) | UInt32(b[p+1]) << 8 | UInt32(b[p+2]) << 16 | UInt32(b[p+3]) << 24
    }

    private static func digest(_ b: [UInt8]) -> UInt32 {
        var v: UInt32 = 2_166_136_261
        for byte in b.prefix(44) {
            v = (v ^ UInt32(byte)) &* 16_777_619
        }
        return v
    }

    public static func decode(_ bytes: Data) throws -> RPFilePose {
        guard bytes.count == size else { throw RPFilePoseError.length }
        let b = Array(bytes)
        guard b[0...3].elementsEqual([82, 80, 70, 56]) else { throw RPFilePoseError.magic }
        guard b[4] == 8, b[5] == 0, b[6] == size, b[7] == 0 else { throw RPFilePoseError.version }
        guard u32(b, 12) == 2, u32(b, 40) == 0x08112026 else { throw RPFilePoseError.mode }
        guard u32(b, 44) == digest(b) else { throw RPFilePoseError.checksum }
        let seq = u32(b, 8), ped = u32(b, 16)
        let x = Double(Float(bitPattern: u32(b, 20)))
        let y = Double(Float(bitPattern: u32(b, 24)))
        let z = Double(Float(bitPattern: u32(b, 28)))
        let h = Double(Float(bitPattern: u32(b, 32)))
        guard seq > 0, ped > 0, ped != UInt32.max,
              [x, y, z, h].allSatisfy({ $0.isFinite }),
              abs(x) <= 100_000, abs(y) <= 100_000,
              abs(z) <= 20_000, abs(h) <= 360_000
        else { throw RPFilePoseError.invalidPose }
        var heading = h.truncatingRemainder(dividingBy: 360)
        if heading < 0 { heading += 360 }
        return RPFilePose(sequence: seq, ped: ped, x: x, y: y, z: z, heading: heading)
    }
}

public final class RPFilePoseConsumer {
    private let fileURL: URL
    private let maxAge: TimeInterval
    private var lastSeq: UInt32 = 0
    private var online = false

    public init(fileURL: URL, maxAge: TimeInterval = 1.5) {
        self.fileURL = fileURL
        self.maxAge = maxAge
    }

    public func setSessionReady(_ ready: Bool) {
        if !ready { lastSeq = 0 }
        online = ready
    }

    public func poll(now: Date = Date()) throws -> RPFilePose? {
        guard online else { return nil }
        let info = try FileManager.default.attributesOfItem(atPath: fileURL.path)
        guard let timestamp = info[.modificationDate] as? Date,
              abs(now.timeIntervalSince(timestamp)) <= maxAge else {
            throw RPFilePoseError.stale
        }
        let first = try Data(contentsOf: fileURL)
        let second = try Data(contentsOf: fileURL)
        guard first == second else { throw RPFilePoseError.torn }
        let pose = try RPFilePoseCodec.decode(first)
        guard pose.sequence > lastSeq else { return nil }
        lastSeq = pose.sequence
        return pose
    }
}
