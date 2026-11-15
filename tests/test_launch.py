from contextlib import redirect_stderr, redirect_stdout
import hashlib
import io
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import doctor
import launch_botw


class LaunchTests(unittest.TestCase):
    def test_doctor_handles_app_path_with_spaces_without_creating_files(self):
        with tempfile.TemporaryDirectory() as directory:
            app = Path(directory) / 'My Cemu.app'
            binary = app / 'Contents/MacOS/Cemu'
            binary.parent.mkdir(parents=True)
            binary.write_bytes(b'synthetic executable')
            before = sorted(str(p) for p in Path(directory).rglob('*'))
            manifest = dict(sha256=hashlib.sha256(binary.read_bytes()).hexdigest())
            self.assertTrue(doctor.inspect_install(app, manifest)['cemu_known_build'])
            self.assertFalse(doctor.inspect_install(app, dict(sha256='unknown'))['cemu_known_build'])
            self.assertEqual(before, sorted(str(p) for p in Path(directory).rglob('*')))

    def test_controller_and_library_selection_reach_child_process(self):
        args = SimpleNamespace(seconds=30, serial='example-controller',
                               hidapi=Path('/custom/libhidapi.dylib'), dry_run=True)
        command = launch_botw.bridge_command(args, 123, Path('test.jsonl'))
        self.assertEqual(command[command.index('--serial')+1], 'example-controller')
        self.assertEqual(command[command.index('--hidapi')+1], '/custom/libhidapi.dylib')
        self.assertIn('--dry-run', command)

    def test_invalid_duration_does_not_launch_or_inspect(self):
        for seconds in ('nan', 'inf', '0', '-1'):
            with patch.object(sys, 'argv', ['launch_botw', '--seconds', seconds]), \
                 patch.object(launch_botw, 'inspect_install') as inspect, \
                 patch.object(launch_botw.subprocess, 'Popen') as spawn, \
                 redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    launch_botw.main()
                inspect.assert_not_called()
                spawn.assert_not_called()

    def test_unknown_cemu_refused_before_creating_a_process(self):
        report = dict(host_supported=True, python_supported=True, cemu_found=True, cemu_known_build=False)
        with patch.object(sys, 'argv', ['launch_botw']), \
             patch.object(launch_botw, 'inspect_install', return_value=report), \
             patch.object(launch_botw.subprocess, 'Popen') as spawn, \
             redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                launch_botw.main()
            spawn.assert_not_called()

    def test_check_mode_never_starts_cemu(self):
        with patch.object(sys, 'argv', ['launch_botw', '--check']), \
             patch.object(launch_botw, 'inspect_install', return_value=dict(ready_for_known_build=True)), \
             patch.object(launch_botw.subprocess, 'Popen') as spawn, \
             redirect_stdout(io.StringIO()):
            self.assertEqual(launch_botw.main(), 0)
            spawn.assert_not_called()
