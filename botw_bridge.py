#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Experimental game-driven trigger bridge for validated EU Wii U BOTW v208."""
import argparse
import math
from pathlib import Path
import signal
import sys
import time

sys.path.insert(0, str(Path(__file__).parent / 'tools'))
from botw_state import BotwState
from local_memory import LocalMemory
from bridge import HID, Logger


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--pid', type=int, required=True)
    p.add_argument('--serial')
    p.add_argument('--hidapi', help='Custom hidapi dylib')
    p.add_argument('--seconds', type=float, default=3600)
    p.add_argument('--dry-run', action='store_true')
    p.add_argument('--log')
    a = p.parse_args()
    if not math.isfinite(a.seconds) or not 0 < a.seconds <= 86400:
        p.error('seconds must be in (0,86400]')
    log = Logger(a.log)
    memory = device = None
    stopped = False

    def stop(signum, frame):
        nonlocal stopped
        stopped = True

    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, stop)
    try:
        memory = LocalMemory(a.pid)
        state = BotwState(memory)
        if not a.dry_run:
            device = HID(a.hidapi) if a.hidapi else HID()
        previous, sent = None, False
        next_connect, waiting, last_input = 0, False, time.monotonic()
        deadline = time.monotonic() + a.seconds
        while not stopped and time.monotonic() < deadline:
            sample = state.sample()
            if sample != previous:
                log.emit('game', **sample)
                previous = sample
            desired = sample['effect']
            if device:
                if not device.dev and time.monotonic() >= next_connect:
                    try:
                        serial = device.open(a.serial)
                        device.effect(False, (2, 5, 8, 4))
                        sent, waiting, last_input = False, False, time.monotonic()
                        log.emit('open', shared=True, game_driven=True)
                    except RuntimeError as e:
                        if not waiting:
                            log.emit('waiting_for_controller', error=str(e))
                        if device.dev:
                            device.close()
                            device = HID(a.hidapi) if a.hidapi else HID()
                        waiting, next_connect = True, time.monotonic() + 2
                if device.dev:
                    try:
                        # Also notice a silent BT loss, rather than retaining the last effect.
                        if device.read():
                            last_input = time.monotonic()
                        if time.monotonic() - last_input > .75:
                            raise RuntimeError('Controller input stopped')
                        if desired != sent:
                            device.effect(desired, (2, 5, 8, 4))
                            log.emit('output', effect='bow' if desired else 'off', transport_only=True)
                            sent = desired
                    except RuntimeError as e:
                        log.emit('controller_lost', error=str(e))
                        try:
                            device.effect(False, (2, 5, 8, 4))
                        except RuntimeError:
                            pass
                        device.close()
                        device = HID(a.hidapi) if a.hidapi else HID()
                        sent, next_connect, waiting = False, time.monotonic() + 2, False
            time.sleep(.025)
        return 0
    except (RuntimeError, OSError, ValueError) as e:
        log.emit('error', error=str(e))
        return 1
    finally:
        if device and device.dev:
            try:
                device.effect(False, (2, 5, 8, 4))
                log.emit('output', effect='off', reason='cleanup', transport_only=True)
            except RuntimeError as e:
                log.emit('cleanup_error', error=str(e))
        if device:
            device.close()
        if memory:
            memory.close()
        log.close()


if __name__ == '__main__':
    sys.exit(main())
