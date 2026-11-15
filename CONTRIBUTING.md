# Contributing

Run `python3 -m unittest discover -s tests -v` before submitting a change.
On macOS, `RUN_EXPORTER_TESTS=1 python3 -m unittest discover -s tests -p test_exporter_macos.py -v`
also builds and exercises the reader against a synthetic host, without Cemu or a controller.

Keep game-memory validation strict. A hash match or a few plausible values alone do not
establish compatibility. For new game profiles, document the title ID, update version,
RPX hash, instruction fingerprints, pointer validation, positive cases and negative cases.
Never silently reuse Switch offsets as Wii U offsets.

A new Cemu hash can be proposed with `python3 doctor.py` output and a reproducible report.
Do not submit game executables, assets, saves, memory dumps, controller addresses, account
information or unredacted local logs. Synthetic fixtures are preferred.

Please separate:

* unit/native synthetic tests;
* live game-state and HID-transport observations;
* a person's report of the physical trigger feel.

Submit changes under GPL-3.0-or-later and preserve upstream notices. This is an experimental
community project; unsupported games/builds should refuse effects rather than guess.
