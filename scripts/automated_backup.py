"""Export, encrypt and independently restore YUNO data before retaining it.

No plaintext, account data, database credentials or encryption keys are logged.
The encrypted result is published only as an unpublished GitHub draft release.
"""
import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile
import urllib.error
import urllib.parse
import urllib.request

from cryptography.fernet import Fernet

from deploy import backup, transfer

REPOSITORY = 'zhanzonggeng123456-ai/yuno-life-shop'
MARKER = 'YUNO_ENCRYPTED_BACKUP_V1'
PREFIX = 'yuno-backup-'


def prepare(output):
    key = os.environ['YUNO_BACKUP_KEY'].encode().strip()
    # Fail before accessing data if the key isn't valid.
    cipher = Fernet(key)
    with tempfile.TemporaryDirectory(prefix='yuno-daily-') as directory:
        root = Path(directory)
        raw = root / 'snapshot.zip'
        transfer.export_remote(raw)
        key_file = root / 'key'
        key_file.write_bytes(key)
        key_file.chmod(0o600)
        backup.seal(raw, key_file, output)
        # A backup isn't successful until decrypt + full independent restore pass.
        backup.restore(cipher.decrypt(Path(output).read_bytes()), root / 'restore')
    return hashlib.sha256(Path(output).read_bytes()).hexdigest()


def retention_candidates(releases):
    """Only our own drafts: seven latest daily snapshots plus four weekly ones."""
    own = sorted((r for r in releases if r.get('draft') is True
                  and r.get('tag_name', '').startswith(PREFIX)
                  and MARKER in (r.get('body') or '')
                  and any(asset.get('name') == 'yuno-snapshot.yuno-backup'
                          and asset.get('state') == 'uploaded' and asset.get('size', 0) > 0
                          for asset in r.get('assets', []))),
                 key=lambda r: r['created_at'], reverse=True)
    keep = {r['id'] for r in own[:7]}
    weeks = set()
    for release in own:
        week = datetime.fromisoformat(release['created_at'].replace('Z', '+00:00')).isocalendar()[:2]
        if week not in weeks and len(weeks) < 4:
            keep.add(release['id'])
            weeks.add(week)
    return [r for r in own if r['id'] not in keep]


def api(path, method='GET', payload=None):
    token = os.environ['GH_TOKEN']
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request('https://api.github.com' + path, data=data, method=method,
        headers={'Authorization': 'Bearer ' + token, 'Accept': 'application/vnd.github+json',
                 'X-GitHub-Api-Version': '2022-11-28', 'Content-Type': 'application/json',
                 'User-Agent': 'YUNO-backup'})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            content = response.read()
            return json.loads(content) if content else None
    except urllib.error.HTTPError as error:
        # Never print HTTP request headers, response body or private signed URLs.
        raise RuntimeError(f'GitHub backup operation failed: HTTP {error.code}') from None


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, file, code, message, headers, url):
        return None


def download_asset(asset_id):
    request = urllib.request.Request(f'https://api.github.com/repos/{REPOSITORY}/releases/assets/{asset_id}',
        headers={'Authorization': 'Bearer ' + os.environ['GH_TOKEN'],
                 'Accept': 'application/octet-stream', 'User-Agent': 'YUNO-backup'})
    try:
        with urllib.request.build_opener(NoRedirect).open(request, timeout=60) as response:
            return response.read()
    except urllib.error.HTTPError as error:
        if error.code not in (301, 302, 303, 307, 308):
            raise RuntimeError(f'Backup download failed: HTTP {error.code}') from None
        location = error.headers['Location']
        parsed = urllib.parse.urlsplit(location)
        if parsed.scheme != 'https' or parsed.hostname != 'release-assets.githubusercontent.com':
            raise RuntimeError('Unexpected backup download destination')
        # Do not forward the repository token to the signed asset download host.
        with urllib.request.urlopen(location, timeout=60) as response:
            return response.read()


