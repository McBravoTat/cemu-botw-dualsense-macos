# SPDX-License-Identifier: GPL-3.0-or-later
"""Experimental, version-locked Wii U BOTW v208 reader. No writes to game memory."""
import struct

TITLE = '00050000101c9500'
PLAYER_INFO = 0x10463F38
POUCH_MANAGER = 0x10469978
PLAYER_VTABLE = 0x101E5FFC


def pointer(value):
    return 0x10000000 <= value < 0x50000000 and value % 4 == 0


class BotwState:
    def __init__(self, memory):
        self.memory = memory
        self.checked = False

    def sample(self):
        m = self.memory
        info = m.info()
        if info.get('running') is not True or info.get('title_id') != TITLE:
            self.checked = False
            return dict(valid=False, reason='game-not-running-or-other-title', effect=False)
        if not self.checked:
            # Version fingerprint from live Wii U code, not Switch structure offsets.
            if m.read(0x02D799B0, 8) != bytes.fromhex('386307cc4e800020'):
                return dict(valid=False, reason='unsupported-game-code', effect=False)
            if m.read(0x02D8D0E4, 8) != bytes.fromhex('386000024e800020'):
                return dict(valid=False, reason='unsupported-bow-slot-code', effect=False)
            self.checked = True
        tracker = m.u32(PLAYER_INFO)
        if not pointer(tracker):
            return dict(valid=False, reason='player-unavailable', effect=False)
        actor = m.u32(tracker + 0x30)
        if not pointer(actor) or m.u32(actor + 0xE8) != PLAYER_VTABLE:
            return dict(valid=False, reason='player-validation-failed', effect=False)
        life = m.u32(actor + 0x540)
        max_life = m.u32(actor + 0x1320)
        if not 1 <= max_life <= 1000 or life > max_life:
            return dict(valid=False, reason='health-validation-failed', effect=False)
        manager = m.u32(POUCH_MANAGER)
        if not pointer(manager):
            return dict(valid=False, reason='pouch-unavailable', effect=False)
        equipped = struct.unpack('>4I', m.read(manager + 0x3812C, 16))
        if any(p and not pointer(p) for p in equipped):
            return dict(valid=False, reason='menu-validation-failed', effect=False)
        menu = any(equipped)
        bow_state = m.u32(actor + 0x19B4)
        mode = m.read(actor + 0x928, 16).split(b'\0', 1)[0].decode('ascii', errors='replace')
        flags = m.u32(actor + 0x83C)
        if bow_state not in (0, 1, 2, 3):
            return dict(valid=False, reason='unknown-bow-state', effect=False)
        # Wii U equipment getter: player+0x7cc, slot 2, stride 0x10.
        handle = m.read(actor + 0x7EC, 12)
        unit, proc_id = struct.unpack('>II', handle[:8])
        bow_name = ''
        if pointer(unit) and proc_id != 0xFFFFFFFF and m.u32(unit + 0x3C) == proc_id:
            bow_actor = m.u32(unit + 0x40)
            if pointer(bow_actor):
                name_ptr = m.u32(bow_actor + 4)
                if pointer(name_ptr):
                    bow_name = m.read(name_ptr, 64).split(b'\0', 1)[0].decode('ascii', errors='replace')
        has_bow = bow_name.startswith('Weapon_Bow_')
        # Pre-arm while Link has the bow in hand, including between shots.
        # The first draw from a sheathed weapon still cannot anticipate physical input.
        effect = bool(life and not menu and has_bow and mode == 'Bow' and
                      (bow_state in (1, 2) or flags & 0x40000000) and bow_state != 3)
        return dict(valid=True, actor=f'0x{actor:08x}', life=life, max_life=max_life,
                    bow=bow_name, mode=mode, flags=f'0x{flags:08x}',
                    bow_state=bow_state, menu=menu, effect=effect)
