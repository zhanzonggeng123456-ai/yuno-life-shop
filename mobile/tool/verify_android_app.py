"""Check the arm64 Flutter runtime, ELF LOAD alignment, ZIP alignment and signature."""
import argparse
import os
from pathlib import Path
import struct
import subprocess
import zipfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('apk', type=Path)
    parser.add_argument('--build-tools', type=Path, default=Path(
        os.environ.get('ANDROID_SDK_ROOT', Path.home() / 'Library/Android/sdk')) / 'build-tools/36.0.0')
    args = parser.parse_args()
    with zipfile.ZipFile(args.apk) as archive:
        names = archive.namelist()
        for required in ('lib/arm64-v8a/libflutter.so',
                         'assets/flutter_assets/kernel_blob.bin'):
            if required not in names:
                parser.error('Missing Flutter debug runtime or Dart assets: ' + required)
        for name in sorted(n for n in names if n.endswith('.so')):
            data = archive.read(name)
            if data[:4] != b'\x7fELF' or data[4] not in (1, 2):
                parser.error('Invalid ELF: ' + name)
            endian = '<' if data[5] == 1 else '>'
            wide = data[4] == 2
            offset = struct.unpack_from(endian + ('Q' if wide else 'I'), data, 32 if wide else 28)[0]
            size, count = struct.unpack_from(endian + 'HH', data, 54 if wide else 42)
            aligns = []
            for index in range(count):
                start = offset + index * size
                if struct.unpack_from(endian + 'I', data, start)[0] == 1:
                    align = struct.unpack_from(endian + ('Q' if wide else 'I'), data, start + (48 if wide else 28))[0]
                    if align < 16384:
                        parser.error('ELF LOAD alignment below 16 KB: ' + name)
                    aligns.append(hex(align))
            if not aligns:
                parser.error('No LOAD segments: ' + name)
            print(name, 'LOAD', ','.join(aligns), flush=True)
    subprocess.run([str(args.build_tools / 'apksigner'), 'verify', '--verbose', str(args.apk)], check=True)
    subprocess.run([str(args.build_tools / 'zipalign'), '-c', '-P', '16', '4', str(args.apk)], check=True)
    print('Flutter runtime, Dart assets, ELF/ZIP 16 KB alignment and signature verified.')


if __name__ == '__main__':
    main()
