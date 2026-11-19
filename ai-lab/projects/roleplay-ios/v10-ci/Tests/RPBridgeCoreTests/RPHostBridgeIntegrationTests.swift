import Foundation
import XCTest
@testable import RPBridgeCore

final class RPHostBridgeIntegrationTests: XCTestCase {
    private func pose(seq: UInt32) -> Data {
        var b = [UInt8](repeating: 0, count: RPFilePoseCodec.size)
        b.replaceSubrange(0..<4, with: [82, 80, 70, 56])
        b[4] = 8; b[6] = 48
        func put(_ p: Int, _ n: UInt32) {
            for i in 0..<4 { b[p+i] = UInt8(truncatingIfNeeded: n >> (8*i)) }
        }
        put(8, seq); put(12, 2); put(16, 15)
        put(20, Float(11).bitPattern); put(24, Float(22).bitPattern)
        put(28, Float(33).bitPattern); put(32, Float(45).bitPattern)
        put(40, 0x08112026)
        var h: UInt32 = 2_166_136_261
        for byte in b.prefix(44) { h = (h ^ UInt32(byte)) &* 16_777_619 }
        put(44, h)
        return Data(b)
    }

    func testNoRemoteDataBeforeWelcome() {
        let roster = RPRemoteRosterV10()
        roster.establish()
        let pkt: [String: Any] = [
            "type": "pose", "id": "000000000002",
            "pose": [1.0, 2.0, 3.0], "heading": 90.0
        ]
        XCTAssertFalse(roster.receive(pkt))
        XCTAssertTrue(roster.peers.isEmpty)
        XCTAssertTrue(roster.receive(["type": "welcome",
                                       "id": "000000000001", "players": []]))
        XCTAssertTrue(roster.receive(pkt))
        XCTAssertEqual(roster.peers.count, 1)
        roster.disconnect()
        XCTAssertTrue(roster.peers.isEmpty)
        XCTAssertFalse(roster.receive(pkt))
    }

    func testMailboxSizeChecksumDedupAndLimit() {
        let a = RPRemotePoseV10(id: "000000000002", xyz: [1, 2, 3], heading: 90)!
        let peers = Array(repeating: a, count: 40)
        let frame = RPRemoteMailboxCodecV10.encode(peers: peers, frame: 3, epoch: 7)
        XCTAssertEqual(frame.count, 764)
        XCTAssertEqual(Array(frame.prefix(4)), [82, 80, 82, 49])
        XCTAssertEqual(frame[5], 1)
        let end = frame.count - 4
        let expected = RPRemoteMailboxCodecV10.checksum(Array(frame))
        let actual = UInt32(frame[end]) | UInt32(frame[end + 1]) << 8
                   | UInt32(frame[end + 2]) << 16 | UInt32(frame[end + 3]) << 24
        XCTAssertEqual(actual, expected)
        let unique = (1...40).compactMap {
            RPRemotePoseV10(id: String(format: "%012x", $0), xyz: [1, 2, 3], heading: 90)
        }
        let bounded = RPRemoteMailboxCodecV10.encode(peers: unique, frame: 4, epoch: 7)
        XCTAssertEqual(bounded[5], 31)
    }

    func testDiscoveryAndLiveProofRequireSequenceChange() throws {
        let temp = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString, isDirectory: true)
        let nested = temp.appendingPathComponent("sub", isDirectory: true)
        try FileManager.default.createDirectory(at: nested,
                                                withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: temp) }
        let file = nested.appendingPathComponent("RPV08_pose.bin")
        try pose(seq: 100).write(to: file)
        let initial = RPFileDiscoveryV10.inspect(roots: [temp])
        XCTAssertEqual(initial.filter(\.valid).count, 1)
        let first = RPLivePoseProofV10.read(at: file)
        XCTAssertEqual(RPLivePoseProofV10.compare(first: first, second: first),
                       .staticSequence)
        try pose(seq: 102).write(to: file)
        let second = RPLivePoseProofV10.read(at: file)
        XCTAssertEqual(RPLivePoseProofV10.compare(first: first, second: second),
                       .verified(100, 102))
        let symlink = temp.appendingPathComponent("RPV08_pose.bin")
        try FileManager.default.createSymbolicLink(at: symlink, withDestinationURL: file)
        XCTAssertEqual(RPFileDiscoveryV10.inspect(roots: [temp]).filter(\.valid).count, 1)
        try Data([1, 2]).write(to: file)
        XCTAssertFalse(RPFileDiscoveryV10.inspect(roots: [temp]).contains(where: { $0.valid }))
    }
}
