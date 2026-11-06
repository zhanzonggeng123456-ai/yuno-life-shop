"""Create a fresh, sparse disk for a Yuno-only Android acceptance AVD.

Uses the SDK's ext4 utility on a regular file, never a block device. The emulator
keeps its compatibility/space checks. No shared AVD, SDK, or Nino data is edited.
"""
import argparse
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-id', required=True)
    args = parser.parse_args()
    if not re.fullmatch(r'[0-9]+', args.run_id):
        parser.error('Use a new numeric run id')
    root = Path(__file__).resolve().parents[2]
    sdk = Path(os.environ.get('ANDROID_SDK_ROOT', Path.home() / 'Library/Android/sdk'))
    image = sdk / 'system-images/android-36/google_apis_ps16k/arm64-v8a'
    formatter = sdk / 'emulator/bin64/mkfs.ext4'
    if not image.is_dir() or not formatter.is_file():
        parser.error('Existing API 36 16KB image and SDK ext4 utility required')
    if shutil.disk_usage(root).free < 2 * 1024**3:
        parser.error('At least 2 GiB free required before preparing this disk')
    avds = root / 'data/android-avd'
    name = f'YunoAcceptance{args.run_id}'
    directory = avds / f'{name}.avd'
    directory.mkdir(parents=True, exist_ok=False)
    values = {
        'avd.ini.encoding': 'UTF-8', 'avd.id': name, 'avd.name': name,
        'abi.type': 'arm64-v8a', 'hw.cpu.arch': 'arm64', 'hw.cpu.ncore': '2',
        'image.sysdir.1': str(image) + '/', 'target': 'android-36',
        'tag.id': 'page_size_16kb', 'tag.ids': 'page_size_16kb,google_apis',
        'tag.display': '16 KB Page Size', 'PlayStore.enabled': 'no',
        'hw.lcd.width': '1080', 'hw.lcd.height': '2400', 'hw.lcd.density': '420',
        'hw.ramSize': '2560', 'vm.heapSize': '576M', 'hw.keyboard': 'yes',
        'hw.gpu.enabled': 'yes', 'hw.gpu.mode': 'swiftshader',
        'hw.camera.back': 'emulated', 'hw.camera.front': 'none', 'hw.sdCard': 'no',
        'disk.dataPartition.size': str(2 * 1024**3), 'userdata.useQcow2': 'no',
        'fastboot.forceColdBoot': 'yes',
    }
    (directory / 'config.ini').write_text(''.join(f'{k}={v}\n' for k, v in values.items()))
    (avds / f'{name}.ini').write_text(
        f'avd.ini.encoding=UTF-8\npath={directory}\ntarget=android-36\n')
    disk = directory / 'userdata-yuno.img'
    with disk.open('xb') as file:
        file.truncate(2 * 1024**3)
    subprocess.run([str(formatter), '-F', '-L', 'data', '-b', '4096', '-I', '256',
                    '-m', '0', '-E', 'lazy_itable_init=1,lazy_journal_init=1',
                    str(disk)], check=True)
    command = [str(sdk / 'emulator/emulator'), '-avd', name, '-data', str(disk),
               '-no-window', '-no-snapshot', '-no-boot-anim', '-no-audio',
               '-gpu', 'swiftshader', '-partition-size', '2048']
    print('ANDROID_AVD_HOME=' + shlex.quote(str(avds)), shlex.join(command))


if __name__ == '__main__':
    main()
