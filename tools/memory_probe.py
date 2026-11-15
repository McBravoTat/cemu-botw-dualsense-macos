#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Research only: bounded guest-memory reads via an already running Cemu GDB stub.

No BOTW addresses are supplied or claimed. Never sends pause, continue, breakpoint,
register-write or memory-write commands. Live compatibility is NOT yet validated.
"""
import argparse
import hashlib
import json
from pathlib import Path
import socket
import struct
import time


class Reader:
    def __init__(self, sock):
        self.sock = sock
        self.stream = sock.makefile('rb')

    def byte(self):
        b = self.stream.read(1)
        if not b:
            raise ConnectionError('Cemu closed the connection')
        return b

    def read_chunk(self, address, size):
        if not (0 <= address < 2**32 and 1 <= size <= 256 and address + size <= 2**32):
            raise ValueError('Require a 32-bit guest range, 1..256 bytes')
        payload = f'm{address:x},{size:x}'.encode('ascii')
        self.sock.sendall(b'$' + payload + f'#{sum(payload) & 255:02x}'.encode())
        start = self.byte()
        if start == b'-':
            raise RuntimeError('Cemu rejected request checksum')
        if start == b'+':
            start = self.byte()
        if start != b'$':
            raise RuntimeError(f'Unexpected RSP prefix {start!r}')
        body = bytearray()
        while True:
            b = self.byte()
            if b == b'#':
                break
            body += b
            if len(body) > 4096:
                raise RuntimeError('Oversized RSP packet')
        try:
            checksum = int(self.byte() + self.byte(), 16)
        except ValueError as e:
            raise RuntimeError('Malformed response checksum') from e
        if sum(body) & 255 != checksum:
            self.sock.sendall(b'-')
            raise RuntimeError('Response checksum mismatch; snapshot aborted')
        self.sock.sendall(b'+')
        if (len(body) == 3 and body.startswith(b'E')) or not body:
            raise RuntimeError(f'Cemu memory read failed: {body.decode(errors="replace")}')
        try:
            result = bytes.fromhex(body.decode('ascii'))
        except ValueError as e:
            raise RuntimeError('Expected hex memory data (target may be stopped)') from e
        if len(result) != size:
            raise RuntimeError(f'Short memory read: {len(result)}/{size}')
        return result

    def read(self, address, size):
        if size < 1 or size > 1024 * 1024 or address < 0 or address + size > 2**32:
            raise ValueError('Snapshot must be 1 byte..1 MiB within 32-bit guest memory')
        result = bytearray()
        while len(result) < size:
            result += self.read_chunk(address + len(result), min(256, size - len(result)))
        return bytes(result)

    def close(self):
        self.stream.close()


def diff(before, after, address):
    if len(before) != len(after):
        raise ValueError('Snapshots must have equal sizes and the same guest range')
    changes = []
    for i in range(0, len(before) - 3, 4):
        old, new = before[i:i+4], after[i:i+4]
        if old != new:
            changes.append(dict(address=f'0x{address+i:08x}', before=old.hex(), after=new.hex(),
                                before_u32be=int.from_bytes(old, 'big'),
                                after_u32be=int.from_bytes(new, 'big'),
                                before_f32be=repr(struct.unpack('>f', old)[0]),
                                after_f32be=repr(struct.unpack('>f', new)[0])))
    return changes


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('snapshot')
    s.add_argument('--port', type=int, required=True, help='Use the port from Cemu GDB log')
    s.add_argument('--address', type=lambda x: int(x, 0), required=True, help='Guest PPC address, NOT host address')
    s.add_argument('--size', type=lambda x: int(x, 0), required=True)
    s.add_argument('--label', required=True)
    s.add_argument('--out', type=Path, required=True)
    d = sub.add_parser('diff')
    d.add_argument('before', type=Path)
    d.add_argument('after', type=Path)
    d.add_argument('--address', type=lambda x: int(x, 0), required=True)
    a = p.parse_args()
    try:
        if a.cmd == 'diff':
            print(json.dumps(diff(a.before.read_bytes(), a.after.read_bytes(), a.address), indent=2))
            return
        metadata_path = Path(str(a.out) + '.json')
        if a.out.exists() or metadata_path.exists():
            p.error('Output exists; choose a new --out path')
        if not 1 <= a.size <= 1024 * 1024 or not 0 <= a.address < a.address + a.size <= 2**32:
            p.error('Require a valid 32-bit guest range of 1 byte..1 MiB')
        if not 1 <= a.port <= 65535:
            p.error('Invalid port')
        # Local Cemu only; no scanner and no LAN connection.
        with socket.create_connection(('127.0.0.1', a.port), timeout=3) as sock:
            reader = Reader(sock)
            try:
                started = time.monotonic()
                data = reader.read(a.address, a.size)
            finally:
                reader.close()
        with a.out.open('xb') as f:
            f.write(data)
        metadata = dict(label=a.label, guest_address=f'0x{a.address:08x}', size=len(data),
                        duration_s=time.monotonic() - started, sha256=hashlib.sha256(data).hexdigest(),
                        endian='big', atomic=False, source='Cemu GDB m packets',
                        validated_botw_state=False)
        with metadata_path.open('x') as f:
            json.dump(metadata, f, indent=2)
        print(json.dumps(metadata, indent=2))
    except (ValueError, OSError, RuntimeError) as e:
        p.exit(1, f'Probe failed: {e}\n')


if __name__ == '__main__':
    main()
