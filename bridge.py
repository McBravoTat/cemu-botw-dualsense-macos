#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Trigger report encoding follows dualsensectl / dualsensectl-macos.
# Original driver notice: Copyright (c) 2020 Sony Interactive Entertainment.
"""Experimental macOS Bluetooth R2 -> adaptive trigger bridge. No Cemu injection."""
import argparse
import ctypes as C
import ctypes.util
import json
import math
from pathlib import Path
import signal
import struct
import sys
import time
import zlib
from dataclasses import dataclass

VID, PID = 0x054C, 0x0CE6  # Standard DualSense only; Edge not validated.


@dataclass(frozen=True)
class Sample:
    r2: int
    digital: bool
    format: str


def parse_input(data):
    """Accept only documented report layouts with a report ID; never guess offsets."""
    if len(data) == 78 and data[0] == 0x31:
        if zlib.crc32(b'\xa1' + data[:-4]) != struct.unpack('<I', data[-4:])[0]:
            raise ValueError('Bluetooth input CRC mismatch')
        return Sample(data[7], bool(data[10] & 8), 'bt-full')
    if len(data) == 10 and data[0] == 1:
        return Sample(data[9], bool(data[6] & 8), 'bt-simple')
    raise ValueError(f'Unsupported input: length={len(data)}, id={data[:1].hex()}')


def output_report(on, seq, bow=(2, 5, 8, 4)):
    """Same right-only report/encoding as dualsensectl-macos command_trigger_bow/off."""
    start, stop, strength, snap = bow
    if not (1 <= start < stop <= 8 and 1 <= strength <= 8 and 1 <= snap <= 8):
        raise ValueError('bow requires 1 <= start < stop <= 8, strength/snap 1..8')
    b = bytearray(78)
    b[0:4] = bytes((0x31, (seq & 15) << 4, 0x10, 0x04))
    b[13] = 0x22 if on else 0x05
    if on:
        zones = (1 << start) | (1 << stop)
        b[14:17] = bytes((zones & 255, zones >> 8, (strength - 1) | ((snap - 1) << 3)))
    # Upstream fills both payload slots; only RIGHT's enable bit is set.
    # Preserve that byte-for-byte behavior, including CRC, for this prototype.
    b[24:35] = b[13:24]
    b[-4:] = struct.pack('<I', zlib.crc32(b'\xa2' + b[:-4]))
    return bytes(b)


class Gate:
    """Analog threshold with hysteresis; deliberately separate from Cemu's logical ZR."""
    def __init__(self, press=32, release=16):
        if not 0 <= release < press <= 255:
            raise ValueError('Require 0 <= release < press <= 255')
        self.press, self.release, self.on = press, release, False

    def update(self, value):
        self.on = value > self.release if self.on else value >= self.press
        return self.on


class DeviceInfo(C.Structure):
    pass


DeviceInfo._fields_ = [
    ('path', C.c_char_p), ('vendor_id', C.c_ushort), ('product_id', C.c_ushort),
    ('serial_number', C.c_wchar_p), ('release_number', C.c_ushort),
    ('manufacturer_string', C.c_wchar_p), ('product_string', C.c_wchar_p),
    ('usage_page', C.c_ushort), ('usage', C.c_ushort), ('interface_number', C.c_int),
    ('next', C.POINTER(DeviceInfo)), ('bus_type', C.c_int),
]


