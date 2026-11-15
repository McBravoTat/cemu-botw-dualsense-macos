# Compatibility and validation

## Verified baseline

| Component | Observed baseline |
|---|---|
| Hardware | Apple M4, standard DualSense 054c:0ce6, Bluetooth |
| Cemu | arm64 commit 3005cb7b46e3b9c45644d4105ae3a984f87336fb |
| Executable SHA-256 | 19d7ca1580b0715e3b464285ee723e4f6339f1e6fb4b8e58bf1ea8e9ce6e2e6d |
| BOTW | Wii U EU, title 00050000101c9500, v208 |
| Updated / base RPX hash | fb7911ad / dcac9927 |
| OS observed by Cemu during game-mode testing | macOS 27.2.1 (26B131) |

macOS 26.2 was initially user-reported. The later local Cemu log reported 27.2.1;
game-driven mode is not separately claimed as tested on 26.2. Intel Macs, Rosetta,
USB, DualSense Edge, other regions and Switch emulators are not validated.

The tested binary hash is public compatibility metadata, not an included binary.
The same source commit compiled differently can have a different hash. Obtain Cemu
from its [official project](https://github.com/cemu-project/Cemu); this project does
not provide Cemu or game downloads.

## Other Cemu builds

Default mode accepts only the known executable hash. To investigate another arm64 build:

```bash
python3 launch_botw.py --cemu /path/to/Cemu.app --experimental-cemu --dry-run
```

This is **unverified compatibility**, not a supported-build claim. It still requires the
Cemu exports used by the reader, the supported title ID, matching game instructions,
valid player/equipment pointers and recognized state values. Nothing disables those checks.
An unknown or hardened build may not load the module or export the required symbols.
Do not disable OS security protections to make it load; report the incompatibility.
`--dry-run` opens no HID device and sends no trigger output.

## What was observed live before publication

* Shared Bluetooth input reading and byte-for-byte output agreement with dualsensectl-macos 0.7.0.
* A user confirmed physical pre-armed bow resistance and working ZR in Cemu.
* Player, life, equipment identity and repeated 0/1/2/3/0 bow-state transitions were read from Wii U BOTW.
* Bow/Sword differences and inventory/map transitions were observed on screen and in memory.
* The game-driven test sent five bow reports and six off reports, including cleanup.
* Controlled game tests used temporary keyboard input and a separate save copy; the original SDL
  controller profile was then restored. The new game-driven physical feel was not independently reported.

The publication refactor adds setup checks, optional explicit unverified-build testing,
privacy cleanup, argument forwarding and native synthetic tests. These changes must not be
represented as a new live hardware/gameplay validation. GitHub Actions results, once run,
will likewise verify software checks, not physical controller behavior.

## Known limits

The first unsheathing cannot be anticipated. The profile is pre-armed while the bow is in hand
for subsequent presses. Runes, no-arrow cases, every bow type/cutscene/loading transition,
long sessions and emulator dialogs/background focus need more live testing.
Reads are not atomic; destruction of an object during sampling can stop the bridge with an off attempt.
An off report cannot be guaranteed after power loss, SIGKILL or a disconnected controller.
