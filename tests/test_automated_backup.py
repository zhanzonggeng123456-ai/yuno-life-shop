from datetime import datetime, timedelta, timezone

from cryptography.fernet import Fernet
import pytest

from deploy import backup
from scripts import automated_backup
from test_backup import fixture_data


def test_backup_encrypts_and_restores_without_logging_private_records(tmp_path, monkeypatch, capsys):
    source, photos = fixture_data(tmp_path)
    monkeypatch.setenv('YUNO_BACKUP_KEY', Fernet.generate_key().decode())
    monkeypatch.setattr(automated_backup.transfer, 'export_remote',
                        lambda output: backup.create(source, photos, output))
    result = tmp_path / 'snapshot.yuno-backup'
    checksum = automated_backup.prepare(result)
    assert checksum == backup.digest(result.read_bytes())
    assert not capsys.readouterr().out
    assert b'private@example.jp' not in result.read_bytes()


def test_retention_keeps_seven_daily_and_four_weekly_and_never_other_releases():
    now = datetime(2026, 11, 6, tzinfo=timezone.utc)
    own = [{'id': index, 'draft': True, 'tag_name': automated_backup.PREFIX + str(index),
            'body': automated_backup.MARKER, 'created_at': (now-timedelta(days=index)).isoformat(),
            'assets': [{'name': 'yuno-snapshot.yuno-backup', 'state': 'uploaded', 'size': 10}]}
           for index in range(45)]
    others = [{'id': 100, 'draft': False, 'tag_name': automated_backup.PREFIX + 'public',
               'body': automated_backup.MARKER, 'created_at': now.isoformat()},
              {'id': 101, 'draft': True, 'tag_name': 'mobile-release', 'body': '', 'created_at': now.isoformat()}]
    expired = automated_backup.retention_candidates(own + others)
    ids = {release['id'] for release in expired}
    assert not ids.intersection(range(7))
    assert 100 not in ids and 101 not in ids
    kept = [release for release in own if release['id'] not in ids]
    weeks = {datetime.fromisoformat(release['created_at']).isocalendar()[:2] for release in kept}
    assert len(weeks) == 4
    assert 44 in ids
    incomplete = {**own[0], 'id': 200, 'assets': []}
    assert not automated_backup.retention_candidates([incomplete])


def test_publisher_refuses_other_projects_and_never_creates_public_backups(tmp_path, monkeypatch):
    monkeypatch.setenv('GITHUB_REPOSITORY', 'another/project')
    with pytest.raises(RuntimeError, match='only publish YUNO'):
        automated_backup.publish(tmp_path / 'unused', 'checksum')
    monkeypatch.setenv('GITHUB_REPOSITORY', automated_backup.REPOSITORY)
    monkeypatch.setenv('GITHUB_RUN_ID', '123')
    monkeypatch.setenv('GITHUB_SHA', 'source-commit')
    calls = []
    def fake_api(path, method='GET', payload=None):
        calls.append((path, method, payload))
        if path == '/repos/' + automated_backup.REPOSITORY:
            return {'private': False, 'visibility': 'public'}
        assert payload['draft'] is True
        # If a provider unexpectedly returns a published release, stop before upload.
        return {'id': 99, 'draft': False, 'upload_url': 'https://unrelated.example/assets'}
    monkeypatch.setattr(automated_backup, 'api', fake_api)
    with pytest.raises(RuntimeError, match='Unexpected release'):
        automated_backup.publish(tmp_path / 'unused', 'checksum')
    assert not any(method == 'DELETE' for _, method, _ in calls)
