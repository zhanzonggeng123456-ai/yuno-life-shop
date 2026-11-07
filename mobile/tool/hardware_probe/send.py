"""Send one JSON command to the separate XCTest runner over devicectl file I/O.

Use throwaway acceptance accounts. Receipts may contain form values and photos;
keep the output directory local and do not commit private device screenshots.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess
import time


def main():
    root = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', type=Path, help='JSON file with a unique id and op')
    parser.add_argument('--device', required=True)
    parser.add_argument('--output-dir', type=Path, default=root / 'outputs/hardware-control')
    parser.add_argument('--print-ax', action='store_true')
    args = parser.parse_args()
    command = json.loads(args.command.read_text())
    identifier = command.get('id', '')
    if not re.fullmatch(r'[A-Za-z0-9_-]+', identifier):
        parser.error('Use a unique alphanumeric command id, with optional hyphens/underscores')
    output = args.output_dir.resolve()
    if root not in output.parents:
        parser.error('Keep acceptance receipts inside this project')
    output.mkdir(parents=True, exist_ok=True, mode=0o700)
    output.chmod(0o700)
    request = output / 'command.json'
    request.write_text(json.dumps(command))
    request.chmod(0o600)
    common = ['--device', args.device, '--domain-type', 'appDataContainer',
              '--domain-identifier', 'com.yunolife.shop.hardwareprobe.xctrunner',
              '--timeout', '5']

    def copy(direction, source, destination, check=False):
        return subprocess.run(
            ['xcrun', 'devicectl', 'device', 'copy', direction, *common,
             '--source', str(source), '--destination', str(destination)],
            capture_output=True, text=True, check=check)

    receipt = output / f'{identifier}.json'
    if receipt.exists():
        parser.error('This receipt already exists; use a new command id')
    copy('to', request, 'Documents/command.json', check=True)
    for _ in range(40):
        result = copy('from', f'Documents/{identifier}.json', receipt)
        if result.returncode == 0 and receipt.exists():
            break
        time.sleep(0.5)
    else:
        raise RuntimeError('No XCTest receipt received: ' + result.stdout + result.stderr)
    data = json.loads(receipt.read_text())
    if command['op'] != 'finish':
        copy('from', f'Documents/{identifier}.png', output / f'{identifier}.png', check=True)
    print(identifier, data['state'], receipt)
    if args.print_ax:
        print(data.get('ax', ''))
    if data['state'] not in ('ok', 'finished'):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
