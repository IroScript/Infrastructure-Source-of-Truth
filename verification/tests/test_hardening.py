import json
import os
import subprocess
import sys
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'projects'))
sys.path.insert(0, str(ROOT / 'verification'))
from atomic_json import atomic_write_json, read_json, registry_lock
from precommit_safety import unsafe_paths, safe_stage
from discover_unregistered_projects import scan_for_projects, is_registered_project_path
from register_project import verify_remote_parity, register_project
from generate_derived_mappings import build_gitpush_entry
from finalize_project_onboarding import validate_data_policy
from finalize_project_onboarding import activation_gaps
from atomic_json import validate_project_registry
from validate_verifier_result import validate as validate_verifier
from audit_all_projects import check_git_status
from storage.backup_data import classify_remote_listing, consistent_snapshot
import sqlite3

class HardeningTests(unittest.TestCase):

    def test_fake_remote_never_verifies(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            subprocess.run(['git', 'init', '-q', str(repo)], check=True, timeout=15)
            subprocess.run(['git', '-C', str(repo), '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '--allow-empty', '-qm', 'init'], check=True, timeout=15)
            ok, reason = verify_remote_parity(str(repo), 'git@github.com:missing/fake-audit-remote.git', 'main')
            self.assertFalse(ok)
            self.assertIn(reason, {'REMOTE_UNREACHABLE_OR_BRANCH_MISSING', 'REMOTE_SHA_MISMATCH'})

    def test_fake_remote_registration_is_incomplete(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'project'
            path.mkdir()
            args = Namespace(path=str(path), id='fake_remote_test', name='Fake Remote', type='application', remote='git@github.com:missing/fake-audit-remote.git', branch='main', visibility='private', local_only=False, tmux='', whatsapp_group='', whatsapp_route='', data_files='', verification_profile='standard_project', dry_run=True)
            entry = register_project(args)
            self.assertNotEqual(entry['status'], 'ACTIVE')
            self.assertEqual(entry['status'], 'ONBOARDING_INCOMPLETE')
            self.assertNotIn('DATA_CLASSIFIED', entry['lifecycle_stages'])
            self.assertNotIn('VERIFICATION_CONFIGURED', entry['lifecycle_stages'])

    def test_failed_push_and_remote_sha_mismatch_are_not_verified(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            bare = base / 'remote.git'
            local = base / 'local'
            other = base / 'other'
            subprocess.run(['git', 'init', '--bare', '-q', '--initial-branch=main', str(bare)], check=True, timeout=15)
            subprocess.run(['git', 'init', '-q', '--initial-branch=main', str(local)], check=True, timeout=15)
            subprocess.run(['git', '-C', str(local), 'config', 'user.name', 'Audit'], check=True, timeout=15)
            subprocess.run(['git', '-C', str(local), 'config', 'user.email', 'audit@example.invalid'], check=True, timeout=15)
            (local / 'file.txt').write_text('one')
            subprocess.run(['git', '-C', str(local), 'add', 'file.txt'], check=True, timeout=15)
            subprocess.run(['git', '-C', str(local), 'commit', '-qm', 'one'], check=True, timeout=15)
            subprocess.run(['git', '-C', str(local), 'remote', 'add', 'origin', str(bare)], check=True, timeout=15)
            subprocess.run(['git', '-C', str(local), 'push', '-q', '-u', 'origin', 'main'], check=True, timeout=15)
            self.assertTrue(verify_remote_parity(str(local), str(bare), 'main')[0])
            subprocess.run(['git', 'clone', '-q', str(bare), str(other)], check=True, timeout=15)
            subprocess.run(['git', '-C', str(other), 'config', 'user.name', 'Audit'], check=True, timeout=15)
            subprocess.run(['git', '-C', str(other), 'config', 'user.email', 'audit@example.invalid'], check=True, timeout=15)
            (other / 'file.txt').write_text('two')
            subprocess.run(['git', '-C', str(other), 'commit', '-qam', 'two'], check=True, timeout=15)
            subprocess.run(['git', '-C', str(other), 'push', '-q', 'origin', 'main'], check=True, timeout=15)
            subprocess.run(['git', '-C', str(local), 'fetch', '-q', 'origin'], check=True, timeout=15)
            self.assertEqual(check_git_status(str(local))['behind'], 1)
            ok, reason = verify_remote_parity(str(local), str(bare), 'main')
            self.assertFalse(ok)
            self.assertEqual(reason, 'REMOTE_SHA_MISMATCH')
            fail = subprocess.run(['git', '-C', str(local), 'push', 'origin', 'missing-branch'], capture_output=True, text=True, timeout=15)
            self.assertNotEqual(fail.returncode, 0)

    def test_nested_and_deep_projects_are_discovered(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            parent = root / 'parent'
            parent.mkdir()
            (parent / 'package.json').write_text('{}')
            child = parent / 'child'
            child.mkdir()
            (child / 'Cargo.toml').write_text('[package]')
            deep = root / 'a' / 'b' / 'c' / 'd'
            deep.mkdir(parents=True)
            (deep / 'go.mod').write_text('module test')
            found = {Path(item['path']).resolve() for item in scan_for_projects(root)}
            self.assertIn(child.resolve(), found)
            self.assertIn(deep.resolve(), found)
            self.assertFalse(is_registered_project_path(child, {str(parent.resolve())}))
            self.assertTrue(is_registered_project_path(parent, {str(parent.resolve())}))

    def test_path_move_regenerates_canonical_mapping_by_immutable_identity(self):
        project = {'project_id': 'stable', 'project_uuid': '12345678-1234-4234-8234-123456789012', 'canonical_path': '/path/A', 'git': {'remote': 'origin'}, 'runtime': {'enabled': True}}
        before = build_gitpush_entry(project)
        project['canonical_path'] = '/path/B'
        after = build_gitpush_entry(project)
        self.assertEqual(before['key'], after['key'])
        self.assertEqual(before['project_uuid'], after['project_uuid'])
        self.assertEqual(after['folder_path'], '/path/B')

    def test_unknown_or_unbacked_persistent_data_cannot_finalize(self):
        self.assertFalse(validate_data_policy({'data_classification': 'unknown', 'project_id': 'p', 'canonical_path': '/tmp/p'})[0])
        self.assertTrue(validate_data_policy({'data_classification': 'source_only', 'project_id': 'p', 'canonical_path': '/tmp/p'})[0])
        self.assertFalse(validate_data_policy({'data_classification': 'persistent_data', 'project_id': 'p', 'canonical_path': '/tmp/p', 'data': ['db.sqlite']})[0])

    def test_activation_requires_remote_push_and_sot_publish(self):
        project = {'git': {'backup_required': True}}
        stages = {'GIT_INITIALIZED', 'DATA_CLASSIFIED', 'BACKUP_POLICY_CONFIGURED', 'VERIFICATION_CONFIGURED', 'REMOTE_CONFIGURED', 'REMOTE_REACHABLE', 'REMOTE_SHA_VERIFIED'}
        gaps = activation_gaps(project, stages)
        self.assertEqual(gaps, ['PUSH_VERIFIED', 'SOT_REGISTRATION_PUSHED'])
        stages.update(gaps)
        self.assertEqual(activation_gaps(project, stages), [])

    def test_duplicate_project_uuid_is_rejected(self):
        shared = '11111111-1111-4111-8111-111111111111'
        registry = {'projects': [{'project_id': 'one', 'project_uuid': shared, 'canonical_path': '/one'}, {'project_id': 'two', 'project_uuid': shared, 'canonical_path': '/two'}]}
        with self.assertRaises(ValueError):
            validate_project_registry(registry)

    def test_dirty_source_tree_is_detected(self):
        with tempfile.TemporaryDirectory() as td:
            subprocess.run(['git', 'init', '-q', '--initial-branch=main', td], check=True, timeout=15)
            subprocess.run(['git', '-C', td, 'config', 'user.name', 'Audit'], check=True, timeout=15)
            subprocess.run(['git', '-C', td, 'config', 'user.email', 'audit@example.invalid'], check=True, timeout=15)
            f = Path(td) / 'source.py'
            f.write_text('clean')
            subprocess.run(['git', '-C', td, 'add', 'source.py'], check=True, timeout=15)
            subprocess.run(['git', '-C', td, 'commit', '-qm', 'initial'], check=True, timeout=15)
            f.write_text('dirty')
            self.assertFalse(check_git_status(td)['clean'])

    def test_stale_backup_or_local_restore_cannot_claim_remote_restore(self):
        status, _ = classify_remote_listing([], 'asset.db', 5, 'a' * 64, 'b' * 32)
        self.assertEqual(status, 'REMOTE_UPLOAD_COMPLETE')
        self.assertNotEqual(status, 'REMOTE_RESTORE_VERIFIED')

    def test_sensitive_and_large_files_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / '.env.prod').write_text('x')
            (root / 'private.pem').write_text('key')
            (root / 'state.sqlite').write_bytes(b'db')
            (root / 'movie.mp4').write_bytes(b'0' * (50 * 1024 * 1024 + 1))
            bad = set(unsafe_paths(root))
            self.assertTrue({'.env.prod', 'private.pem', 'state.sqlite', 'movie.mp4'}.issubset(bad))

    def test_sensitive_files_block_staging(self):
        with tempfile.TemporaryDirectory() as td:
            subprocess.run(['git', 'init', '-q', td], check=True, timeout=15)
            (Path(td) / 'README.md').write_text('safe')
            (Path(td) / '.env.prod').write_text('credential')
            with self.assertRaises(ValueError):
                safe_stage(td)
            staged = subprocess.check_output(['git', '-C', td, 'diff', '--cached', '--name-only'], text=True)
            self.assertEqual(staged, '')

    def test_ssh_cookie_and_database_dump_artifacts_are_blocked(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            keydir = root / '.ssh'
            keydir.mkdir()
            (keydir / 'id_ed25519').write_text('private')
            (root / 'cookies-session.json').write_text('session')
            (root / 'backup.sql.gz').write_bytes(b'dump')
            bad = set(unsafe_paths(root))
            self.assertTrue({'.ssh', '.ssh/id_ed25519', 'cookies-session.json', 'backup.sql.gz'}.issubset(bad))

    def test_concurrent_atomic_updates_do_not_lose_changes(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'registry.json'
            atomic_write_json(path, {'values': []})
            script = "import sys; from atomic_json import registry_lock, read_json, atomic_write_json\np=sys.argv[1]; value=sys.argv[2]\nwith registry_lock(p):\n d=read_json(p); d['values'].append(value); atomic_write_json(p,d)\n"
            env = dict(os.environ, PYTHONPATH=str(ROOT / 'projects'))
            workers = [subprocess.Popen([sys.executable, '-c', script, str(path), str(i)], env=env) for i in range(100)]
            codes = [p.wait() for p in workers]
            self.assertEqual(codes, [0] * len(workers))
            values = read_json(path)['values']
            self.assertEqual(len(values), 100)
            self.assertEqual(len(set(values)), 100)

    def test_malformed_registry_is_rejected(self):
        with self.assertRaises(ValueError):
            from atomic_json import validate_project_registry
            validate_project_registry({'projects': [{'project_id': 'dup', 'canonical_path': '/a'}, {'project_id': 'dup', 'canonical_path': '/b'}]})

    def test_empty_ai_pass_evidence_is_rejected(self):
        ok, _ = validate_verifier({'task_id': 't1', 'verifier_id': 'ai', 'verifier_type': 'codex', 'timestamp': '2026-10-07T00:00:00Z', 'claim': 'claim', 'evidence': [], 'deterministic_result': 'pass', 'independent_verdict': 'approved', 'unresolved_items': [], 'confidence_category': 'high'})
        self.assertFalse(ok)

    def test_verifier_requires_hashed_files_and_negative_tests(self):
        import hashlib
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / 'out.txt').write_text('ok\n')
            (root / 'err.txt').write_text('')
            (root / 'neg-out.txt').write_text('')
            (root / 'neg-err.txt').write_text('blocked\n')
            (root / 'x.py').write_text("print('ok')\n")
            sha = lambda p: hashlib.sha256((root / p).read_bytes()).hexdigest()
            record = {'task_id': 't1', 'verifier_id': 'external', 'verifier_type': 'claude', 'timestamp': '2026-10-07T00:00:00Z', 'claim': 'claim', 'evidence': [{'command': 'python3', 'arguments': ['-c', 'pass'], 'stdout_ref': 'out.txt', 'stderr_ref': 'err.txt', 'stdout_sha256': sha('out.txt'), 'stderr_sha256': sha('err.txt'), 'exit_code': 0, 'commit_sha': 'a' * 40, 'runtime_identity': 'python3 test', 'timestamp': '2026-10-07T00:00:00Z', 'files_inspected': [{'path': 'x.py', 'artifact_ref': 'x.py', 'sha256': sha('x.py')}], 'negative_tests': [{'command': 'python3', 'arguments': ['-c', 'raise SystemExit(1)'], 'exit_code': 1, 'expected_exit_code': 1, 'expected_effect': 'blocked', 'observed_effect': 'blocked', 'expected_stderr_contains': 'blocked', 'matched': True, 'stdout_ref': 'neg-out.txt', 'stderr_ref': 'neg-err.txt', 'stdout_sha256': sha('neg-out.txt'), 'stderr_sha256': sha('neg-err.txt')}]}], 'deterministic_result': 'pass', 'independent_verdict': 'approved', 'unresolved_items': [], 'confidence_category': 'high'}
            self.assertTrue(validate_verifier(record, root)[0])
            record['evidence'][0]['stdout_sha256'] = 'f' * 64
            self.assertFalse(validate_verifier(record, root)[0])
            record['evidence'][0]['stdout_sha256'] = sha('out.txt')
            record['evidence'][0]['negative_tests'][0]['matched'] = False
            self.assertFalse(validate_verifier(record, root)[0])

    def test_remote_backup_status_needs_exact_object_and_size(self):
        status, obj = classify_remote_listing([], 'db.sqlite', 100, 'a' * 64)
        self.assertEqual(status, 'REMOTE_UPLOAD_COMPLETE')
        self.assertIsNone(obj)
        status, obj = classify_remote_listing([{'Name': 'db.sqlite', 'Size': 99, 'Hashes': {}}], 'db.sqlite', 100, 'a' * 64)
        self.assertEqual(status, 'REMOTE_UPLOAD_COMPLETE')
        self.assertIsNone(obj)
        status, obj = classify_remote_listing([{'Name': 'db.sqlite', 'Size': 100, 'Hashes': {}}], 'db.sqlite', 100, 'a' * 64)
        self.assertEqual(status, 'REMOTE_OBJECT_VERIFIED')
        self.assertNotEqual(status, 'REMOTE_RESTORE_VERIFIED')
        status, obj = classify_remote_listing([{'Name': 'db.sqlite', 'Size': 100, 'Hashes': {'md5': 'b' * 32}}], 'db.sqlite', 100, 'a' * 64, 'b' * 32)
        self.assertEqual(status, 'REMOTE_CHECKSUM_VERIFIED')

    def test_sqlite_snapshot_is_consistent_and_isolated(self):
        with tempfile.TemporaryDirectory() as td:
            source = Path(td) / 'live.db'
            with sqlite3.connect(source) as db:
                db.execute('CREATE TABLE items(value TEXT)')
                db.execute("INSERT INTO items VALUES ('before')")
            with consistent_snapshot(source) as snapshot:
                with sqlite3.connect(source) as db:
                    db.execute("INSERT INTO items VALUES ('after')")
                with sqlite3.connect(snapshot) as db:
                    values = [r[0] for r in db.execute('SELECT value FROM items ORDER BY rowid')]
                self.assertEqual(values, ['before'])
                self.assertTrue(Path(snapshot).is_file())
            self.assertFalse(Path(snapshot).exists())

    def test_blank_home_trust_install_and_tamper_fail_closed(self):
        with tempfile.TemporaryDirectory() as home:
            env = dict(os.environ, HOME=home)
            install = subprocess.run(['bash', str(ROOT / 'trust/restore_trust_baseline.sh')], env=env, capture_output=True, text=True, timeout=30)
            self.assertEqual(install.returncode, 0, install.stderr)
            settings = Path(home) / '.agents/settings.json'
            settings.write_text(settings.read_text() + '\n')
            verify = subprocess.run(['bash', str(ROOT / 'trust/verify_trust_baseline.sh')], env=env, capture_output=True, text=True, timeout=30)
            self.assertNotEqual(verify.returncode, 0)
            settings.write_bytes((ROOT / 'configuration/settings.json').read_bytes())
            runner = Path(home) / '.agents/run_regression_suite.py'
            runner.unlink()
            verify_missing = subprocess.run(['bash', str(ROOT / 'trust/verify_trust_baseline.sh')], env=env, capture_output=True, text=True, timeout=30)
            self.assertNotEqual(verify_missing.returncode, 0)
if __name__ == '__main__':
    unittest.main()