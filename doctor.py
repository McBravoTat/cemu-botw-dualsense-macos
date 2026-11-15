#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Read-only installation checks. Does not launch Cemu or open a controller."""
import argparse
import ctypes.util
import hashlib
import json
from pathlib import Path
import platform
import shutil
import sys

ROOT = Path(__file__).resolve().parent


def inspect_install(app, manifest=None):
    manifest = manifest or json.loads((ROOT / 'cemu-build.json').read_text())
    executable = Path(app).expanduser() / 'Contents/MacOS/Cemu'
    digest = hashlib.sha256(executable.read_bytes()).hexdigest() if executable.is_file() else None
    libraries = ['/opt/homebrew/opt/hidapi/lib/libhidapi.dylib',
                 '/usr/local/opt/hidapi/lib/libhidapi.dylib']
    result = dict(
        system=platform.system(), macos=platform.mac_ver()[0], architecture=platform.machine(),
        python=platform.python_version(), python_supported=sys.version_info >= (3, 10),
        cemu_found=digest is not None, cemu_sha256=digest,
        cemu_known_build=digest == manifest['sha256'],
        clang_found=shutil.which('clang') is not None,
        hidapi_found=any(Path(p).is_file() for p in libraries) or bool(ctypes.util.find_library('hidapi')),
    )
    result['host_supported'] = result['system'] == 'Darwin' and result['architecture'] == 'arm64'
    result['ready_for_known_build'] = all(result[key] for key in (
        'host_supported', 'python_supported', 'cemu_found', 'cemu_known_build', 'clang_found', 'hidapi_found'))
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cemu', type=Path, default=Path('/Applications/Cemu.app'))
    args = p.parse_args()
    try:
        result = inspect_install(args.cemu)
    except (OSError, ValueError) as e:
        p.exit(1, f'Check failed: {e}\n')
    print(json.dumps(result, indent=2))
    return 0 if result['ready_for_known_build'] else 1


if __name__ == '__main__':
    sys.exit(main())
