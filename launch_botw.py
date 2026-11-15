#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Start Cemu with the read-only BOTW reader and Bluetooth trigger bridge."""
import argparse
import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time

from doctor import inspect_install

ROOT = Path(__file__).resolve().parent


def verify_export(pid):
    from tools.local_memory import LocalMemory
    reports = []
    for _ in range(3):
        memory = LocalMemory(pid)
        try:
            info = memory.info()
            if info.get('pid') != pid or info.get('read_only') is not True:
                raise RuntimeError('Unexpected exporter identity')
            if info.get('running') not in (True, False):
                raise RuntimeError('Cemu running-state export is missing')
            reports.append(info)
        finally:
            memory.close()
    rejected = []
    for command in (b'read ffffffffffffffff 2\n', b'read 10000000 65537\n', b'unsupported\n'):
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as peer:
            peer.settimeout(3)
            peer.connect(f'/private/tmp/cemu-botw-{pid}.sock')
            peer.sendall(command)
            reply = peer.recv(128)
            if not reply.startswith(b'ERR invalid-range-or-command'):
                raise RuntimeError('Exporter accepted an invalid request')
            rejected.append(command.decode().strip())
    return dict(reconnects=len(reports), invalid_requests_rejected=rejected)


def bridge_command(args, pid, log_path):
    result = [sys.executable, str(ROOT / 'botw_bridge.py'), '--pid', str(pid),
              '--seconds', str(args.seconds), '--log', str(log_path)]
    for flag, value in (('--serial', args.serial), ('--hidapi', args.hidapi)):
        if value:
            result += [flag, str(value)]
    if args.dry_run:
        result.append('--dry-run')
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cemu', type=Path, default=Path('/Applications/Cemu.app'))
    p.add_argument('--mlc', type=Path, help='Optional separate MLC; default is your normal Cemu data')
    p.add_argument('--serial', help='Choose one controller when several are connected')
    p.add_argument('--hidapi', type=Path, help='Custom hidapi dylib')
    p.add_argument('--seconds', type=float, default=86400)
    p.add_argument('--dry-run', action='store_true', help='Read game state without opening HID or sending effects')
    p.add_argument('--experimental-cemu', action='store_true',
                   help='Explicitly try an unverified Cemu executable; all game checks remain enabled')
    p.add_argument('--check', action='store_true', help='Only check dependencies; launch nothing')
    a = p.parse_args()
    if not math.isfinite(a.seconds) or not 0 < a.seconds <= 86400:
        p.error('seconds must be finite and in (0,86400]')
    if a.mlc and not a.mlc.expanduser().is_dir():
        p.error('--mlc must name an existing directory')
    try:
        report = inspect_install(a.cemu)
    except (OSError, ValueError) as e:
        p.exit(1, f'Check failed: {e}\n')
    if a.check:
        print(json.dumps(report, indent=2))
        return 0 if report['ready_for_known_build'] else 1
    if not report['host_supported'] or not report['python_supported']:
        p.exit(1, 'Game mode requires native arm64 Python 3.10+ on macOS.\n')
    if not report['cemu_found']:
        p.exit(1, 'Cemu.app not found. Select it with --cemu /path/to/Cemu.app.\n')
    if not report['cemu_known_build'] and not a.experimental_cemu:
        p.exit(1, 'Unverified Cemu executable. Run --check and read COMPATIBILITY.md.\n'
                  'An opt-in test is available with --experimental-cemu --dry-run.\n')
    if not report['clang_found']:
        p.exit(1, 'Command Line Tools are required: xcode-select --install\n')
    if not a.dry_run and not a.hidapi and not report['hidapi_found']:
        p.exit(1, 'hidapi is required: brew install hidapi\n')
    if not report['cemu_known_build']:
        print('EXPERIMENTAL: this Cemu build has not been validated. Runtime game checks stay enabled.', flush=True)
    running = subprocess.run(['/usr/bin/pgrep', '-x', 'Cemu'], capture_output=True, text=True)
    if running.returncode == 0:
        p.exit(1, 'Close Cemu before starting this launcher.\n')
    if running.returncode != 1:
        p.exit(1, 'Could not check for an existing Cemu process.\n')

    runtime = ROOT / '.runtime'
    runtime.mkdir(exist_ok=True)
    library = runtime / 'cemu_memory_export.dylib'
    source = ROOT / 'tools/cemu_memory_export.c'
    stamp_path = runtime / 'exporter-source.sha256'
    source_digest = hashlib.sha256(source.read_bytes()).hexdigest()
    try:
        if not library.exists() or not stamp_path.exists() or stamp_path.read_text() != source_digest:
            subprocess.run(['/usr/bin/clang', '-arch', 'arm64', '-Wall', '-Wextra', '-Werror', '-O2',
                            '-dynamiclib', str(source), '-o', str(library)], check=True)
            stamp_path.write_text(source_digest)
    except (OSError, subprocess.CalledProcessError) as e:
        p.exit(1, f'Could not build the local reader: {e}\n')
    logs = ROOT / 'logs'
    logs.mkdir(exist_ok=True)
    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    env = os.environ.copy()
    env['DYLD_INSERT_LIBRARIES'] = str(library)
    command = [str(a.cemu.expanduser().resolve() / 'Contents/MacOS/Cemu'),
               '--title-id', '00050000101c9500']
    if a.mlc:
        command += ['--mlc', str(a.mlc.expanduser().resolve())]
    cemu = bridge = None
    stopped = False

    def stop(signum, frame):
        nonlocal stopped
        stopped = True

    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, stop)
    try:
        with (logs / f'cemu-{stamp}.log').open('x') as output:
            cemu = subprocess.Popen(command, env=env, stdout=output, stderr=subprocess.STDOUT,
                                    start_new_session=True)
            socket_path = Path(f'/private/tmp/cemu-botw-{cemu.pid}.sock')
            deadline = time.monotonic() + 30
            while not socket_path.exists():
                if stopped:
                    return 0
                if cemu.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError('Local reader did not start. See the Cemu log; no effects were enabled.')
                time.sleep(.1)
            checked = verify_export(cemu.pid)
            (logs / f'export-check-{stamp}.json').write_text(json.dumps(checked, indent=2) + '\n')
            bridge = subprocess.Popen(bridge_command(a, cemu.pid, logs / f'triggers-{stamp}.jsonl'))
            print('Bridge started. Continue BOTW, then take out the bow.', flush=True)
            while not stopped and cemu.poll() is None and bridge.poll() is None:
                time.sleep(.25)
            return bridge.poll() or 0
    except (RuntimeError, OSError, ValueError) as e:
        print(f'Launch failed: {e}', file=sys.stderr)
        return 1
    finally:
        if bridge and bridge.poll() is None:
            bridge.terminate()
            try:
                bridge.wait(timeout=5)
            except subprocess.TimeoutExpired:
                bridge.kill()
                bridge.wait()
        # Leave Cemu open if the bridge stops; do not overwrite game/app files.
        if cemu and cemu.poll() is not None:
            path = Path(f'/private/tmp/cemu-botw-{cemu.pid}.sock')
            if path.exists():
                path.unlink()


if __name__ == '__main__':
    sys.exit(main())
