# Read-only Wii U telemetry

The launcher loads `tools/cemu_memory_export.c` into its Cemu child using
DYLD_INSERT_LIBRARIES; it does not patch the installed executable or write game memory.
The module resolves `memory_base`, `CafeSystem::sSystemRunning` and `sForegroundTitleId`.
It reads its own process through mach_vm_read_overwrite and serves one client at a time
on `/private/tmp/cemu-botw-PID.sock` (0600). No TCP listener or memory-write command exists.

The client validates title/code/pointers before selecting an effect. Values are Wii U
guest big-endian, with 32-bit guest pointers; host pointers must not be substituted.

| Guest field | Observed meaning |
|---|---|
| [0x10463f38] + 0x30 | PlayerInfo -> player |
| player + 0xe8 | player vtable, expected 0x101e5ffc |
| player + 0x540 / +0x1320 | current / maximum life |
| player + 0x7cc + 2*0x10 | bow equipment handle |
| unit + 0x3c / +0x40 | proc-id validation / actor pointer |
| equipment actor + 4 | pointer to name, expected Weapon_Bow_* |
| player + 0x928 | observed None/Bow/Sword mode marker |
| player + 0x83c | flags, including 0x40000000 between shots |
| player + 0x19b4 | observed bow sequence 0 -> 1 -> 2 -> 3 -> 0 |
| [0x10469978] + 0x3812c | equipment snapshot, nonzero in tested inventory/map cases |

In the tested game, 1/2 correlated with nocking/holding and 3 with the shot. These are
observed correlations, not a complete reconstruction of the Player class.
The Bow flag can remain set after switching to Sword, so mode validation is also required.
Mode 1/2 can have zero flags, so those states must not incorrectly disable the effect.

Instruction fingerprints: 0x02d799b0 = `addi r3,r3,0x7cc; blr`,
0x02d8d0e4 = `li r3,2; blr`. These do not replace the other validation steps.

A read can race with game object destruction. Transport loss or validation failure produces
an off attempt, never a fabricated game state. One permanent client is supported; do not
run memory_probe alongside the bridge. memory_probe.py is a separate experimental GDB
research tool, not used by the game launcher; its live Cemu compatibility is not claimed.

See COMPATIBILITY.md for the exact supported game/build and untested cases, and NOTICE.md
for the sources of the initial Wii U leads. Synthetic tests and a short validation summary
are published; personal raw captures are deliberately excluded.
