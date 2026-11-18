import XCTest
import Foundation
@testable import RPBridgeCore

final class RPBridgeCoreTests: XCTestCase {
    func testHandshakeMustReceiveWelcome() {
        let gate = RPSessionGateV09()
        XCTAssertFalse(gate.maySendGameplay)
        XCTAssertFalse(gate.admitServerPacket(["type": "welcome", "protocol": 1, "id": "aa", "room": "VN"]))
        gate.transportReady()
        XCTAssertFalse(gate.admitServerPacket(["type": "pose", "id": "aa"]))
        XCTAssertFalse(gate.maySendGameplay)
        XCTAssertTrue(gate.admitServerPacket(["type": "welcome", "protocol": 1, "id": "abcd1234", "room": "VN"]))
        XCTAssertTrue(gate.maySendGameplay)
        XCTAssertFalse(gate.admitServerPacket(["type": "welcome", "protocol": 1, "id": "other", "room": "VN"]))
        gate.reset()
        XCTAssertFalse(gate.maySendGameplay)
    }

    private func bytes(seq: UInt32 = 1, ped: UInt32 = 4) -> Data {
        var b = [UInt8](repeating: 0, count: 48)
        b.replaceSubrange(0..<4, with: [82,80,70,56]); b[4] = 8; b[6] = 48
        func put(_ i: Int, _ u: UInt32) {
            for j in 0..<4 { b[i+j] = UInt8(truncatingIfNeeded: u >> (8 * j)) }
        }
        put(8, seq); put(12, 2); put(16, ped)
        put(20, Float(1.25).bitPattern); put(24, Float(-2.5).bitPattern)
        put(28, Float(3.75).bitPattern); put(32, Float(90).bitPattern)
        put(40, 0x08112026)
        var v: UInt32 = 2_166_136_261
        for byte in b.prefix(44) { v = (v ^ UInt32(byte)) &* 16_777_619 }
        put(44, v)
        return Data(b)
    }

    func testPoseDecode() throws {
        let pose = try RPFilePoseCodec.decode(bytes())
        XCTAssertEqual(pose.sequence, 1)
        XCTAssertEqual(pose.ped, 4)
        XCTAssertEqual(pose.x, 1.25)
        XCTAssertEqual(pose.y, -2.5)
        XCTAssertEqual(pose.z, 3.75)
        XCTAssertEqual(pose.heading, 90)
    }

    func testPoseRejectsCorruption() throws {
        var raw = bytes()
        raw[26] = 255
        XCTAssertThrowsError(try RPFilePoseCodec.decode(raw)) { err in
            XCTAssertEqual(err as? RPFilePoseError, .checksum)
        }
        XCTAssertThrowsError(try RPFilePoseCodec.decode(Data(repeating: 0, count: 47)))
    }

    func testPoseConsumerDoesNotPollWithoutWelcome() throws {
        let url = URL(fileURLWithPath: NSTemporaryDirectory()).appendingPathComponent(UUID().uuidString)
        try bytes().write(to: url)
        defer { try? FileManager.default.removeItem(at: url) }
        let consumer = RPFilePoseConsumer(fileURL: url)
        XCTAssertNil(try consumer.poll())
        consumer.setSessionReady(true)
        XCTAssertNotNil(try consumer.poll())
        XCTAssertNil(try consumer.poll())
        consumer.setSessionReady(false)
        XCTAssertNil(try consumer.poll())
    }
}
