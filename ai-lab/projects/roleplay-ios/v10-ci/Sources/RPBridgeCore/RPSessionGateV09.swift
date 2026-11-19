import Foundation

/// Testable handshake state machine. NWConnection.ready is NOT a server login.
public final class RPSessionGateV09 {
    public enum Phase: Equatable { case idle, awaitingWelcome, established }
    public private(set) var phase: Phase = .idle
    public private(set) var localID: String?

    public init() {}

    public func reset() {
        phase = .idle
        localID = nil
    }

    public func transportReady() {
        reset()
        phase = .awaitingWelcome
    }

    public func admitServerPacket(_ packet: [String: Any]) -> Bool {
        guard let type = packet["type"] as? String else { return false }
        switch phase {
        case .idle:
            return false
        case .awaitingWelcome:
            guard type == "welcome",
                  let version = packet["protocol"] as? Int, version == 1,
                  let id = packet["id"] as? String,
                  !id.isEmpty, id.count <= 64,
                  let room = packet["room"] as? String,
                  !room.isEmpty, room.count <= 24 else { return false }
            localID = id
            phase = .established
            return true
        case .established:
            return type != "welcome"
        }
    }

    public var maySendGameplay: Bool { phase == .established }
}
