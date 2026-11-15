# SPDX-License-Identifier: GPL-3.0-or-later
"""Client for the experimental local Cemu read-only exporter."""
import json
import socket
import struct


class LocalMemory:
    def __init__(self, pid):
        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.socket.settimeout(3)
        try:
            self.socket.connect(f'/private/tmp/cemu-botw-{int(pid)}.sock')
            self.stream = self.socket.makefile('rb')
        except OSError:
            self.socket.close()
            raise

    def info(self):
        self.socket.sendall(b'info\n')
        line = self.stream.readline(1024)
        if not line.endswith(b'\n'):
            raise RuntimeError('Missing exporter status')
        return json.loads(line)

    def read(self, address, size):
        if not 0x01000000 <= address < address + size <= 0x50000000 or not 1 <= size <= 65536:
            raise ValueError('Invalid guest range')
        self.socket.sendall(f'read {address:x} {size}\n'.encode())
        result = self.stream.readline(128)
        if result != f'OK {size}\n'.encode():
            raise RuntimeError(result.decode(errors='replace').strip())
        data = self.stream.read(size)
        if len(data) != size:
            raise ConnectionError('Truncated guest data')
        return data

    def u32(self, address):
        return struct.unpack('>I', self.read(address, 4))[0]

    def close(self):
        self.stream.close()
        self.socket.close()