class HID:
    def __init__(self, library=None):
        candidates = [library] if library else [
            '/opt/homebrew/opt/hidapi/lib/libhidapi.dylib',
            '/usr/local/opt/hidapi/lib/libhidapi.dylib', ctypes_path()]
        self.lib = None
        for path in filter(None, candidates):
            try:
                self.lib = C.CDLL(path)
                break
            except OSError:
                pass
        if self.lib is None:
            raise RuntimeError('hidapi not found. Install: brew install hidapi; or use --hidapi PATH')
        h = self.lib
        signatures = {
            'hid_init': ([], C.c_int), 'hid_exit': ([], C.c_int),
            'hid_darwin_set_open_exclusive': ([C.c_int], None),
            'hid_darwin_is_device_open_exclusive': ([C.c_void_p], C.c_int),
            'hid_enumerate': ([C.c_ushort, C.c_ushort], C.POINTER(DeviceInfo)),
            'hid_free_enumeration': ([C.POINTER(DeviceInfo)], None),
            'hid_open_path': ([C.c_char_p], C.c_void_p),
            'hid_read_timeout': ([C.c_void_p, C.c_void_p, C.c_size_t, C.c_int], C.c_int),
            'hid_write': ([C.c_void_p, C.c_void_p, C.c_size_t], C.c_int),
            'hid_error': ([C.c_void_p], C.c_wchar_p),
            'hid_close': ([C.c_void_p], None),
        }
        for name, (args, result) in signatures.items():
            fn = getattr(h, name)
            fn.argtypes, fn.restype = args, result
        if h.hid_init() != 0:
            raise RuntimeError('hid_init failed')
        # Must be AFTER hid_init, which resets this option to exclusive.
        h.hid_darwin_set_open_exclusive(0)
        self.dev, self.seq = None, 0

    def devices(self):
        head = self.lib.hid_enumerate(VID, PID)
        result, node = [], head
        try:
            while node:
                d = node.contents
                result.append(dict(path=d.path, serial=d.serial_number or '',
                                   bus=d.bus_type, interface=d.interface_number))
                node = d.next
        finally:
            self.lib.hid_free_enumeration(head)
        return result

    def open(self, serial=None):
        devices = [d for d in self.devices() if d['bus'] == 2]  # HID_API_BUS_BLUETOOTH
        if serial:
            devices = [d for d in devices if d['serial'].casefold() == serial.casefold()]
        if len(devices) != 1:
            raise RuntimeError(f'Expected one Bluetooth DualSense, found {len(devices)}. Use list / --serial.')
        self.dev = self.lib.hid_open_path(devices[0]['path'])
        if not self.dev:
            raise RuntimeError(f'HID open failed: {self.lib.hid_error(None)}')
        if self.lib.hid_darwin_is_device_open_exclusive(self.dev) != 0:
            self.lib.hid_close(self.dev)
            self.dev = None
            raise RuntimeError('Shared HID open was not confirmed; refusing to continue')
        return devices[0]['serial']

    def read(self):
        if not self.dev:
            raise RuntimeError('Controller is not open')
        b = (C.c_ubyte * 128)()
        n = self.lib.hid_read_timeout(self.dev, b, len(b), 50)
        if n < 0:
            raise RuntimeError(f'HID read failed: {self.lib.hid_error(self.dev)}')
        return bytes(b[:n])

    def effect(self, on, bow):
        if not self.dev:
            raise RuntimeError('Controller is not open')
        packet = output_report(on, self.seq, bow)
        b = C.create_string_buffer(packet, len(packet))
        n = self.lib.hid_write(self.dev, b, len(packet))
        if n != len(packet):
            raise RuntimeError(f'HID write returned {n}/{len(packet)}: {self.lib.hid_error(self.dev)}')
        self.seq = (self.seq + 1) & 15

    def close(self):
        if self.dev:
            self.lib.hid_close(self.dev)
            self.dev = None
        self.lib.hid_exit()


def ctypes_path():
    return C.util.find_library('hidapi')


class Logger:
    def __init__(self, path=None):
        self.file = open(path, 'x', encoding='utf8') if path else None
        self.start = time.monotonic()

    def emit(self, event, **values):
        row = dict(t=round(time.monotonic() - self.start, 6), event=event, **values)
        line = json.dumps(row, ensure_ascii=False)
        print(line, flush=True)
        if self.file:
            self.file.write(line + '\n')
            self.file.flush()

    def close(self):
        if self.file:
            self.file.close()


