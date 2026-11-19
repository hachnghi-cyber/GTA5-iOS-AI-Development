import Foundation

/// Fixed-width, little-endian guest mailbox; NOT an RAGE multiplayer protocol.
/// RPR1: 16-byte header + 31 remote peers * 24 bytes + checksum = 764 bytes.
public struct RPRemotePoseV10: Equatable {
    public let id: UInt64
    public let x: Float
    public let y: Float
    public let z: Float
    public let heading: Float

    public init?(id: String, xyz: [Double], heading: Double) {
        guard id.count == 12,
              id.utf8.allSatisfy({ (48...57).contains($0) || (97...102).contains($0) }),
              let peerID = UInt64(id, radix: 16), peerID > 0,
              xyz.count == 3, (xyz + [heading]).allSatisfy(\.isFinite),
              abs(xyz[0]) <= 100_000, abs(xyz[1]) <= 100_000, abs(xyz[2]) <= 20_000,
              abs(heading) <= 360_000 else { return nil }
        self.id = peerID
        x = Float(xyz[0]); y = Float(xyz[1]); z = Float(xyz[2]); self.heading = Float(heading)
    }
}

public enum RPRemoteMailboxCodecV10 {
    public static let maxPeers = 31
    public static let size = 16 + maxPeers * 24 + 4

    private static func write32(_ b: inout [UInt8], _ i: Int, _ value: UInt32) {
        for j in 0..<4 { b[i + j] = UInt8(truncatingIfNeeded: value >> (8 * j)) }
    }
    private static func write64(_ b: inout [UInt8], _ i: Int, _ value: UInt64) {
        for j in 0..<8 { b[i + j] = UInt8(truncatingIfNeeded: value >> (8 * j)) }
    }
    public static func checksum(_ b: [UInt8]) -> UInt32 {
        var h: UInt32 = 2_166_136_261
        for v in b.dropLast(4) { h = (h ^ UInt32(v)) &* 16_777_619 }
        return h
    }
    public static func encode(peers: [RPRemotePoseV10], frame: UInt32,
                              epoch: UInt32 = 0x20261118) -> Data {
        var b = [UInt8](repeating: 0, count: size)
        b[0...3] = [82, 80, 82, 49][...]; b[4] = 1
        let unique = Dictionary(peers.map { ($0.id, $0) }, uniquingKeysWith: { _, latest in latest })
        let selected = unique.values.sorted { $0.id < $1.id }.prefix(maxPeers)
        b[5] = UInt8(selected.count)
        write32(&b, 8, frame)
        precondition(epoch != 0, "mailbox epoch must be nonzero")
        write32(&b, 12, epoch)
        for (index, peer) in selected.enumerated() {
            let i = 16 + index * 24
            write64(&b, i, peer.id)
            write32(&b, i + 8, peer.x.bitPattern)
            write32(&b, i + 12, peer.y.bitPattern)
            write32(&b, i + 16, peer.z.bitPattern)
            write32(&b, i + 20, peer.heading.bitPattern)
        }
        write32(&b, size - 4, checksum(b))
        return Data(b)
    }
}

/// Only accepts remote packets after the server's welcome, not merely TCP.ready.
public final class RPRemoteRosterV10 {
    public private(set) var connected = false
    public private(set) var localID: String?
    public private(set) var peers: [String: RPRemotePoseV10] = [:]

    public init() {}
    public func disconnect() { connected = false; localID = nil; peers.removeAll() }
    public func establish() { connected = true; localID = nil; peers.removeAll() }

    @discardableResult public func receive(_ packet: [String: Any]) -> Bool {
        guard connected, let type = packet["type"] as? String else { return false }
        if type != "welcome" && localID == nil { return false }
        switch type {
        case "welcome":
            guard let id = packet["id"] as? String,
                  id.count == 12,
                  id.utf8.allSatisfy({ (48...57).contains($0) || (97...102).contains($0) })
            else { return false }
            localID = id
            peers.removeAll()
            for info in packet["players"] as? [[String: Any]] ?? [] { _ = add(info) }
            return true
        case "joined":
            if let info = packet["player"] as? [String: Any] { return add(info) }
        case "pose":
            guard let id = packet["id"] as? String, id != localID,
                  let xyz = packet["pose"] as? [Double],
                  let heading = packet["heading"] as? Double,
                  let pose = RPRemotePoseV10(id: id, xyz: xyz, heading: heading)
            else { return false }
            peers[id] = pose
            return true
        case "left":
            guard let id = packet["id"] as? String else { return false }
            return peers.removeValue(forKey: id) != nil
        default: break
        }
        return false
    }
    private func add(_ info: [String: Any]) -> Bool {
        guard let id = info["id"] as? String, id != localID,
              let xyz = info["pose"] as? [Double],
              let heading = info["heading"] as? Double,
              let pose = RPRemotePoseV10(id: id, xyz: xyz, heading: heading)
        else { return false }
        peers[id] = pose
        return true
    }
    public func frame(_ sequence: UInt32, epoch: UInt32 = 0x20261118) -> Data {
        RPRemoteMailboxCodecV10.encode(peers: Array(peers.values), frame: sequence, epoch: epoch)
    }
}

/// Background file writer, capped at four writes/s; does not touch the game thread.
public final class RPRemoteMailboxWriterV10 {
    public var onDiagnostic: ((String) -> Void)?
    private let destination: URL
    private let queue = DispatchQueue(label: "rp.v10.remote.file", qos: .utility)
    private var timer: DispatchSourceTimer?
    private let roster = RPRemoteRosterV10()
    private var dirty = true
    private var generation: UInt32 = 0
    private let epoch = UInt32.random(in: 1...UInt32.max)

    public init(poseFileURL: URL) {
        precondition(poseFileURL.isFileURL)
        destination = poseFileURL.deletingLastPathComponent().appendingPathComponent("RPV10_remote.bin")
    }
    public func start() {
        queue.async { [weak self] in
            guard let self = self, self.timer == nil else { return }
            let timer = DispatchSource.makeTimerSource(queue: self.queue)
            timer.schedule(deadline: .now(), repeating: .milliseconds(250))
            timer.setEventHandler { [weak self] in self?.flush() }
            self.timer = timer
            timer.resume()
        }
    }
    public func stop() {
        queue.async { [weak self] in
            guard let self = self else { return }
            self.roster.disconnect(); self.dirty = true; self.flush()
            self.timer?.cancel(); self.timer = nil
        }
    }
    public func setSessionReady(_ ready: Bool) {
        queue.async { [weak self] in
            guard let self = self else { return }
            if ready { self.roster.establish() } else { self.roster.disconnect() }
            self.dirty = true
        }
    }
    public func receive(_ packet: [String: Any]) {
        queue.async { [weak self] in
            guard let self = self else { return }
            self.dirty = self.roster.receive(packet) || self.dirty
        }
    }
    private func flush() {
        guard dirty else { return }
        generation = generation == UInt32.max ? 1 : generation + 1
        do {
            try roster.frame(generation, epoch: epoch).write(to: destination, options: .atomic)
            dirty = false
        } catch { onDiagnostic?("remote_mailbox_write_failed: \(error)") }
    }
}
