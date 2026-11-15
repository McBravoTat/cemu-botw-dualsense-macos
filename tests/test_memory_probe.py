import io
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from memory_probe import Reader, diff


def response(body, ack=True):
    return (b'+' if ack else b'') + b'$' + body + f'#{sum(body) & 255:02x}'.encode()


class Socket:
    def __init__(self, data):
        self.data, self.sent = io.BytesIO(data), []

    def makefile(self, mode):
        return self.data

    def sendall(self, data):
        self.sent.append(data)


class ProbeTests(unittest.TestCase):
    def test_reads_guest_address_and_sends_only_memory_read_and_ack(self):
        sock = Socket(response(b'12345678'))
        self.assertEqual(Reader(sock).read(0x10000000, 4), bytes.fromhex('12345678'))
        self.assertEqual(sock.sent, [b'$m10000000,4#4e', b'+'])

    def test_hex_data_starting_with_E_is_not_error(self):
        self.assertEqual(Reader(Socket(response(b'E0000000'))).read(0, 4), b'\xe0\0\0\0')

    def test_error_response_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'failed'):
            Reader(Socket(response(b'E01'))).read(0, 1)

    def test_corrupt_response_sends_nack_and_aborts(self):
        sock = Socket(b'+$00#00')
        with self.assertRaisesRegex(RuntimeError, 'checksum'):
            Reader(sock).read(0, 1)
        self.assertEqual(sock.sent[-1], b'-')

    def test_short_response_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'Short'):
            Reader(Socket(response(b'00'))).read(0, 2)

    def test_split_reads_in_256_byte_chunks(self):
        sock = Socket(response(b'01' * 256) + response(b'02' * 4, ack=False))
        self.assertEqual(Reader(sock).read(0x100, 260), b'\x01' * 256 + b'\x02' * 4)
        self.assertEqual(len([x for x in sock.sent if x.startswith(b'$m')]), 2)

    def test_bounds_prevent_invalid_or_giant_requests(self):
        sock = Socket(b'')
        for addr, size in [(0,0),(-1,1),(0xffffffff,2),(0,2**21)]:
            with self.assertRaises(ValueError):
                Reader(sock).read(addr, size)
        self.assertEqual(sock.sent, [])

    def test_diff_decodes_powerpc_big_endian(self):
        changes = diff(bytes.fromhex('000000013f800000'), bytes.fromhex('0000000240000000'), 0x1000)
        self.assertEqual(changes[0]['after_u32be'], 2)
        self.assertEqual(changes[1]['after_f32be'], '2.0')


if __name__ == '__main__':
    unittest.main()
