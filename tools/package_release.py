#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Make an allowlisted source archive, excluding local runtime and personal captures."""
import argparse
from pathlib import Path
import re
import zipfile

ROOT = Path(__file__).resolve().parents[1]
ROOT_FILES = ('README.md', 'README.ru.md', 'COMPATIBILITY.md', 'TELEMETRY.md',
              'NOTICE.md', 'CONTRIBUTING.md', 'CHANGELOG.md', 'LICENSE', 'VERSION',
              '.gitignore', 'cemu-build.json', 'bridge.py', 'botw_bridge.py',
              'doctor.py', 'launch_botw.py', 'Start BOTW Triggers.command')
TOOL_FILES = ('botw_state.py', 'cemu_memory_export.c', 'local_memory.py',
              'memory_probe.py', 'reference_packets.c', 'package_release.py', 'README.md')


def source_files(root=ROOT):
    files = [root / name for name in ROOT_FILES]
    files += [root / 'tools' / name for name in TOOL_FILES]
    files += sorted((root / 'tests').glob('test_*.py'))
    files += [root / 'tests' / name for name in
              ('reference_packets.txt', 'r2_trace.jsonl', 'export_fixture.cpp', 'README.md')]
    files += [root / '.github/workflows/ci.yml']
    for path in files:
        if not path.is_file() or path.is_symlink():
            raise ValueError(f'Missing or symlinked public source: {path.name}')
        text = path.read_text(encoding='utf8')
        if re.search(r'/(?:Users|home)/[^/\s]+', text):
            raise ValueError(f'Personal home path found in {path.name}')
        if re.search(r'(?<![\w])(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}(?![\w])', text):
            raise ValueError(f'Device address found in {path.name}')
    return files


def package(output, root=ROOT):
    files = source_files(root)
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            info = zipfile.ZipInfo('cemu-botw-dualsense-macos/' + path.relative_to(root).as_posix(),
                                   date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.compress_type = zipfile.ZIP_DEFLATED
            mode = 0o100755 if path.name.endswith('.command') else 0o100644
            info.external_attr = mode << 16
            archive.writestr(info, path.read_bytes())
    return len(files)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, default=ROOT / 'dist/source.zip')
    args = p.parse_args()
    try:
        count = package(args.output)
    except (OSError, ValueError) as e:
        p.exit(1, f'Packaging refused: {e}\n')
    print(f'Created source archive with {count} allowlisted files: {args.output}')


if __name__ == '__main__':
    main()
