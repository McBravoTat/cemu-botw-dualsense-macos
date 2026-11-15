import json
import os
from pathlib import Path
import socket
import stat
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from local_memory import LocalMemory


@unittest.skipUnless(sys.platform == 'darwin' and os.environ.get('RUN_EXPORTER_TESTS') == '1',
                     'Set RUN_EXPORTER_TESTS=1 on macOS for the synthetic native test')
class ExporterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='botw-export-test-')
        temp = Path(cls.temp.name)
        library, host = temp / 'reader.dylib', temp / 'host'
        subprocess.run(['clang', '-Wall', '-Wextra', '-Werror', '-dynamiclib',
                        str(ROOT / 'tools/cemu_memory_export.c'), '-o', str(library)], check=True)
        subprocess.run(['clang++', '-std=c++17', '-Wall', '-Wextra', '-Werror',
                        '-Wl,-export_dynamic', str(ROOT / 'tests/export_fixture.cpp'),
                        '-o', str(host)], check=True)
        env = os.environ.copy()
        env['DYLD_INSERT_LIBRARIES'] = str(library)
        cls.proc = subprocess.Popen([str(host)], env=env, stdin=subprocess.PIPE,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if cls.proc.stdout.readline().strip() != 'READY':
            raise RuntimeError('Synthetic host failed to start')
        cls.path = Path(f'/private/tmp/cemu-botw-{cls.proc.pid}.sock')
        deadline = time.monotonic() + 5
        while not cls.path.exists() and time.monotonic() < deadline:
            time.sleep(.01)
        if not cls.path.exists():
            raise RuntimeError('Exporter did not start in synthetic host')

    @classmethod
    def tearDownClass(cls):
        cls.proc.communicate(timeout=5)
        cls.path.unlink(missing_ok=True)
        cls.temp.cleanup()

    def test_status_read_and_reconnect(self):
        for _ in range(3):
            memory = LocalMemory(self.proc.pid)
            try:
                info = memory.info()
                self.assertEqual(info['title_id'], '00050000101c9500')
                self.assertTrue(info['running'])
                self.assertEqual(memory.u32(0x10000000), 0x12345678)
                with self.assertRaisesRegex(RuntimeError, 'unmapped'):
                    memory.read(0x01000000, 4)
            finally:
                memory.close()

    def test_socket_is_owner_only(self):
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o600)

    def test_invalid_commands_and_overflows(self):
        requests = [b'write 10000000 1\n', b'read ffffffffffffffff 4\n',
                    b'read 10000000 65537\n', b'read 4fffffff 4\n',
                    b'read 10000000 4 extra\n', b'x' * 128 + b'\n']
        for request in requests:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as peer:
                peer.settimeout(3)
                peer.connect(str(self.path))
                peer.sendall(request)
                self.assertTrue(peer.recv(128).startswith(b'ERR'))
        memory = LocalMemory(self.proc.pid)
        try:
            self.assertEqual(memory.u32(0x10000000), 0x12345678)
        finally:
            memory.close()