def run_loop(device, args, log, stopped, clock=time.monotonic):
    gate = Gate(args.press, args.release)
    start = last_valid = clock()
    last_log, last_write, sent = -math.inf, start, False
    writes = args.command in ('follow', 'armed') and not args.dry_run
    try:
        if writes:
            sent = args.command == 'armed'
            device.effect(sent, args.bow)
            log.emit('output', effect='bow' if sent else 'off',
                     reason='prearm' if sent else 'startup', transport_only=True)
        while not stopped() and clock() - start < args.seconds:
            data = device.read()
            now = clock()
            if not data:
                if now - last_valid >= args.stale:
                    raise RuntimeError(f'No valid controller input for {args.stale}s')
                continue
            try:
                sample = parse_input(data)
            except ValueError as e:
                # Fail closed on a corrupt/unknown frame instead of applying guessed input.
                log.emit('invalid_input', error=str(e))
                raise RuntimeError(str(e)) from e
            last_valid = now
            previous = gate.on
            desired = gate.update(sample.r2)
            if args.raw:
                log.emit('raw', hex=data.hex())
            if previous != desired or now - last_log >= .25:
                log.emit('input', r2=sample.r2, digital=sample.digital,
                         format=sample.format, gate=desired, zr='proxy_r2')
                last_log = now
            # Edge writes by default; optional refresh helps diagnose another output writer.
            refresh = args.refresh > 0 and now - last_write >= args.refresh
            if writes and args.command == 'follow' and (desired != sent or refresh):
                before = clock()
                device.effect(desired, args.bow)
                sent, last_write = desired, clock()
                log.emit('output', effect='bow' if desired else 'off',
                         reason='refresh' if desired == previous else 'edge',
                         write_ms=round((last_write - before) * 1000, 3), transport_only=True)
            elif args.command == 'follow' and args.dry_run and previous != desired:
                log.emit('would_output', effect='bow' if desired else 'off')
    finally:
        if writes:
            # Normal stop, Ctrl+C/SIGTERM, timeout and read/write errors all attempt release.
            # No software can guarantee delivery after disconnect, SIGKILL or loss of power.
            device.effect(False, args.bow)
            log.emit('output', effect='off', reason='cleanup', transport_only=True)


def replay(path, press, release):
    gate = Gate(press, release)
    for line in Path(path).read_text().splitlines():
        row = json.loads(line)
        if row.get('event') == 'raw' or 'hex' in row:
            s = parse_input(bytes.fromhex(row['hex']))
            previous = gate.on
            on = gate.update(s.r2)
            if on != previous:
                print(json.dumps(dict(t=row.get('t'), r2=s.r2, effect='bow' if on else 'off')))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=['list', 'monitor', 'follow', 'armed', 'off', 'replay'])
    p.add_argument('--serial')
    p.add_argument('--hidapi', help='Path to hidapi 0.12+ dylib')
    p.add_argument('--seconds', type=float, default=30, help='Bounded run; default 30 seconds')
    p.add_argument('--press', type=int, default=32)
    p.add_argument('--release', type=int, default=16)
    p.add_argument('--stale', type=float, default=.75)
    p.add_argument('--refresh', type=float, default=0, help='Optional effect refresh period in seconds, >=0.1')
    p.add_argument('--bow', nargs=4, type=int, default=[2, 5, 8, 4], metavar=('START','STOP','STR','SNAP'))
    p.add_argument('--dry-run', action='store_true', help='Read real input, send no output')
    p.add_argument('--raw', action='store_true', help='Log every input packet; potentially large')
    p.add_argument('--log', help='New JSONL path (existing files are not overwritten)')
    p.add_argument('--trace', help='Raw JSONL for offline replay')
    a = p.parse_args()
    try:
        Gate(a.press, a.release)
        output_report(False, 0, a.bow)
        if not all(math.isfinite(x) for x in (a.seconds, a.stale, a.refresh)):
            p.error('Durations must be finite')
        if a.seconds <= 0 or a.stale < .1 or (a.refresh != 0 and a.refresh < .1):
            p.error('seconds > 0, stale >= 0.1, refresh = 0 or >= 0.1 required')
        if a.command == 'replay':
            if not a.trace:
                p.error('replay requires --trace')
            replay(a.trace, a.press, a.release)
            return 0
        if sys.platform != 'darwin':
            p.error('Live mode requires macOS; replay works on any platform')
        if a.dry_run and a.command == 'off':
            p.error('off with --dry-run is ambiguous; use monitor')
        log = Logger(a.log)
    except (ValueError, OSError) as e:
        p.error(str(e))
    device, stopped = None, False

    def stop(signum, frame):
        nonlocal stopped
        stopped = True

    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, stop)
    try:
        device = HID(a.hidapi)
        if a.command == 'list':
            for d in device.devices():
                log.emit('device', serial=d['serial'], bus=d['bus'], interface=d['interface'])
            return 0
        serial = device.open(a.serial)
        log.emit('open', serial=serial, shared=True, command=a.command,
                 dry_run=a.dry_run, press=a.press, release=a.release)
        if a.command == 'off':
            device.effect(False, a.bow)
            log.emit('output', effect='off', reason='manual', transport_only=True)
        else:
            run_loop(device, a, log, lambda: stopped)
        return 0
    except (RuntimeError, OSError, AttributeError) as e:
        log.emit('error', error=str(e))
        return 1
    finally:
        if device:
            device.close()
        log.close()


if __name__ == '__main__':
    sys.exit(main())