def publish(output, checksum):
    if os.environ.get('GITHUB_REPOSITORY') != REPOSITORY:
        raise RuntimeError('This job may only publish YUNO backups')
    status = api(f'/repos/{REPOSITORY}')
    if status.get('private') or status.get('visibility') != 'public':
        raise RuntimeError('Refuse private-repository runner costs; public standard Linux only')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    run_id = os.environ['GITHUB_RUN_ID']
    tag = PREFIX + stamp + '-' + run_id
    release = api(f'/repos/{REPOSITORY}/releases', 'POST', {
        'tag_name': tag, 'target_commitish': os.environ['GITHUB_SHA'],
        'name': 'YUNO encrypted backup ' + stamp, 'draft': True,
        'body': MARKER + '\nEncrypted private application data. Do not publish.\nSHA256: ' + checksum})
    upload_url = release['upload_url'].split('{')[0]
    expected = f'https://uploads.github.com/repos/{REPOSITORY}/releases/{release["id"]}/assets'
    if upload_url != expected or release.get('draft') is not True:
        raise RuntimeError('Unexpected release upload target or visibility')
    data = Path(output).read_bytes()
    request = urllib.request.Request(upload_url + '?name=yuno-snapshot.yuno-backup', data=data,
        headers={'Authorization': 'Bearer ' + os.environ['GH_TOKEN'],
                 'Content-Type': 'application/octet-stream', 'User-Agent': 'YUNO-backup'}, method='POST')
    with urllib.request.urlopen(request, timeout=120) as response:
        asset = json.load(response)
    if asset['size'] != len(data):
        raise RuntimeError('Uploaded backup size mismatch')
    downloaded = download_asset(asset['id'])
    if hashlib.sha256(downloaded).hexdigest() != checksum:
        raise RuntimeError('Independent backup download checksum mismatch')
    with tempfile.TemporaryDirectory(prefix='yuno-readback-') as directory:
        backup.restore(Fernet(os.environ['YUNO_BACKUP_KEY'].encode().strip()).decrypt(downloaded),
                       Path(directory) / 'restored')
    # This small non-sensitive receipt records a real successful backup in Git.
    # It also keeps an actively used backup workflow from becoming an idle repo.
    receipt_path = f'/repos/{REPOSITORY}/contents/ops/last-backup.json'
    try:
        old = api(receipt_path)
    except RuntimeError as error:
        if 'HTTP 404' not in str(error):
            raise
        old = None
    receipt = {'format': 1, 'created_at_utc': stamp, 'ciphertext_sha256': checksum,
               'draft_release_id': release['id'], 'verified_restore': True}
    body = {'message': 'ops: record verified encrypted YUNO backup [skip ci]',
            'content': base64.b64encode((json.dumps(receipt, indent=2) + '\n').encode()).decode(),
            'branch': 'main'}
    if old:
        body['sha'] = old['sha']
    api(receipt_path, 'PUT', body)
    # Preserve old backups until the NEW downloaded copy has restored correctly.
    releases = api(f'/repos/{REPOSITORY}/releases?per_page=100')
    for expired in retention_candidates(releases):
        api(f'/repos/{REPOSITORY}/releases/{expired["id"]}', 'DELETE')
    return {'encrypted': True, 'download_and_restore_verified': True,
            'draft_release_id': release['id'], 'sha256': checksum}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    parser.add_argument('--publish', action='store_true')
    args = parser.parse_args()
    try:
        checksum = prepare(args.output)
        result = publish(args.output, checksum) if args.publish else {'encrypted': True, 'sha256': checksum}
        print(json.dumps(result))
    except Exception as error:
        # Keep platform-provided exception strings from disclosing credentials.
        print('YUNO backup failed before completion (' + type(error).__name__ + '); old backups retained')
        raise SystemExit(1)


if __name__ == '__main__':
    main()
