import io
import json
from pathlib import Path
import struct
import sys
import unittest
from types import SimpleNamespace
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bridge


def frame(value, digital=False):
    data = bytearray(78)
    data[0], data[7], data[10] = 0x31, value, 8 if digital else 0
    data[-4:] = struct.pack('<I', zlib.crc32(b'\xa1' + data[:-4]))
    return bytes(data)


class FakeDevice:
    def __init__(self, frames):
        self.frames, self.effects, self.now = iter(frames), [], 0

    def read(self):
        self.now += .1
        value = next(self.frames, b'')
        if isinstance(value, Exception):
            raise value
        return value

    def effect(self, on, bow):
        self.effects.append(on)


class Log:
    def emit(self, *args, **kwargs):
        pass


def run_fake(device, **options):
    opts = dict(command='follow', dry_run=False, press=32, release=16, bow=(2,5,8,4),
                seconds=.6, stale=.75, refresh=0, raw=False)
    opts.update(options)
    bridge.run_loop(device, SimpleNamespace(**opts), Log(), lambda: False, lambda: device.now)


class BridgeTests(unittest.TestCase):
    def test_packets_match_unmodified_c_oracle_all_sequence_numbers(self):
        packets = Path(__file__).with_name('reference_packets.txt').read_text().splitlines()
        self.assertEqual(len(packets), 32)
        for on, offset in [(True, 0), (False, 16)]:
            for seq in range(16):
                # Upstream initializes identical left effect bytes too, but leaves its enable
                # bit unset. Match the FULL packet, including these ignored bytes and CRC.
                self.assertEqual(bridge.output_report(on, seq).hex(), packets[offset + seq])

    def test_synthetic_full_report_distinguishes_analog_and_digital(self):
        self.assertEqual(bridge.parse_input(frame(88, False)), bridge.Sample(88, False, 'bt-full'))
        self.assertEqual(bridge.parse_input(frame(0, True)), bridge.Sample(0, True, 'bt-full'))

    def test_closed_hid_handle_cannot_reach_native_read_or_write(self):
        device = bridge.HID.__new__(bridge.HID)
        device.dev = None
        with self.assertRaisesRegex(RuntimeError, 'not open'):
            device.read()
        with self.assertRaisesRegex(RuntimeError, 'not open'):
            device.effect(True, (2,5,8,4))

    def test_simple_and_full_right_trigger(self):
        self.assertEqual(bridge.parse_input(frame(255, True)).r2, 255)
        simple = bytes([1,128,128,128,128,8,8,0,0,173])
        self.assertEqual(bridge.parse_input(simple), bridge.Sample(173, True, 'bt-simple'))

    def test_corrupt_frame_rejected(self):
        raw = bytearray(frame(255)); raw[7] = 0
        with self.assertRaisesRegex(ValueError, 'CRC'):
            bridge.parse_input(raw)

    def test_short_and_unknown_frames_rejected(self):
        for raw in [b'', bytes(77), bytes(73), b'\x01' * 64, b'\x31' * 10]:
            with self.assertRaises(ValueError):
                bridge.parse_input(raw)

    def test_noise_near_threshold_does_not_chatter(self):
        gate = bridge.Gate()
        values = [0,31,32,31,20,17,16,17,31,32,0]
        self.assertEqual([gate.update(v) for v in values],
                         [False,False,True,True,True,True,False,False,False,True,False])

    def test_press_hold_release_only_edge_writes(self):
        d = FakeDevice([frame(x) for x in [0,45,255,200,0,0]])
        run_fake(d)
        self.assertEqual(d.effects, [False, True, False, False])

    def test_read_failure_attempts_release(self):
        d = FakeDevice([frame(255), RuntimeError('disconnected')])
        with self.assertRaisesRegex(RuntimeError, 'disconnected'):
            run_fake(d)
        self.assertEqual(d.effects, [False, True, False])

    def test_stale_input_attempts_release(self):
        d = FakeDevice([frame(255)])
        with self.assertRaisesRegex(RuntimeError, 'No valid'):
            run_fake(d, seconds=2, stale=.3)
        self.assertEqual(d.effects, [False, True, False])

    def test_bad_frame_attempts_release(self):
        d = FakeDevice([frame(255), b'bad'])
        with self.assertRaises(RuntimeError):
            run_fake(d)
        self.assertEqual(d.effects, [False, True, False])

    def test_dry_run_never_writes_even_at_cleanup(self):
        d = FakeDevice([frame(255), frame(0)])
        run_fake(d, dry_run=True)
        self.assertEqual(d.effects, [])

    def test_monitor_never_writes(self):
        d = FakeDevice([frame(255), frame(0)])
        run_fake(d, command='monitor')
        self.assertEqual(d.effects, [])

    def test_armed_preloads_effect_and_keeps_it_across_release(self):
        d = FakeDevice([frame(0), frame(255), frame(0)])
        run_fake(d, command='armed')
        self.assertEqual(d.effects, [True, False])

    def test_bow_validation(self):
        for bow in [(0,5,8,4),(5,2,8,4),(2,9,8,4),(2,5,0,4),(2,5,8,9)]:
            with self.assertRaises(ValueError):
                bridge.output_report(True, 0, bow)


if __name__ == '__main__':
    unittest.main()
