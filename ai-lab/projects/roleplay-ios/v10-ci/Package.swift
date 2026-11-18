// swift-tools-version: 5.9
import PackageDescription

let package = Package(
  name: "GTA5PortRPHandshakeAndPose",
  platforms: [.iOS(.v16)],
  products: [.library(name: "RPBridgeCore", targets: ["RPBridgeCore"])],
  targets: [
    .target(name: "RPBridgeCore"),
    .testTarget(name: "RPBridgeCoreTests", dependencies: ["RPBridgeCore"])
  ]
)
