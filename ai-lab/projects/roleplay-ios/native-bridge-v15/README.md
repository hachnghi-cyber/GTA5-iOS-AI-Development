# GTA5Port RP v1.5 — opt-in LAN pose uplink

## Scope
Diagnostics only: iPhone Story Mode -> ScriptHookV ASI -> RPF8 48-byte pose in Documents/Mods -> ARM64 host bridge -> private TCP RP server.
No native gameplay hooks, remote PEDs or multiplayer action replication.

## Real-device evidence inherited from v1.4
User iPhone log confirmed FILE_SOURCE bucket=mods_child and two independent POSE_LIVE sequence increments (57->59, 119->127).
This proves ASI-to-file-to-ARM64, NOT an uplink to the server.

## v1.5 architecture
- Source file src/RPBridgeNetworkV15.c.gz.b64 is a reproducible gzip+base64 representation; CI decodes it and verifies SHA256 45c90ea3b21aa81e84f2fb897ea3e04175301229377916c208d16995d99d1bd3 before building.
- Complete readable source, Python server and tests are also handed to the project owner as GTA5Port-Roleplay-v1.5-LAN-POSE-TRANSPORT-SOURCE.zip.
- No network unless Documents/RPBridgeNetwork_v15.conf exists and includes enabled=1.
- Only RFC1918 and loopback IPv4; one connect, max 180 seconds, <=4 pose updates/s, no auto-reconnect.
- Validate RPF8 version, CRC, sequence and numeric bounds before any network pose.
- Send hello to the private JSON-line protocol v1 server, await welcome, then send pose only on new sequence.
- Log statuses to Documents/RPBridgeNetwork_v15.log; no coordinates, room key or full sandbox paths logged.

## Source reconstruction
Run from the native-bridge-v15 folder:
    python3 -c "import base64,gzip,hashlib,pathlib; p=pathlib.Path('src/RPBridgeNetworkV15.c.gz.b64'); s=gzip.decompress(base64.b64decode(p.read_text().strip(),validate=True)); assert hashlib.sha256(s).hexdigest()=='45c90ea3b21aa81e84f2fb897ea3e04175301229377916c208d16995d99d1bd3'; pathlib.Path('src/RPBridgeNetworkV15.c').write_bytes(s)"

## CI
- GitHub Actions compiles and tests on Linux, then compiles an unsigned ARM64 MH_DYLIB with the iPhoneOS SDK on macOS.
- Workflow: .github/workflows/build-gta5port-rp-v15.yml.
- No IPAs, game assets, private credentials, or certificates are uploaded.

## Manual iPhone/LAN diagnostic test
1. Install the re-signed diagnostic IPA including the v1.5 dylib.
2. Enable the existing RPPoseToFile-v0.8-E.asi in Story Mode.
3. On your private laptop, start the Python server with the SAME room key and TCP 7789.
4. Create Documents/RPBridgeNetwork_v15.conf on the iPhone with lines:
   enabled=1
   host=192.168.1.10
   port=7789
   room=VNTEST
   name=iPhoneA
   room_key=REPLACE_WITH_PRIVATE_KEY
5. Play and move; look for LAN_CONNECTED, SERVER_WELCOME_OK, POSE_INITIAL_READ, POSE_SENT_TO_TCP in the client log and pose reception in the server log.
6. Set enabled=0 (or delete config) to disable all connection attempts.

SECURITY: plaintext TCP is LAN test only; DO NOT port-forward or use on public Wi-Fi. The actual iPhone-to-server route remains unverified until device and server logs are available.