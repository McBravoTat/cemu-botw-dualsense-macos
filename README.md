# Cemu BOTW DualSense Triggers for macOS

**Experimental adaptive R2 triggers for Wii U Breath of the Wild in Cemu over Bluetooth.**

[Русская инструкция](README.ru.md) · [Compatibility](COMPATIBILITY.md) · [Telemetry](TELEMETRY.md)

The bridge reads game state. It prepares the bow profile while Link has the bow in hand,
releases it on a shot, and prepares it again between shots. Sword mode, inventory and map
suppress the effect in the tested build. Cemu keeps receiving the controller's input.
The first unsheathing still cannot be anticipated; this is a prototype, not universal support.

## Requirements

* Apple Silicon Mac, native arm64 Python 3.10+, standard DualSense paired over Bluetooth.
* Homebrew hidapi 0.12+ and Apple's Command Line Tools.
* Your own Cemu and Wii U BOTW installation. The **verified baseline is EU v208 and one
  arm64 Cemu 3005cb7 executable**; see [exact hashes and test limits](COMPATIBILITY.md).

No Cemu/game/controller-driver binaries are included. Python uses its standard library;
there is no pip dependency to install. The local C reader is built from source on your Mac.

## Install and run

Download this repository with **Code -> Download ZIP**, unzip it, or clone it:

```bash
git clone https://github.com/McBravoTat/cemu-botw-dualsense-macos.git
cd cemu-botw-dualsense-macos
brew install python hidapi
chmod +x "Start BOTW Triggers.command"
```

If Command Line Tools are missing, install them with `xcode-select --install`.
Then check the installation without launching a game or touching the controller:

```bash
python3 doctor.py
```

Close an existing Cemu instance. Double-click **Start BOTW Triggers.command**, or run:

```bash
python3 launch_botw.py
```

Continue your game, then take out the bow. The launcher uses your **normal Cemu data and saves**
by default. To use a separate test copy, pass `--mlc /path/to/copied/mlc01`.
The bridge does not edit saves or Cemu settings; normal game play can of course save progress.

If Cemu is elsewhere:

```bash
python3 launch_botw.py --cemu /path/to/Cemu.app
```

An unrecognized executable is refused by default. A developer can explicitly try an
unverified build with `--experimental-cemu --dry-run`; runtime game validation remains on.
See COMPATIBILITY.md before treating such a build as usable.

## Controls and shutdown

* No remapping: assign Cemu ZR to physical R2 as usual.
* A sleeping controller needs its PS button pressed. The bridge waits and retries connection.
* Close Cemu or stop the launcher with Ctrl+C to request R2 off. Stopping the bridge can leave Cemu open.
* To explicitly clear R2 after stopping the bridge: `python3 bridge.py off`.
* Run one bridge. Do not run dualsensectl or a competing effect writer at the same time.

The prepared profile remains enabled while the bow is in hand, even with R2 released.
That is intentional. Off delivery cannot be guaranteed after disconnect, SIGKILL or power loss.

## Options and diagnostics

```bash
python3 launch_botw.py --check
python3 launch_botw.py --dry-run
python3 launch_botw.py --serial YOUR_CONTROLLER_SERIAL --hidapi /path/to/libhidapi.dylib
python3 bridge.py list
python3 bridge.py monitor --seconds 30
python3 bridge.py follow --seconds 30
python3 bridge.py armed --seconds 30
python3 bridge.py replay --trace tests/r2_trace.jsonl
```

`follow` is the original R2-edge experiment and can engage too late during a fast press.
`armed` prepares the effect independently of the game; it is a hardware comparison, not telemetry.
`list` reveals device identifiers locally; do not paste them into public issues.
Logs stay in ignored `logs/`; locally built files stay in ignored `.runtime/`.
A successful HID write is a transport observation, not a physical motor acknowledgement.

## Validation and limitations

The earlier live baseline confirmed Bluetooth output, game-state transitions, and off for
Sword/inventory/map. The physical pre-armed effect was user-confirmed. Public-source changes
are software-tested separately; see COMPATIBILITY.md for the evidence boundary.
All runes/bows, no-arrow scenarios, every cutscene/loading state, background focus and long
sessions are not fully tested. No claims are made for other games, Switch, USB or DualSense Edge.

```bash
python3 -m unittest discover -s tests -v
RUN_EXPORTER_TESTS=1 python3 -m unittest discover -s tests -p test_exporter_macos.py -v
```

The optional native test uses a synthetic process, not Cemu, a game or a controller.
GitHub Actions runs software checks; CI does not verify physical trigger feel.

GPL-3.0-or-later. See [LICENSE](LICENSE), [notices and upstream credits](NOTICE.md),
[contribution notes](CONTRIBUTING.md) and [changelog](CHANGELOG.md).
